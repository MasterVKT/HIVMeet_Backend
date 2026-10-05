from datetime import date, timedelta
from importlib import import_module
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory

from profiles.kyc import KYC_UPLOAD_INTENT_TTL, start_or_resume_kyc_attempt
from profiles.models import (
    AccountDeletionRequest,
    DataExportRequest,
    KycAttempt,
    KycDocument,
    KycUploadIntent,
    ProfilePhoto,
)
from profiles.photo_storage import (
    ProfilePhotoStorageUnavailable,
    profile_photo_delivery_url,
    profile_photo_storage,
)
from profiles.private_storage import (
    PrivateObjectIntegrityError,
    PrivateObjectNotFound,
    PrivateStorageUnavailable,
    private_object_storage,
    private_storage_configuration_errors,
    validate_document_binary,
)
from profiles.tasks import (
    _build_export_payload,
    _delete_private_kyc_objects_for_user,
    _delete_profile_media_for_user,
    expire_kyc_upload_intents,
    expire_verified_kyc_attempts,
    migrate_legacy_profile_photo,
    purge_due_kyc_documents,
    purge_kyc_document,
    verify_kyc_upload,
)
from profiles.views import _delete_photo_references
from profiles.views_settings import _serialize_data_request
from hivmeet_backend.kyc_runtime import (
    validate_kyc_runtime_gate,
    validate_private_storage_runtime_gate,
)
from hivmeet_backend.storage.manager import StorageManager


User = get_user_model()


