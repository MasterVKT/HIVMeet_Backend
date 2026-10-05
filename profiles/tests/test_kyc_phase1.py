from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import resolve
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from hivmeet_backend.asgi import application
from profiles.kyc import (
    HasActiveKycVerification,
    KycIdempotencyConflict,
    KycRateLimited,
    has_active_kyc,
    start_or_resume_kyc_attempt,
    submit_kyc_attempt,
)
from profiles.models import KycAttempt, KycDocument, KycUploadIntent, Verification
from subscriptions.utils import is_premium_user


User = get_user_model()


class KycPhase1Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='kyc-owner@example.test',
            password='safe-test-password',
            display_name='Kyc Owner',
            birth_date='1990-01-01',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _verify_attempt(self, user=None):
        user = user or self.user
        return KycAttempt.objects.create(
            user=user,
            status=KycAttempt.VERIFIED,
            is_open=False,
            expires_at=timezone.now() + timedelta(days=1),
        )

    def test_legacy_verification_is_not_an_access_source(self):
        verification = Verification.objects.get(user=self.user)
        verification.status = Verification.VERIFIED
        verification.expires_at = timezone.now() + timedelta(days=1)
        verification.save()

        self.assertFalse(has_active_kyc(self.user))
        response = self.client.get('/api/v1/discovery/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error'], 'kyc_required')

    def test_verified_nonexpired_attempt_is_the_only_access_source(self):
        self._verify_attempt()
        self.assertTrue(has_active_kyc(self.user))

        attempt = KycAttempt.objects.get(user=self.user)
        attempt.expires_at = timezone.now() - timedelta(seconds=1)
        attempt.save(update_fields=['expires_at'])
        self.assertFalse(has_active_kyc(self.user))

    def test_start_is_idempotent_and_status_read_is_non_mutating(self):
        before_count = KycAttempt.objects.count()
        first = self.client.post(
            '/api/v1/user-profiles/me/verification/start/',
            {
                'consent_version': 'kyc-v1-test',
                'confirmations': {
                    'official_identity_document': True,
                    'medical_document_under_90_days': True,
                    'single_use_selfie_challenge': True,
                    'human_review_acknowledged': True,
                },
                'idempotency_key': 'start-key-0000001',
            },
            format='json',
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(KycAttempt.objects.count(), before_count + 1)
        self.assertIn('code', first.data['selfie_challenge'])
        self.assertEqual(first['Cache-Control'], 'no-store, max-age=0')
        self.assertEqual(first['Pragma'], 'no-cache')
        self.assertEqual(first['X-Content-Type-Options'], 'nosniff')

        replay = self.client.post(
            '/api/v1/user-profiles/me/verification/start/',
            {
                'consent_version': 'kyc-v1-test',
                'confirmations': {
                    'official_identity_document': True,
                    'medical_document_under_90_days': True,
                    'single_use_selfie_challenge': True,
                    'human_review_acknowledged': True,
                },
                'idempotency_key': 'start-key-0000001',
            },
            format='json',
        )
        self.assertEqual(replay.status_code, status.HTTP_200_OK)
        self.assertTrue(replay.data['idempotent_replay'])
        self.assertEqual(replay['Cache-Control'], 'no-store, max-age=0')
        self.assertEqual(
            first.data['selfie_challenge']['code'],
            replay.data['selfie_challenge']['code'],
        )
        self.assertEqual(KycAttempt.objects.count(), before_count + 1)

        status_response = self.client.get('/api/v1/user-profiles/me/verification/')
        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        self.assertEqual(status_response['Cache-Control'], 'no-store, max-age=0')
        self.assertNotIn('code', status_response.data)
        self.assertNotIn('challenge_hash', status_response.data)
        self.assertNotIn('opaque_storage_key', status_response.data)

    def test_start_conflicting_idempotency_key_and_reissue_quota_are_rejected(self):
        with patch('profiles.kyc.KYC_ATTEMPT_DAILY_LIMIT', 1):
            start_or_resume_kyc_attempt(
                user=self.user,
                consent_version='kyc-v1-test',
                idempotency_key='quota-start-key-01',
            )
            with self.assertRaises(KycIdempotencyConflict):
                start_or_resume_kyc_attempt(
                    user=self.user,
                    consent_version='kyc-v1-other',
                    idempotency_key='quota-start-key-01',
                )
            with self.assertRaises(KycRateLimited):
                start_or_resume_kyc_attempt(
                    user=self.user,
                    consent_version='kyc-v1-test',
                    idempotency_key='quota-start-key-02',
                )

    def test_selfie_pdf_is_rejected_and_intent_exposes_no_storage_key(self):
        attempt, _, _ = start_or_resume_kyc_attempt(
            user=self.user,
            consent_version='kyc-v1-test',
            idempotency_key='service-start-key-01',
        )
        invalid = self.client.post(
            '/api/v1/user-profiles/me/verification/upload-intents/',
            {
                'attempt_id': str(attempt.id),
                'document_type': 'selfie_with_code',
                'mime_type': 'application/pdf',
                'size_bytes': 1024,
                'sha256': 'a' * 64,
                'idempotency_key': 'upload-key-0000001',
            },
            format='json',
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)

        issued = self.client.post(
            '/api/v1/user-profiles/me/verification/upload-intents/',
            {
                'attempt_id': str(attempt.id),
                'document_type': 'identity_document',
                'mime_type': 'image/jpeg',
                'size_bytes': 1024,
                'sha256': 'a' * 64,
                'idempotency_key': 'upload-key-0000002',
            },
            format='json',
        )
        self.assertEqual(issued.status_code, status.HTTP_201_CREATED)
        self.assertIn('upload_url', issued.data)
        self.assertNotIn('opaque_object_key', issued.data)
        self.assertNotIn('opaque_storage_key', issued.data)
        self.assertNotIn('file_path_on_storage', issued.data)

    def test_legacy_storage_routes_are_gone(self):
        for path in (
            '/api/v1/user-profiles/me/verification/generate-upload-url/',
            '/api/v1/user-profiles/me/verification/submit-documents/',
        ):
            response = self.client.post(path, {}, format='json')
            self.assertEqual(response.status_code, status.HTTP_410_GONE)
            self.assertEqual(response.data['error'], 'kyc_legacy_endpoint_deprecated')

    def test_submit_requires_three_server_owned_accepted_intents_and_consumes_challenge(self):
        attempt, challenge_code, _ = start_or_resume_kyc_attempt(
            user=self.user,
            consent_version='kyc-v1-test',
            idempotency_key='service-start-key-02',
        )
        uploads = {}
        for document_type, payload_key in (
            (KycDocument.IDENTITY_DOCUMENT, 'identity_upload_id'),
            (KycDocument.MEDICAL_DOCUMENT, 'medical_upload_id'),
            (KycDocument.SELFIE_WITH_CODE, 'selfie_upload_id'),
        ):
            document = KycDocument.objects.create(
                attempt=attempt,
                document_type=document_type,
                opaque_storage_key=f'opaque-{uuid4()}',
                scan_status=KycDocument.ACCEPTED,
            )
            intent = KycUploadIntent.objects.create(
                attempt=attempt,
                document_type=document.document_type,
                declared_mime_type='image/jpeg',
                declared_size_bytes=1,
                declared_sha256='a' * 64,
                idempotency_key=f'intent-{uuid4()}',
                opaque_object_key=f'object-{uuid4()}',
                status=KycUploadIntent.CONSUMED,
                expires_at=timezone.now() + timedelta(minutes=30),
                used_at=timezone.now(),
            )
            uploads[payload_key] = intent.id

        submitted, replay = submit_kyc_attempt(
            user=self.user,
            attempt_id=attempt.id,
            upload_ids=uploads,
            selfie_challenge_code=challenge_code,
            idempotency_key='submit-key-0000001',
        )
        self.assertFalse(replay)
        self.assertEqual(submitted.status, KycAttempt.PENDING_REVIEW)
        self.assertIsNotNone(submitted.challenge_used_at)

        event = submitted.audit_events.get(event_type='attempt_submitted')
        self.assertNotEqual(event.metadata['idempotency_key'], 'submit-key-0000001')
        self.assertTrue(event.metadata['idempotency_key'].startswith('v1:'))

        replayed, replay = submit_kyc_attempt(
            user=self.user,
            attempt_id=attempt.id,
            upload_ids=uploads,
            selfie_challenge_code=challenge_code,
            idempotency_key='submit-key-0000001',
        )
        self.assertTrue(replay)
        self.assertEqual(replayed.id, submitted.id)

        # A deployment may have pre-fingerprinting audit rows. Preserve the
        # legitimate retry path without writing further raw client input.
        event.metadata['idempotency_key'] = 'submit-key-0000001'
        event.save(update_fields=['metadata'])
        legacy_replayed, legacy_replay = submit_kyc_attempt(
            user=self.user,
            attempt_id=attempt.id,
            upload_ids=uploads,
            selfie_challenge_code=challenge_code,
            idempotency_key='submit-key-0000001',
        )
        self.assertTrue(legacy_replay)
        self.assertEqual(legacy_replayed.id, submitted.id)

    def test_open_attempt_constraint_and_premium_effective_gate(self):
        KycAttempt.objects.create(user=self.user, status=KycAttempt.NOT_STARTED)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                KycAttempt.objects.create(
                    user=self.user,
                    status=KycAttempt.PENDING_ID,
                )

        self.user.is_premium = True
        self.user.premium_until = timezone.now() + timedelta(days=1)
        self.user.save(update_fields=['is_premium', 'premium_until'])
        self.assertFalse(is_premium_user(self.user))
        KycAttempt.objects.filter(user=self.user).update(is_open=False)
        self._verify_attempt()
        self.assertTrue(is_premium_user(self.user))

    def test_every_live_social_and_premium_mutation_route_has_kyc_permission(self):
        identifier = '00000000-0000-0000-0000-000000000001'
        paths = [
            f'/api/v1/user-profiles/{identifier}/',
            '/api/v1/user-profiles/likes-received/',
            '/api/v1/user-profiles/super-likes-received/',
            '/api/v1/user-settings/blocks',
            f'/api/v1/user-settings/blocks/{identifier}',
            '/api/v1/discovery/',
            '/api/v1/discovery/profiles',
            '/api/v1/discovery/filters',
            '/api/v1/discovery/filters/get',
            '/api/v1/discovery/interactions/like',
            '/api/v1/discovery/interactions/dislike',
            '/api/v1/discovery/interactions/superlike',
            '/api/v1/discovery/interactions/super-like',
            f'/api/v1/discovery/interactions/{identifier}/rewind/',
            '/api/v1/discovery/interactions/rewind',
            '/api/v1/discovery/interactions/liked-me',
            '/api/v1/discovery/interactions/status',
            '/api/v1/discovery/interactions/my-likes',
            '/api/v1/discovery/interactions/my-passes',
            '/api/v1/discovery/interactions/revoke-bulk',
            f'/api/v1/discovery/interactions/{identifier}/revoke',
            '/api/v1/discovery/interactions/stats',
            '/api/v1/discovery/boost/activate',
            '/api/v1/matches/',
            '/api/v1/matches/unseen-count/',
            '/api/v1/matches/seen/',
            '/api/v1/matches/likes-received/reveal/',
            f'/api/v1/matches/{identifier}/unlock-free/',
            f'/api/v1/matches/{identifier}',
            '/api/v1/conversations/',
            '/api/v1/conversations/unread-count/',
            f'/api/v1/conversations/{identifier}/messages/',
            f'/api/v1/conversations/{identifier}/messages/media/',
            f'/api/v1/conversations/{identifier}/messages/{identifier}/media/',
            f'/api/v1/conversations/{identifier}/messages/mark-as-read/',
            f'/api/v1/conversations/{identifier}/messages/delete/',
            f'/api/v1/conversations/{identifier}/messages/{identifier}/',
            f'/api/v1/conversations/{identifier}/messages/{identifier}/read/',
            f'/api/v1/conversations/{identifier}/typing/',
            f'/api/v1/conversations/{identifier}/presence/',
            '/api/v1/conversations/calls/initiate-premium/',
            f'/api/v1/conversations/{identifier}/restore/',
            f'/api/v1/conversations/{identifier}/',
            '/api/v1/calls/initiate',
            f'/api/v1/calls/{identifier}/answer',
            f'/api/v1/calls/{identifier}/ice-candidate',
            f'/api/v1/calls/{identifier}/terminate',
            '/api/v1/notifications/',
            '/api/v1/notifications/unread-count/',
            '/api/v1/notifications/read-all/',
            '/api/v1/notifications/delete-all/',
            f'/api/v1/notifications/{identifier}/read/',
            f'/api/v1/notifications/{identifier}/delete/',
            '/api/v1/feed/posts',
            f'/api/v1/feed/posts/{identifier}/like',
            f'/api/v1/feed/posts/{identifier}/comments',
            '/api/v1/subscriptions/purchase/',
            '/api/v1/subscriptions/current/reactivate/',
            '/api/v1/subscriptions/current/modify/',
        ]
        for path in paths:
            resolved = resolve(path)
            self.assertIn(
                HasActiveKycVerification,
                resolved.func.cls.permission_classes,
                path,
            )

    def test_unverified_request_is_rejected_before_social_or_premium_processing(self):
        requests = [
            ('get', '/api/v1/user-profiles/00000000-0000-0000-0000-000000000001/'),
            ('get', '/api/v1/discovery/filters/get'),
            ('post', '/api/v1/discovery/interactions/like'),
            ('get', '/api/v1/matches/'),
            ('get', '/api/v1/conversations/'),
            ('post', '/api/v1/calls/initiate'),
            ('get', '/api/v1/notifications/'),
            ('get', '/api/v1/feed/posts'),
            ('post', '/api/v1/subscriptions/purchase/'),
            ('post', '/api/v1/subscriptions/current/reactivate/'),
            ('post', '/api/v1/subscriptions/current/modify/'),
        ]
        for method, path in requests:
            response = getattr(self.client, method)(path, {}, format='json')
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, path)
            self.assertEqual(response.data['error'], 'kyc_required', path)


class KycWebSocketPhase1Tests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='kyc-websocket@example.test',
            password='safe-test-password',
            display_name='Kyc Socket',
            birth_date='1990-01-01',
        )
        self.token = str(RefreshToken.for_user(self.user).access_token)

    async def _connect(self, path):
        communicator = WebsocketCommunicator(
            application,
            path,
            headers=[(b'authorization', f'Bearer {self.token}'.encode('ascii'))],
        )
        connected, detail = await communicator.connect()
        if connected:
            await communicator.disconnect()
        return connected, detail

    def test_unverified_user_cannot_open_social_websockets(self):
        conversation_path = f'/ws/conversations/{uuid4()}/'
        connected, close_code = async_to_sync(self._connect)(conversation_path)
        self.assertFalse(connected)
        self.assertEqual(close_code, 4403)

        connected, close_code = async_to_sync(self._connect)('/ws/notifications/')
        self.assertFalse(connected)
        self.assertEqual(close_code, 4403)
