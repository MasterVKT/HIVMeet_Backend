from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from authentication.models import User
from notifications.models import Notification
from profiles.kyc_review import (
    KYC_REVIEWER_GROUP,
    KYC_SUPERVISOR_GROUP,
    _totp_code,
    _totp_counter,
    assign_kyc_case,
    begin_mfa_enrollment,
    confirm_mfa_enrollment,
    decide_kyc_case,
    require_reviewer_mfa,
    verify_reviewer_mfa,
)
from profiles.kyc import serialize_safe_kyc_status
from profiles.models import KycAttempt, KycDocument, KycReviewAnomalyAlert, KycReviewDecision
from profiles.private_storage import private_object_storage
from profiles.tasks import (
    alert_kyc_review_access_anomalies,
    alert_overdue_kyc_reviews,
    expire_verified_kyc_attempts,
    purge_kyc_document,
)


class KycPhase3ReviewTests(TestCase):
    def setUp(self):
        self.supervisor = self._user('supervisor@example.test')
        self.reviewer = self._user('reviewer@example.test')
        self.outsider = self._user('outsider@example.test')
        supervisor_group, _ = Group.objects.get_or_create(name=KYC_SUPERVISOR_GROUP)
        reviewer_group, _ = Group.objects.get_or_create(name=KYC_REVIEWER_GROUP)
        self.supervisor.groups.add(supervisor_group)
        self.reviewer.groups.add(reviewer_group)
        self.attempt = KycAttempt.objects.create(
            user=self.outsider,
            status=KycAttempt.PENDING_REVIEW,
            submitted_at=timezone.now(),
        )

    @staticmethod
    def _user(email):
        return User.objects.create_user(
            email=email,
            password='safe-test-password',
            display_name=email.split('@')[0],
            birth_date=date(1990, 1, 1),
            email_verified=True,
        )

    def _mfa_assertion(self, user, at):
        _, uri = begin_mfa_enrollment(user=user)
        secret = parse_qs(urlparse(uri).query)['secret'][0]
        counter = _totp_counter(at)
        confirm_mfa_enrollment(user=user, code=_totp_code(secret, counter), now=at)
        assertion, _ = verify_reviewer_mfa(
            user=user,
            code=_totp_code(secret, counter + 1),
            now=at + timedelta(seconds=30),
        )
        return assertion

    def test_only_mfa_supervisor_can_assign_and_assigned_reviewer_can_decide(self):
        now = timezone.now().replace(microsecond=0)
        supervisor_assertion = self._mfa_assertion(self.supervisor, now)
        reviewer_assertion = self._mfa_assertion(self.reviewer, now)
        self.assertEqual(require_reviewer_mfa(user=self.supervisor, assertion=supervisor_assertion), KYC_SUPERVISOR_GROUP)

        assignment = assign_kyc_case(
            supervisor=self.supervisor,
            attempt_id=self.attempt.id,
            reviewer_id=self.reviewer.id,
            now=now,
        )
        record, replay = decide_kyc_case(
            actor=self.reviewer,
            role=require_reviewer_mfa(user=self.reviewer, assertion=reviewer_assertion),
            attempt_id=self.attempt.id,
            decision=KycReviewDecision.VERIFIED,
            reason_code='verified_human_review',
            internal_comment='minimal internal note',
            idempotency_key='phase3-decision-idempotency-0001',
            now=now + timedelta(minutes=1),
        )
        self.assertFalse(replay)
        self.assertEqual(record.assignment_id, assignment.id)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, KycAttempt.VERIFIED)
        self.assertFalse(self.attempt.is_open)
        self.assertGreater(self.attempt.expires_at, now)
        self.assertTrue(record.internal_comment_ciphertext)
        self.assertNotIn('minimal internal note', record.internal_comment_ciphertext)
        self.assertTrue(Notification.objects.filter(
            user=self.outsider, type='system', data__event='verification_update',
        ).exists())
        audit = self.attempt.audit_events.filter(event_type='review_decision_recorded').last()
        self.assertIsNotNone(audit)
        self.assertNotIn('minimal internal note', str(audit.metadata))

    def test_outsider_or_missing_mfa_cannot_assign_or_decide(self):
        with self.assertRaises(PermissionDenied):
            require_reviewer_mfa(user=self.outsider, assertion='not-valid')
        now = timezone.now().replace(microsecond=0)
        supervisor_assertion = self._mfa_assertion(self.supervisor, now)
        assignment = assign_kyc_case(
            supervisor=self.supervisor, attempt_id=self.attempt.id,
            reviewer_id=self.reviewer.id, now=now,
        )
        self.assertIsNotNone(assignment)
        with self.assertRaises(PermissionDenied):
            decide_kyc_case(
                actor=self.outsider, role='', attempt_id=self.attempt.id,
                decision=KycReviewDecision.REJECTED, reason_code='invalid',
                internal_comment='', idempotency_key='phase3-decision-idempotency-0002', now=now,
            )
        with self.assertRaises(PermissionDenied):
            require_reviewer_mfa(user=self.supervisor, assertion='wrong')
        self.assertTrue(supervisor_assertion)

    def test_decision_replay_requires_identical_request(self):
        now = timezone.now().replace(microsecond=0)
        self._mfa_assertion(self.supervisor, now)
        reviewer_assertion = self._mfa_assertion(self.reviewer, now)
        assign_kyc_case(supervisor=self.supervisor, attempt_id=self.attempt.id, reviewer_id=self.reviewer.id, now=now)
        role = require_reviewer_mfa(user=self.reviewer, assertion=reviewer_assertion)
        values = dict(
            actor=self.reviewer, role=role, attempt_id=self.attempt.id,
            decision=KycReviewDecision.REJECTED, reason_code='identity_unreadable',
            internal_comment='', idempotency_key='phase3-decision-idempotency-0003', now=now,
        )
        _, replay = decide_kyc_case(**values)
        self.assertFalse(replay)
        _, replay = decide_kyc_case(**values)
        self.assertTrue(replay)
        status = serialize_safe_kyc_status(user=self.outsider)
        self.assertEqual(status['status'], KycAttempt.REJECTED)
        self.assertEqual(status['rejection_reason_code'], 'identity_unreadable')

    def test_overdue_review_creates_only_generic_supervisor_alert(self):
        self.attempt.submitted_at = timezone.now() - timedelta(hours=25)
        self.attempt.save(update_fields=['submitted_at'])
        self.assertEqual(alert_overdue_kyc_reviews.run(), 1)
        self.assertTrue(Notification.objects.filter(
            user=self.supervisor, data__event='kyc_review_sla',
        ).exists())
        self.assertTrue(self.attempt.audit_events.filter(
            event_type='review_sla_alerted',
        ).exists())
        self.assertEqual(alert_overdue_kyc_reviews.run(), 0)

    def test_internal_routes_require_authentication_mfa_and_assignment(self):
        client = APIClient()
        self.assertEqual(client.get('/api/v1/internal/kyc/cases/').status_code, 401)
        client.force_authenticate(self.reviewer)
        self.assertEqual(client.get('/api/v1/internal/kyc/cases/').status_code, 403)
        client.force_authenticate(self.supervisor)
        now = timezone.now().replace(microsecond=0)
        _, uri = begin_mfa_enrollment(user=self.supervisor)
        secret = parse_qs(urlparse(uri).query)['secret'][0]
        counter = _totp_counter(now)
        self.assertEqual(client.post('/api/v1/internal/kyc/mfa/confirm/', {'code': _totp_code(secret, counter)}, format='json').status_code, 200)
        assertion = client.post('/api/v1/internal/kyc/mfa/assertions/', {'code': _totp_code(secret, counter + 1)}, format='json').data['assertion']
        response = client.post(
            f'/api/v1/internal/kyc/cases/{self.attempt.id}/assignment/',
            {'reviewer_id': str(self.reviewer.id)}, format='json',
            HTTP_X_KYC_MFA_ASSERTION=assertion,
        )
        self.assertEqual(response.status_code, 200)

    def test_revocation_schedules_purge_and_expiration_removes_access(self):
        now = timezone.now().replace(microsecond=0)
        self._mfa_assertion(self.supervisor, now)
        reviewer_assertion = self._mfa_assertion(self.reviewer, now)
        key = 'kyc/quarantine/' + ('a' * 32)
        private_object_storage.put_bytes(
            scope='kyc', key=key, data=b'synthetic-kyc-fixture',
            content_type='application/octet-stream',
        )
        document = KycDocument.objects.create(
            attempt=self.attempt,
            document_type=KycDocument.IDENTITY_DOCUMENT,
            opaque_storage_key=key,
            scan_status=KycDocument.ACCEPTED,
        )
        assign_kyc_case(supervisor=self.supervisor, attempt_id=self.attempt.id, reviewer_id=self.reviewer.id, now=now)
        decide_kyc_case(
            actor=self.reviewer,
            role=require_reviewer_mfa(user=self.reviewer, assertion=reviewer_assertion),
            attempt_id=self.attempt.id, decision=KycReviewDecision.REVOKED,
            reason_code='manual_revocation', internal_comment='',
            idempotency_key='phase3-decision-idempotency-0004', now=now,
        )
        self.attempt.refresh_from_db()
        document.refresh_from_db()
        self.assertEqual(self.attempt.status, KycAttempt.REJECTED)
        self.assertEqual(self.attempt.rejection_reason_code, 'manual_revocation')
        self.assertEqual(document.purge_after, now)
        self.assertEqual(purge_kyc_document.run(str(document.id)), 'purged')
        document.refresh_from_db()
        self.assertEqual(document.scan_status, KycDocument.PURGED)

        expiring = KycAttempt.objects.create(
            user=self._user('expired@example.test'), status=KycAttempt.VERIFIED,
            expires_at=now - timedelta(seconds=1), is_open=False,
        )
        self.assertEqual(expire_verified_kyc_attempts.run(), 1)
        expiring.refresh_from_db()
        self.assertEqual(expiring.status, KycAttempt.EXPIRED)

    def test_assigned_reviewer_can_read_synthetic_memory_document_only(self):
        now = timezone.now().replace(microsecond=0)
        self._mfa_assertion(self.supervisor, now)
        reviewer_assertion = self._mfa_assertion(self.reviewer, now)
        key = 'kyc/quarantine/' + ('b' * 32)
        private_object_storage.put_bytes(
            scope='kyc', key=key, data=b'synthetic-kyc-fixture',
            content_type='application/octet-stream',
        )
        document = KycDocument.objects.create(
            attempt=self.attempt, document_type=KycDocument.IDENTITY_DOCUMENT,
            opaque_storage_key=key, scan_status=KycDocument.ACCEPTED,
        )
        assign_kyc_case(supervisor=self.supervisor, attempt_id=self.attempt.id, reviewer_id=self.reviewer.id, now=now)
        client = APIClient()
        client.force_authenticate(self.reviewer)
        response = client.get(
            f'/api/v1/internal/kyc/cases/{self.attempt.id}/documents/{document.id}/development-content/',
            HTTP_X_KYC_MFA_ASSERTION=reviewer_assertion,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'synthetic-kyc-fixture')
        self.assertEqual(response['Cache-Control'], 'no-store, max-age=0')
        self.assertTrue(self.attempt.audit_events.filter(event_type='review_document_accessed').exists())

    def test_memory_read_url_does_not_expose_the_storage_key(self):
        now = timezone.now().replace(microsecond=0)
        self._mfa_assertion(self.supervisor, now)
        reviewer_assertion = self._mfa_assertion(self.reviewer, now)
        key = 'kyc/quarantine/' + ('c' * 32)
        document = KycDocument.objects.create(
            attempt=self.attempt, document_type=KycDocument.IDENTITY_DOCUMENT,
            opaque_storage_key=key, scan_status=KycDocument.ACCEPTED,
        )
        assign_kyc_case(supervisor=self.supervisor, attempt_id=self.attempt.id, reviewer_id=self.reviewer.id, now=now)
        client = APIClient()
        client.force_authenticate(self.reviewer)
        response = client.post(
            f'/api/v1/internal/kyc/cases/{self.attempt.id}/documents/{document.id}/access/',
            HTTP_X_KYC_MFA_ASSERTION=reviewer_assertion,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['url'], 'https://review.invalid/development-only')
        self.assertNotIn(key, response.data['url'])

    def test_development_document_content_route_fails_closed_outside_safe_mode(self):
        now = timezone.now().replace(microsecond=0)
        self._mfa_assertion(self.supervisor, now)
        reviewer_assertion = self._mfa_assertion(self.reviewer, now)
        document = KycDocument.objects.create(
            attempt=self.attempt, document_type=KycDocument.IDENTITY_DOCUMENT,
            opaque_storage_key='kyc/quarantine/' + ('d' * 32),
            scan_status=KycDocument.ACCEPTED,
        )
        assign_kyc_case(supervisor=self.supervisor, attempt_id=self.attempt.id, reviewer_id=self.reviewer.id, now=now)
        client = APIClient()
        client.force_authenticate(self.reviewer)
        with self.settings(DEBUG=False, TESTING=False, KYC_STORAGE_BACKEND='memory'):
            response = client.get(
                f'/api/v1/internal/kyc/cases/{self.attempt.id}/documents/{document.id}/development-content/',
                HTTP_X_KYC_MFA_ASSERTION=reviewer_assertion,
            )
        self.assertEqual(response.status_code, 403)

    def test_document_access_anomaly_is_generic_and_idempotent(self):
        now = timezone.now().replace(microsecond=0)
        self._mfa_assertion(self.supervisor, now)
        reviewer_assertion = self._mfa_assertion(self.reviewer, now)
        key = 'kyc/quarantine/' + ('e' * 32)
        private_object_storage.put_bytes(
            scope='kyc', key=key, data=b'synthetic-kyc-fixture',
            content_type='application/octet-stream',
        )
        document = KycDocument.objects.create(
            attempt=self.attempt, document_type=KycDocument.IDENTITY_DOCUMENT,
            opaque_storage_key=key, scan_status=KycDocument.ACCEPTED,
        )
        assign_kyc_case(supervisor=self.supervisor, attempt_id=self.attempt.id, reviewer_id=self.reviewer.id, now=now)
        client = APIClient()
        client.force_authenticate(self.reviewer)
        self.assertEqual(client.get(
            f'/api/v1/internal/kyc/cases/{self.attempt.id}/documents/{document.id}/development-content/',
            HTTP_X_KYC_MFA_ASSERTION=reviewer_assertion,
        ).status_code, 200)
        with self.settings(KYC_REVIEW_ANOMALY_ACCESS_THRESHOLD=1):
            self.assertEqual(alert_kyc_review_access_anomalies.run(), 1)
            self.assertEqual(alert_kyc_review_access_anomalies.run(), 0)
        self.assertTrue(KycReviewAnomalyAlert.objects.filter(actor=self.reviewer).exists())
        notification = Notification.objects.get(
            user=self.supervisor, data__event='kyc_review_anomaly',
        )
        self.assertNotIn(str(self.attempt.id), str(notification.data))
        self.assertTrue(self.attempt.audit_events.filter(
            event_type='review_access_anomaly_alerted',
        ).exists())
