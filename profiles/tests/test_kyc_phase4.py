from datetime import date, timedelta
from smtplib import SMTPAuthenticationError
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase
from django.utils import timezone

from authentication.models import User
from profiles.kyc_review import (
    KYC_REVIEWER_GROUP,
    KYC_SUPERVISOR_GROUP,
    assign_kyc_case,
    decide_kyc_case,
)
from profiles.models import (
    KycAttempt,
    KycDecisionEmailDelivery,
    KycReviewDecision,
)
from profiles.tasks import (
    KycDecisionEmailTransientError,
    _current_verified_kyc_recipient,
    dispatch_due_kyc_decision_emails,
    send_kyc_decision_email,
)


class KycDecisionEmailDeliveryTests(TestCase):
    def setUp(self):
        self.supervisor = self._user('phase4-supervisor@example.test')
        self.reviewer = self._user('phase4-reviewer@example.test')
        self.subject = self._user('phase4-subject@example.test')
        self.subject.firebase_uid = 'phase4-subject-firebase-uid'
        self.subject.save(update_fields=['firebase_uid'])
        supervisor_group, _ = Group.objects.get_or_create(name=KYC_SUPERVISOR_GROUP)
        reviewer_group, _ = Group.objects.get_or_create(name=KYC_REVIEWER_GROUP)
        self.supervisor.groups.add(supervisor_group)
        self.reviewer.groups.add(reviewer_group)

    @staticmethod
    def _user(email):
        return User.objects.create_user(
            email=email,
            password='safe-test-password',
            display_name='phase4',
            birth_date=date(1990, 1, 1),
            email_verified=True,
        )

    def _attempt(self):
        return KycAttempt.objects.create(
            user=self.subject,
            status=KycAttempt.PENDING_REVIEW,
            submitted_at=timezone.now(),
        )

    def _decision(self, *, decision, reason_code, idempotency_key):
        attempt = self._attempt()
        assign_kyc_case(
            supervisor=self.supervisor,
            attempt_id=attempt.id,
            reviewer_id=self.reviewer.id,
        )
        return decide_kyc_case(
            actor=self.reviewer,
            role=KYC_REVIEWER_GROUP,
            attempt_id=attempt.id,
            decision=decision,
            reason_code=reason_code,
            internal_comment='internal detail that must never leave the database',
            idempotency_key=idempotency_key,
        )

    @patch('profiles.kyc_review._queue_kyc_decision_email')
    def test_decision_creates_one_delivery_in_its_transaction_and_replay_does_not_queue_again(self, queue):
        values = {
            'decision': KycReviewDecision.VERIFIED,
            'reason_code': 'verified_human_review',
            'idempotency_key': 'phase4-delivery-idempotency-0001',
        }
        with self.captureOnCommitCallbacks(execute=True):
            record, replay = self._decision(**values)
        self.assertFalse(replay)
        delivery = KycDecisionEmailDelivery.objects.get(decision=record)
        self.assertEqual(delivery.status, KycDecisionEmailDelivery.PENDING)
        self.assertNotIn(
            'email',
            {field.name for field in KycDecisionEmailDelivery._meta.fields},
        )
        self.assertEqual(queue.call_count, 1)

        with self.captureOnCommitCallbacks(execute=True):
            same_record, replay = decide_kyc_case(
                actor=self.reviewer,
                role=KYC_REVIEWER_GROUP,
                attempt_id=record.attempt_id,
                decision=values['decision'],
                reason_code=values['reason_code'],
                internal_comment='internal detail that must never leave the database',
                idempotency_key=values['idempotency_key'],
            )
        self.assertTrue(replay)
        self.assertEqual(same_record.id, record.id)
        self.assertEqual(KycDecisionEmailDelivery.objects.count(), 1)
        self.assertEqual(queue.call_count, 1)

    @patch(
        'profiles.tasks.send_kyc_decision_email.delay',
        side_effect=OSError('synthetic broker outage'),
    )
    def test_broker_outage_leaves_the_committed_decision_and_delivery_pending(self, delay):
        with self.captureOnCommitCallbacks(execute=True):
            record, replay = self._decision(
                decision=KycReviewDecision.VERIFIED,
                reason_code='verified_human_review',
                idempotency_key='phase4-delivery-idempotency-0007',
            )
        self.assertFalse(replay)
        record.attempt.refresh_from_db()
        delivery = KycDecisionEmailDelivery.objects.get(decision=record)
        self.assertEqual(record.attempt.status, KycAttempt.VERIFIED)
        self.assertEqual(delivery.status, KycDecisionEmailDelivery.PENDING)
        delay.assert_called_once_with(str(delivery.id))

    def test_delivery_is_neutral_bilingual_and_does_not_change_an_approved_decision(self):
        record, _ = self._decision(
            decision=KycReviewDecision.VERIFIED,
            reason_code='verified_human_review',
            idempotency_key='phase4-delivery-idempotency-0002',
        )
        delivery = KycDecisionEmailDelivery.objects.get(decision=record)
        with patch(
            'profiles.tasks._current_verified_kyc_recipient',
            return_value=self.subject.email,
        ):
            result = send_kyc_decision_email.run(str(delivery.id))
        self.assertEqual(result, KycDecisionEmailDelivery.SENT)
        delivery.refresh_from_db()
        record.attempt.refresh_from_db()
        self.assertEqual(delivery.status, KycDecisionEmailDelivery.SENT)
        self.assertEqual(record.attempt.status, KycAttempt.VERIFIED)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn('Mise a jour', message.subject)
        self.assertIn('Verification update', message.subject)
        self.assertIn('Bonjour / Hello', message.body)
        self.assertNotIn('verified_human_review', message.body)
        self.assertNotIn('internal detail', message.body)
        self.assertNotIn('verified', message.body.lower())

    def test_transient_smtp_failure_retries_without_reversing_the_decision(self):
        record, _ = self._decision(
            decision=KycReviewDecision.REJECTED,
            reason_code='identity_unreadable',
            idempotency_key='phase4-delivery-idempotency-0003',
        )
        delivery = KycDecisionEmailDelivery.objects.get(decision=record)
        with patch(
            'profiles.tasks._current_verified_kyc_recipient',
            return_value=self.subject.email,
        ), patch(
            'profiles.tasks.EmailMultiAlternatives.send',
            side_effect=OSError('synthetic smtp outage'),
        ), self.assertRaises(KycDecisionEmailTransientError):
            send_kyc_decision_email.run(str(delivery.id))
        delivery.refresh_from_db()
        record.attempt.refresh_from_db()
        self.assertEqual(delivery.status, KycDecisionEmailDelivery.RETRYING)
        self.assertEqual(delivery.last_error_code, 'smtp_transient_failure')
        self.assertEqual(record.attempt.status, KycAttempt.REJECTED)

        delivery.next_attempt_at = timezone.now() - timedelta(seconds=1)
        delivery.save(update_fields=['next_attempt_at'])
        with patch(
            'profiles.tasks._current_verified_kyc_recipient',
            return_value=self.subject.email,
        ):
            result = send_kyc_decision_email.run(str(delivery.id))
        self.assertEqual(result, KycDecisionEmailDelivery.SENT)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, KycDecisionEmailDelivery.SENT)
        self.assertEqual(delivery.attempt_count, 2)

    def test_unverified_current_recipient_is_suppressed_without_email_or_decision_change(self):
        record, _ = self._decision(
            decision=KycReviewDecision.REVOKED,
            reason_code='manual_revocation',
            idempotency_key='phase4-delivery-idempotency-0004',
        )
        delivery = KycDecisionEmailDelivery.objects.get(decision=record)
        with patch('profiles.tasks._current_verified_kyc_recipient', return_value=None):
            result = send_kyc_decision_email.run(str(delivery.id))
        delivery.refresh_from_db()
        record.attempt.refresh_from_db()
        self.assertEqual(result, KycDecisionEmailDelivery.SUPPRESSED)
        self.assertEqual(delivery.last_error_code, 'recipient_not_verified')
        self.assertEqual(record.attempt.status, KycAttempt.REJECTED)
        self.assertEqual(len(mail.outbox), 0)

    @patch('hivmeet_backend.firebase_service.firebase_service.get_user')
    def test_recipient_must_still_match_a_verified_firebase_address(self, get_user):
        get_user.return_value = SimpleNamespace(
            email=self.subject.email.upper(),
            email_verified=True,
        )
        self.assertEqual(
            _current_verified_kyc_recipient(user_id=self.subject.id),
            self.subject.email,
        )
        get_user.return_value = SimpleNamespace(
            email=self.subject.email,
            email_verified=False,
        )
        self.assertIsNone(_current_verified_kyc_recipient(user_id=self.subject.id))

    def test_permanent_smtp_failure_is_durable_and_does_not_reverse_the_decision(self):
        record, _ = self._decision(
            decision=KycReviewDecision.VERIFIED,
            reason_code='verified_human_review',
            idempotency_key='phase4-delivery-idempotency-0006',
        )
        delivery = KycDecisionEmailDelivery.objects.get(decision=record)
        with patch(
            'profiles.tasks._current_verified_kyc_recipient',
            return_value=self.subject.email,
        ), patch(
            'profiles.tasks.EmailMultiAlternatives.send',
            side_effect=SMTPAuthenticationError(535, b'authentication failed'),
        ):
            result = send_kyc_decision_email.run(str(delivery.id))
        delivery.refresh_from_db()
        record.attempt.refresh_from_db()
        self.assertEqual(result, KycDecisionEmailDelivery.FAILED)
        self.assertEqual(delivery.last_error_code, 'smtp_permanent_failure')
        self.assertEqual(record.attempt.status, KycAttempt.VERIFIED)

    @patch('profiles.tasks.send_kyc_decision_email.delay')
    def test_dispatcher_recovers_pending_delivery_without_creating_another_row(self, delay):
        record, _ = self._decision(
            decision=KycReviewDecision.VERIFIED,
            reason_code='verified_human_review',
            idempotency_key='phase4-delivery-idempotency-0005',
        )
        delivery = KycDecisionEmailDelivery.objects.get(decision=record)
        self.assertEqual(dispatch_due_kyc_decision_emails.run(), 1)
        delay.assert_called_once_with(str(delivery.id))
        self.assertEqual(KycDecisionEmailDelivery.objects.filter(decision=record).count(), 1)