class KycPhase2StorageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='kyc-phase2@example.test',
            password='safe-test-password',
            display_name='Kyc Phase 2',
            birth_date=date(1990, 1, 1),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.attempt, _, _ = start_or_resume_kyc_attempt(
            user=self.user,
            consent_version='kyc-v1-test',
            idempotency_key='phase2-start-key-0001',
        )

    def test_upload_intent_default_ttl_matches_the_canonical_plan(self):
        self.assertEqual(KYC_UPLOAD_INTENT_TTL, timedelta(minutes=30))

    @staticmethod
    def _jpeg_bytes():
        image = Image.new('RGB', (24, 24), color='purple')
        output = BytesIO()
        image.save(output, format='JPEG')
        return output.getvalue()

    @staticmethod
    def _pdf_bytes():
        from pypdf import PdfWriter

        output = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.write(output)
        return output.getvalue()

    def _issue(self, *, sha256, document_type=KycDocument.IDENTITY_DOCUMENT):
        return self.client.post(
            '/api/v1/user-profiles/me/verification/upload-intents/',
            {
                'attempt_id': str(self.attempt.id),
                'document_type': document_type,
                'mime_type': 'image/jpeg',
                'size_bytes': len(self._jpeg_bytes()),
                'sha256': sha256,
                'idempotency_key': f'phase2-intent-{document_type}-0001',
            },
            format='json',
        )

    def test_private_upload_intent_is_opaque_and_idempotent(self):
        import hashlib

        response = self._issue(sha256=hashlib.sha256(self._jpeg_bytes()).hexdigest())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('upload_url', response.data)
        self.assertEqual(response['Cache-Control'], 'no-store, max-age=0')
        self.assertEqual(response['Pragma'], 'no-cache')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertNotIn('opaque_object_key', response.data)
        self.assertNotIn('opaque_storage_key', response.data)
        self.assertNotIn(str(self.user.id), response.data['upload_url'])
        self.assertEqual(
            response.data['required_headers'],
            {
                'Content-Type': 'image/jpeg',
                'Content-Length': str(len(self._jpeg_bytes())),
            },
        )

        intent = KycUploadIntent.objects.get(id=response.data['upload_id'])
        self.assertNotIn(str(self.user.id), intent.opaque_object_key)
        self.assertFalse(hasattr(intent, 'upload_url'))

        replay = self._issue(sha256=hashlib.sha256(self._jpeg_bytes()).hexdigest())
        self.assertEqual(replay.status_code, status.HTTP_200_OK)
        self.assertTrue(replay.data['idempotent_replay'])
        self.assertEqual(replay['Cache-Control'], 'no-store, max-age=0')
        self.assertEqual(replay.data['upload_id'], response.data['upload_id'])

    @override_settings(
        KYC_STORAGE_BACKEND='gcs',
        KYC_STORAGE_BUCKET='kyc-private-test',
        KYC_STORAGE_KMS_KEY='projects/test/keys/kyc',
        PROFILE_MEDIA_PRIVATE_BUCKET='profile-private-test',
        PROFILE_MEDIA_KMS_KEY='projects/test/keys/profile',
        PRIVATE_STORAGE_RUNTIME_SERVICE_ACCOUNT='runtime@test.iam.gserviceaccount.com',
    )
    def test_gcs_upload_signature_binds_declared_content_length(self):
        """The caller must send the exact byte size declared in its intent."""
        signed_url = 'https://uploads.example.test/opaque'
        blob = Mock()
        blob.generate_signed_url.return_value = signed_url
        bucket = Mock()
        bucket.blob.return_value = blob
        expires_at = timezone.now() + timedelta(minutes=30)

        with patch.object(private_object_storage, '_bucket', return_value=bucket):
            result = private_object_storage.issue_upload_url(
                key=private_object_storage.new_key('kyc'),
                content_type='image/jpeg',
                content_length=1234,
                expires_at=expires_at,
            )

        self.assertEqual(result, signed_url)
        blob.generate_signed_url.assert_called_once_with(
            version='v4',
            expiration=expires_at,
            method='PUT',
            content_type='image/jpeg',
            headers={'Content-Length': '1234'},
            query_parameters={'ifGenerationMatch': '0'},
        )

    def test_complete_upload_performs_technical_validation_before_consuming_intent(self):
        import hashlib

        image_bytes = self._jpeg_bytes()
        issued = self._issue(sha256=hashlib.sha256(image_bytes).hexdigest())
        intent = KycUploadIntent.objects.get(id=issued.data['upload_id'])
        private_object_storage.put_bytes(
            scope='kyc',
            key=intent.opaque_object_key,
            data=image_bytes,
            content_type='image/jpeg',
        )

        completed = self.client.post(
            '/api/v1/user-profiles/me/verification/upload-intents/complete/',
            {'upload_id': str(intent.id)},
            format='json',
        )
        self.assertEqual(completed.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(verify_kyc_upload.run(str(intent.id)), 'accepted')
        intent.refresh_from_db()
        document = intent.document
        document.refresh_from_db()
        self.assertEqual(intent.status, KycUploadIntent.CONSUMED)
        self.assertEqual(document.scan_status, KycDocument.ACCEPTED)
        self.assertEqual(document.detected_mime_type, 'image/jpeg')
        self.assertEqual(document.sha256, hashlib.sha256(image_bytes).hexdigest())
        self.assertIsNotNone(document.purge_after)

    def test_medical_pdf_is_parsed_and_technically_accepted(self):
        import hashlib

        pdf_bytes = self._pdf_bytes()
        issued = self.client.post(
            '/api/v1/user-profiles/me/verification/upload-intents/',
            {
                'attempt_id': str(self.attempt.id),
                'document_type': KycDocument.MEDICAL_DOCUMENT,
                'mime_type': 'application/pdf',
                'size_bytes': len(pdf_bytes),
                'sha256': hashlib.sha256(pdf_bytes).hexdigest(),
                'idempotency_key': 'phase2-medical-pdf-0001',
            },
            format='json',
        )
        self.assertEqual(issued.status_code, status.HTTP_201_CREATED)
        intent = KycUploadIntent.objects.get(id=issued.data['upload_id'])
        private_object_storage.put_bytes(
            scope='kyc',
            key=intent.opaque_object_key,
            data=pdf_bytes,
            content_type='application/pdf',
        )
        completed = self.client.post(
            '/api/v1/user-profiles/me/verification/upload-intents/complete/',
            {'upload_id': str(intent.id)},
            format='json',
        )
        self.assertEqual(completed.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(verify_kyc_upload.run(str(intent.id)), 'accepted')
        intent.refresh_from_db()
        self.assertEqual(intent.document.detected_mime_type, 'application/pdf')

    @override_settings(KYC_MAX_PDF_PAGES=1)
    def test_pdf_page_limit_is_enforced_before_technical_acceptance(self):
        from pypdf import PdfWriter

        output = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.add_blank_page(width=72, height=72)
        writer.write(output)

        with self.assertRaises(PrivateObjectIntegrityError):
            validate_document_binary(
                data=output.getvalue(),
                expected_mime_type='application/pdf',
            )

    @override_settings(KYC_MAX_PDF_OBJECTS=1)
    def test_pdf_object_limit_is_enforced_before_technical_acceptance(self):
        from pypdf import PdfWriter

        output = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.write(output)

        with self.assertRaises(PrivateObjectIntegrityError):
            validate_document_binary(
                data=output.getvalue(),
                expected_mime_type='application/pdf',
            )

    def test_invalid_upload_is_quarantined_then_purged_idempotently(self):
        issued = self._issue(sha256='0' * 64)
        intent = KycUploadIntent.objects.get(id=issued.data['upload_id'])
        private_object_storage.put_bytes(
            scope='kyc',
            key=intent.opaque_object_key,
            data=self._jpeg_bytes(),
            content_type='image/jpeg',
        )
        completed = self.client.post(
            '/api/v1/user-profiles/me/verification/upload-intents/complete/',
            {'upload_id': str(intent.id)},
            format='json',
        )
        self.assertEqual(completed.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(verify_kyc_upload.run(str(intent.id)), 'quarantined')
        intent.refresh_from_db()
        document = intent.document
        document.refresh_from_db()
        self.assertEqual(intent.status, KycUploadIntent.EXPIRED)
        self.assertEqual(document.scan_status, KycDocument.QUARANTINED)
        self.assertEqual(document.quarantine_reason_code, 'technical_validation_failed')

        document.purge_after = timezone.now() - timedelta(seconds=1)
        document.save(update_fields=['purge_after'])
        self.assertEqual(purge_kyc_document.run(str(document.id)), 'purged')
        self.assertEqual(purge_kyc_document.run(str(document.id)), 'already_purged')
        document.refresh_from_db()
        self.assertEqual(document.scan_status, KycDocument.PURGED)
        self.assertIsNotNone(document.deletion_verified_at)
        with self.assertRaises(PrivateObjectNotFound):
            private_object_storage.metadata(scope='kyc', key=document.opaque_storage_key)

    def test_expired_intent_is_quarantined_and_queued_for_purge(self):
        import hashlib

        issued = self._issue(sha256=hashlib.sha256(self._jpeg_bytes()).hexdigest())
        intent = KycUploadIntent.objects.get(id=issued.data['upload_id'])
        intent.expires_at = timezone.now() - timedelta(seconds=1)
        intent.save(update_fields=['expires_at'])

        self.assertEqual(expire_kyc_upload_intents.run(), 1)
        intent.refresh_from_db()
        document = intent.document
        document.refresh_from_db()
        self.assertEqual(intent.status, KycUploadIntent.EXPIRED)
        self.assertEqual(document.scan_status, KycDocument.QUARANTINED)
        self.assertEqual(document.quarantine_reason_code, 'upload_expired')
        self.assertLessEqual(document.purge_after, timezone.now())

    def test_due_purge_dispatcher_retries_documents_at_their_next_attempt(self):
        import hashlib

        issued = self._issue(sha256=hashlib.sha256(self._jpeg_bytes()).hexdigest())
        intent = KycUploadIntent.objects.get(id=issued.data['upload_id'])
        document = intent.document
        document.scan_status = KycDocument.QUARANTINED
        document.purge_after = timezone.now() - timedelta(seconds=1)
        document.next_purge_attempt_at = timezone.now() - timedelta(seconds=1)
        document.save(update_fields=['scan_status', 'purge_after', 'next_purge_attempt_at'])

        with patch('profiles.tasks.purge_kyc_document.delay') as dispatched:
            self.assertEqual(purge_due_kyc_documents.run(), 1)
        dispatched.assert_called_once_with(str(document.id))

    def test_verified_kyc_expiry_updates_projection_and_queues_document_purge(self):
        key = private_object_storage.new_key('kyc')
        document = KycDocument.objects.create(
            attempt=self.attempt,
            document_type=KycDocument.IDENTITY_DOCUMENT,
            opaque_storage_key=key,
            scan_status=KycDocument.ACCEPTED,
            purge_after=timezone.now() + timedelta(days=1),
        )
        self.attempt.status = KycAttempt.VERIFIED
        self.attempt.expires_at = timezone.now() - timedelta(seconds=1)
        self.attempt.is_open = True
        self.attempt.save(update_fields=['status', 'expires_at', 'is_open'])

        with patch('profiles.tasks.purge_kyc_document.delay') as dispatched:
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(expire_verified_kyc_attempts.run(), 1)
        self.attempt.refresh_from_db()
        document.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.attempt.status, KycAttempt.EXPIRED)
        self.assertFalse(self.attempt.is_open)
        self.assertEqual(self.user.verification_status, 'expired')
        self.assertLessEqual(document.purge_after, timezone.now())
        self.assertLessEqual(document.next_purge_attempt_at, timezone.now())
        dispatched.assert_called_once_with(str(document.id))
        self.assertTrue(
            self.attempt.audit_events.filter(event_type='kyc_expired').exists()
        )
        self.assertEqual(expire_verified_kyc_attempts.run(), 0)

    def test_account_deletion_cleanup_verifies_kyc_and_profile_object_absence(self):
        kyc_key = private_object_storage.new_key('kyc')
        profile_key = private_object_storage.new_key('profile')
        thumbnail_key = private_object_storage.new_key('profile')
        KycDocument.objects.create(
            attempt=self.attempt,
            document_type=KycDocument.IDENTITY_DOCUMENT,
            opaque_storage_key=kyc_key,
            scan_status=KycDocument.ACCEPTED,
        )
        ProfilePhoto.objects.create(
            profile=self.user.profile,
            photo_url='',
            thumbnail_url='',
            storage_key=profile_key,
            thumbnail_storage_key=thumbnail_key,
            storage_state=ProfilePhoto.PRIVATE,
            is_main=True,
        )
        private_object_storage.put_bytes(
            scope='kyc', key=kyc_key, data=b'evidence', content_type='image/jpeg',
        )
        private_object_storage.put_bytes(
            scope='profile', key=profile_key, data=b'image', content_type='image/jpeg',
        )
        private_object_storage.put_bytes(
            scope='profile', key=thumbnail_key, data=b'thumb', content_type='image/jpeg',
        )

        _delete_private_kyc_objects_for_user(self.user)
        _delete_profile_media_for_user(self.user)

        with self.assertRaises(PrivateObjectNotFound):
            private_object_storage.metadata(scope='kyc', key=kyc_key)
        with self.assertRaises(PrivateObjectNotFound):
            private_object_storage.metadata(scope='profile', key=profile_key)
        with self.assertRaises(PrivateObjectNotFound):
            private_object_storage.metadata(scope='profile', key=thumbnail_key)

    def test_new_profile_photo_uses_private_keys_and_owner_or_kyc_delivery(self):
        uploaded = self.client.post(
            '/api/v1/user-profiles/me/photos/',
            {'file': self._uploaded_image()},
            format='multipart',
        )
        self.assertEqual(uploaded.status_code, status.HTTP_201_CREATED)
        photo = ProfilePhoto.objects.get(id=uploaded.data['photo_id'])
        self.assertEqual(photo.storage_state, ProfilePhoto.PRIVATE)
        self.assertTrue(photo.storage_key)
        self.assertFalse(photo.photo_url)
        media_url = uploaded.data['url']
        self.assertIn('/api/v1/user-profiles/media/photos/', media_url)
        owner_media = self.client.get(media_url)
        self.assertEqual(owner_media.status_code, status.HTTP_200_OK)
        self.assertTrue(owner_media.content.startswith(b'\xff\xd8'))
        self.assertEqual(owner_media['Cache-Control'], 'private, no-store, max-age=0')
        self.assertEqual(owner_media['X-Content-Type-Options'], 'nosniff')

        other = User.objects.create_user(
            email='kyc-phase2-other@example.test',
            password='safe-test-password',
            display_name='Other',
            birth_date=date(1991, 1, 1),
        )
        request = APIRequestFactory().get('/')
        request.user = other
        self.assertIsNone(profile_photo_delivery_url(photo, request))
        self.client.force_authenticate(other)
        denied_media = self.client.get(media_url)
        self.assertEqual(denied_media.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(denied_media.data['error'], 'kyc_required')

        KycAttempt.objects.create(
            user=other,
            status=KycAttempt.VERIFIED,
            is_open=False,
            expires_at=timezone.now() + timedelta(days=1),
        )
        allowed_media = self.client.get(media_url)
        self.assertEqual(allowed_media.status_code, status.HTTP_200_OK)
        self.assertTrue(allowed_media.content.startswith(b'\xff\xd8'))
        KycAttempt.objects.filter(user=other).update(
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        expired_media = self.client.get(media_url)
        self.assertEqual(expired_media.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(expired_media.data['error'], 'kyc_required')

        raw_legacy_write = ProfilePhoto.objects.create(
            profile=self.user.profile,
            photo_url='profiles/untrusted/direct-write.jpg',
            thumbnail_url='profiles/untrusted/direct-write-thumb.jpg',
            is_main=False,
        )
        request.user = self.user
        self.assertIsNone(profile_photo_delivery_url(raw_legacy_write, request))
        self.client.force_authenticate(self.user)
        raw_media = self.client.get(
            f'/api/v1/user-profiles/media/photos/{raw_legacy_write.id}/main/'
        )
        self.assertEqual(raw_media.status_code, status.HTTP_404_NOT_FOUND)

    def _uploaded_image(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile('profile.jpg', self._jpeg_bytes(), content_type='image/jpeg')

    def test_legacy_photo_migration_switches_only_after_verified_copy_and_delete(self):
        legacy_prefix = f'profiles/{self.user.id}/legacy'
        photo = ProfilePhoto.objects.create(
            profile=self.user.profile,
            photo_url=f'{legacy_prefix}/main.jpg',
            thumbnail_url=f'{legacy_prefix}/thumb.jpg',
            is_main=True,
            legacy_source_verified=True,
        )
        image_bytes = self._jpeg_bytes()
        with patch(
            'profiles.private_storage.download_legacy_profile_object',
            side_effect=[image_bytes, image_bytes],
        ), patch(
            'profiles.private_storage.delete_legacy_profile_object',
            return_value=True,
        ):
            result = migrate_legacy_profile_photo.run(str(photo.id))
        self.assertEqual(result, 'migrated')
        photo.refresh_from_db()
        self.assertEqual(photo.storage_state, ProfilePhoto.PRIVATE)
        self.assertTrue(photo.storage_key)
        self.assertFalse(photo.photo_url)
        self.assertIsNotNone(photo.legacy_deleted_at)

    def test_legacy_photo_migration_fails_closed_when_source_is_missing(self):
        legacy_prefix = f'profiles/{self.user.id}/legacy'
        photo = ProfilePhoto.objects.create(
            profile=self.user.profile,
            photo_url=f'{legacy_prefix}/missing-main.jpg',
            thumbnail_url=f'{legacy_prefix}/missing-thumb.jpg',
            is_main=True,
            legacy_source_verified=True,
        )
        with patch(
            'profiles.private_storage.download_legacy_profile_object',
            side_effect=PrivateObjectNotFound(),
        ):
            result = migrate_legacy_profile_photo.run(str(photo.id))
        self.assertEqual(result, 'source_or_copy_missing')
        photo.refresh_from_db()
        self.assertEqual(photo.storage_state, ProfilePhoto.MIGRATION_FAILED)

    def test_partial_copy_with_unverified_compensation_retains_cleanup_handles(self):
        legacy_prefix = f'profiles/{self.user.id}/legacy'
        photo = ProfilePhoto.objects.create(
            profile=self.user.profile,
            photo_url=f'{legacy_prefix}/main.jpg',
            thumbnail_url=f'{legacy_prefix}/thumb.jpg',
            is_main=True,
            legacy_source_verified=True,
        )
        image_bytes = self._jpeg_bytes()
        with patch(
            'profiles.private_storage.download_legacy_profile_object',
            side_effect=[image_bytes, image_bytes],
        ), patch(
            'profiles.private_storage.private_object_storage.put_bytes',
            side_effect=[None, PrivateStorageUnavailable()],
        ), patch(
            'profiles.private_storage.private_object_storage.delete',
            return_value=False,
        ):
            result = migrate_legacy_profile_photo.run(str(photo.id))
        self.assertEqual(result, 'private_cleanup_unverified')
        photo.refresh_from_db()
        self.assertEqual(photo.storage_state, ProfilePhoto.MIGRATION_FAILED)
        self.assertTrue(photo.storage_key)
        self.assertTrue(photo.thumbnail_storage_key)

    def test_account_cleanup_does_not_ignore_a_verified_legacy_delete_failure(self):
        legacy_prefix = f'profiles/{self.user.id}/legacy'
        photo = ProfilePhoto.objects.create(
            profile=self.user.profile,
            photo_url=f'{legacy_prefix}/delete-main.jpg',
            thumbnail_url=f'{legacy_prefix}/delete-thumb.jpg',
            is_main=True,
            legacy_source_verified=True,
        )
        with patch(
            'profiles.photo_storage.delete_legacy_profile_object',
            return_value=False,
        ):
            with self.assertRaises(ProfilePhotoStorageUnavailable):
                profile_photo_storage.delete_photo(photo)

    def test_unverified_raw_reference_is_never_a_legacy_delete_target(self):
        with patch('profiles.photo_storage.delete_legacy_profile_object') as deleted:
            _delete_photo_references({
                'photo_url': 'profiles/untrusted/raw-main.jpg',
                'thumbnail_url': 'profiles/untrusted/raw-thumb.jpg',
                'legacy_source_verified': False,
            })
        deleted.assert_not_called()

    def test_legacy_cutover_requires_complete_owner_bound_pair(self):
        cutover = import_module('profiles.migrations.0013_phase2_legacy_photo_cutover')
        owned_prefix = f'profiles/{self.user.id}/legacy'
        trusted = ProfilePhoto.objects.create(
            profile=self.user.profile,
            photo_url=f'{owned_prefix}/main.jpg',
            thumbnail_url=f'{owned_prefix}/thumb.jpg',
        )
        cross_owner = ProfilePhoto.objects.create(
            profile=self.user.profile,
            photo_url='profiles/00000000-0000-0000-0000-000000000002/main.jpg',
            thumbnail_url='profiles/00000000-0000-0000-0000-000000000002/thumb.jpg',
        )
        incomplete = ProfilePhoto.objects.create(
            profile=self.user.profile,
            photo_url=f'{owned_prefix}/only-main.jpg',
            thumbnail_url='',
        )
        cutover.mark_preexisting_legacy_sources(
            SimpleNamespace(get_model=lambda app_label, model_name: ProfilePhoto),
            None,
        )
        trusted.refresh_from_db()
        cross_owner.refresh_from_db()
        incomplete.refresh_from_db()
        self.assertTrue(trusted.legacy_source_verified)
        self.assertFalse(cross_owner.legacy_source_verified)
        self.assertFalse(incomplete.legacy_source_verified)

    def test_verified_cross_owner_legacy_reference_is_never_touched(self):
        photo = ProfilePhoto.objects.create(
            profile=self.user.profile,
            photo_url='profiles/00000000-0000-0000-0000-000000000002/main.jpg',
            thumbnail_url='profiles/00000000-0000-0000-0000-000000000002/thumb.jpg',
            is_main=True,
            legacy_source_verified=True,
        )
        with patch('profiles.private_storage.download_legacy_profile_object') as downloaded, patch(
            'profiles.private_storage.delete_legacy_profile_object',
        ) as deleted:
            result = migrate_legacy_profile_photo.run(str(photo.id))
        self.assertEqual(result, 'unsupported_legacy_reference')
        downloaded.assert_not_called()
        deleted.assert_not_called()
        photo.refresh_from_db()
        self.assertEqual(photo.storage_state, ProfilePhoto.MIGRATION_FAILED)

    @override_settings(
        KYC_STORAGE_BACKEND='gcs',
        PRIVATE_STORAGE_RUNTIME_SERVICE_ACCOUNT='runtime@example.iam.gserviceaccount.com',
    )
    def test_bucket_gate_requires_public_access_prevention(self):
        bucket = SimpleNamespace(
            iam_configuration=SimpleNamespace(
                uniform_bucket_level_access_enabled=True,
                public_access_prevention='inherited',
            ),
            default_kms_key_name='projects/test/locations/test/keyRings/test/cryptoKeys/test',
            cors=[{
                'origin': ['https://app.example.test'],
                'method': ['PUT'],
                'responseHeader': ['Content-Type', 'X-Goog-Meta-Unapproved'],
            }],
        )
        bucket.reload = lambda: None
        bucket.get_iam_policy = lambda **_: SimpleNamespace(bindings=[{
            'role': 'roles/storage.objectAdmin',
            'members': ['serviceAccount:runtime@example.iam.gserviceaccount.com'],
        }])
        with patch.object(private_object_storage, '_bucket', return_value=bucket):
            errors = private_object_storage.verify_bucket_policy('kyc')
        self.assertIn('public_access_prevention_not_enforced', errors)
        self.assertIn('cors_excessive_response_header', errors)
        self.assertNotIn('runtime_object_admin_missing', errors)

    @override_settings(
        KYC_STORAGE_BACKEND='gcs',
        PRIVATE_STORAGE_RUNTIME_SERVICE_ACCOUNT='runtime@example.iam.gserviceaccount.com',
    )
    def test_bucket_gate_requires_expected_runtime_object_admin_member(self):
        bucket = SimpleNamespace(
            iam_configuration=SimpleNamespace(
                uniform_bucket_level_access_enabled=True,
                public_access_prevention='enforced',
            ),
            default_kms_key_name='projects/test/locations/test/keyRings/test/cryptoKeys/test',
            cors=[{
                'origin': ['https://app.example.test'],
                'method': ['PUT'],
                'responseHeader': ['Content-Type', 'x-goog-generation'],
            }],
        )
        bucket.reload = lambda: None
        bucket.get_iam_policy = lambda **_: SimpleNamespace(bindings=[])
        with patch.object(private_object_storage, '_bucket', return_value=bucket):
            errors = private_object_storage.verify_bucket_policy('kyc')
        self.assertIn('runtime_object_admin_missing', errors)

    @override_settings(
        KYC_STORAGE_BACKEND='gcs',
        PRIVATE_STORAGE_RUNTIME_SERVICE_ACCOUNT='runtime@example.iam.gserviceaccount.com',
    )
    def test_bucket_gate_rejects_an_additional_object_access_principal(self):
        bucket = SimpleNamespace(
            iam_configuration=SimpleNamespace(
                uniform_bucket_level_access_enabled=True,
                public_access_prevention='enforced',
            ),
            default_kms_key_name='projects/test/locations/test/keyRings/test/cryptoKeys/test',
            cors=[{
                'origin': ['https://app.example.test'],
                'method': ['PUT'],
                'responseHeader': ['Content-Type', 'x-goog-generation'],
            }],
        )
        bucket.reload = lambda: None
        bucket.get_iam_policy = lambda **_: SimpleNamespace(bindings=[
            {
                'role': 'roles/storage.objectAdmin',
                'members': ['serviceAccount:runtime@example.iam.gserviceaccount.com'],
            },
            {
                'role': 'roles/storage.objectViewer',
                'members': ['serviceAccount:unexpected@example.iam.gserviceaccount.com'],
            },
        ])
        with patch.object(private_object_storage, '_bucket', return_value=bucket):
            errors = private_object_storage.verify_bucket_policy('kyc')
        self.assertIn('unexpected_object_access_binding', errors)

        bucket.get_iam_policy = lambda **_: SimpleNamespace(bindings=[
            {
                'role': 'roles/storage.objectAdmin',
                'members': ['serviceAccount:runtime@example.iam.gserviceaccount.com'],
            },
            {
                'role': 'roles/viewer',
                'members': ['user:unexpected@example.test'],
            },
        ])
        with patch.object(private_object_storage, '_bucket', return_value=bucket):
            errors = private_object_storage.verify_bucket_policy('kyc')
        self.assertIn('unexpected_object_access_binding', errors)

    @override_settings(KYC_STORAGE_BACKEND='gcs', PRIVATE_STORAGE_RUNTIME_SERVICE_ACCOUNT='')
    def test_gcs_storage_configuration_requires_runtime_service_account(self):
        self.assertIn(
            'runtime_service_account_missing',
            private_storage_configuration_errors('kyc'),
        )

    def test_private_storage_command_accepts_only_the_isolated_memory_backend(self):
        call_command('verify_private_storage', '--scope', 'all')

    def test_private_storage_rejects_cross_scope_or_non_opaque_keys(self):
        with self.assertRaises(PrivateObjectIntegrityError):
            private_object_storage.put_bytes(
                scope='profile',
                key=private_object_storage.new_key('kyc'),
                data=b'image',
                content_type='image/jpeg',
            )
        with self.assertRaises(PrivateObjectIntegrityError):
            private_object_storage.metadata(
                scope='kyc',
                key='kyc/quarantine/not-an-opaque-token',
            )

        malformed = ProfilePhoto.objects.create(
            profile=self.user.profile,
            storage_key='profile-media/private/not-an-opaque-token',
            storage_state=ProfilePhoto.PRIVATE,
        )
        response = self.client.get(
            f'/api/v1/user-profiles/media/photos/{malformed.id}/main/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_legacy_storage_adapter_rejects_kyc_and_profile_media_paths(self):
        manager = object.__new__(StorageManager)
        for path in ('kyc/quarantine/opaque', 'profiles/legacy/photo.jpg'):
            with self.assertRaisesRegex(ValueError, 'private_media_requires_private_adapter'):
                manager.generate_signed_url(file_path=path)

    def test_development_static_handler_refuses_direct_kyc_media_path(self):
        """A development server must not make a local KYC path reachable."""
        response = self.client.get('/media/kyc/opaque-document')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_exports_and_request_messages_do_not_contain_full_email(self):
        """KYC privacy policy applies to exports and pending-state messages."""
        payload = _build_export_payload(self.user, self.user.profile)
        self.assertNotIn('email', payload['user'])
        self.assertTrue(payload['user']['email_present'])
        self.assertNotIn(self.user.email, str(payload))

        export = DataExportRequest.objects.create(user=self.user)
        deletion = AccountDeletionRequest.objects.create(user=self.user)
        for request_obj, action_type in (
            (export, 'data_export'),
            (deletion, 'account_deletion'),
        ):
            response = _serialize_data_request(request_obj, action_type)
            self.assertNotIn(self.user.email, response['message'])

    def test_production_runtime_requires_written_legal_kyc_gate(self):
        """Production cannot silently activate mandatory KYC permissions."""
        with self.assertRaises(ImproperlyConfigured):
            validate_kyc_runtime_gate(
                deployment_environment='production',
                enforcement_mode='disabled',
                legal_approval=True,
                legal_approval_reference='LEGAL-2026-001',
            )
        with self.assertRaises(ImproperlyConfigured):
            validate_kyc_runtime_gate(
                deployment_environment='production',
                enforcement_mode='enforced',
                legal_approval=False,
                legal_approval_reference='',
            )
        validate_kyc_runtime_gate(
            deployment_environment='preproduction',
            enforcement_mode='preproduction',
            legal_approval=False,
            legal_approval_reference='',
        )
        validate_kyc_runtime_gate(
            deployment_environment='production',
            enforcement_mode='enforced',
            legal_approval=True,
            legal_approval_reference='LEGAL-2026-001',
        )

    def test_production_runtime_requires_complete_private_storage_configuration(self):
        """A legal flag alone cannot start a non-private KYC deployment."""
        valid = {
            'deployment_environment': 'production',
            'kyc_storage_backend': 'gcs',
            'profile_media_storage_backend': 'gcs',
            'kyc_bucket': 'kyc-private-test',
            'profile_media_bucket': 'profile-media-private-test',
            'kyc_kms_key': 'projects/test/keys/kyc',
            'profile_media_kms_key': 'projects/test/keys/profile-media',
            'runtime_service_account': 'runtime@test.iam.gserviceaccount.com',
            'kyc_document_retention_days': 90,
            'antivirus_backend': 'clamav-cli',
            'kyc_storage_upload_ttl_seconds': 1800,
            'kyc_quarantine_retention_hours': 24,
            'kyc_scan_timeout_seconds': 30,
            'kyc_max_image_pixels': 24_000_000,
            'kyc_max_pdf_pages': 25,
            'kyc_max_pdf_objects': 5_000,
            'profile_media_max_upload_bytes': 5 * 1024 * 1024,
            'profile_media_max_image_pixels': 25_000_000,
            'kyc_clamav_binary': 'clamscan',
        }
        validate_private_storage_runtime_gate(**valid)

        for field, invalid_value in (
            ('kyc_storage_backend', 'memory'),
            ('profile_media_storage_backend', 'firebase'),
            ('kyc_bucket', ''),
            ('profile_media_bucket', ''),
            ('kyc_kms_key', ''),
            ('profile_media_kms_key', ''),
            ('runtime_service_account', ''),
            ('kyc_document_retention_days', 0),
            ('kyc_storage_upload_ttl_seconds', 0),
            ('kyc_quarantine_retention_hours', 0),
            ('kyc_scan_timeout_seconds', 0),
            ('kyc_max_image_pixels', 0),
            ('kyc_max_pdf_pages', 0),
            ('kyc_max_pdf_objects', 0),
            ('profile_media_max_upload_bytes', 0),
            ('profile_media_max_image_pixels', 0),
            ('antivirus_backend', 'disabled'),
            ('kyc_clamav_binary', ''),
        ):
            with self.subTest(field=field), self.assertRaises(ImproperlyConfigured):
                validate_private_storage_runtime_gate(
                    **{**valid, field: invalid_value}
                )

        for field, duplicate_value in (
            ('profile_media_bucket', valid['kyc_bucket']),
            ('profile_media_kms_key', valid['kyc_kms_key']),
        ):
            with self.subTest(field=field), self.assertRaises(ImproperlyConfigured):
                validate_private_storage_runtime_gate(
                    **{**valid, field: duplicate_value}
                )
