"""
Celery tasks for GDPR-related profile operations.

- generate_data_export: prepares a JSON archive of the user's personal data,
  stores it temporarily, and sends a signed download link via email.
- process_account_deletion: hard-deletes the user's account after the grace
  period has expired and the request has not been cancelled.
"""

import json
import hashlib
import logging
import os
from datetime import timedelta
from io import StringIO

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.db.models import Q

from profiles.models import DataExportRequest, AccountDeletionRequest

logger = logging.getLogger(__name__)

User = get_user_model()


def _build_export_payload(user, profile):
    """Serialize the personal data we want to expose to the user."""
    data = {
        'user': {
            'id': str(user.id),
            # KYC policy excludes full email addresses from every generated
            # export. The client already owns its account contact channel, so
            # an existence flag is sufficient for this non-KYC archive.
            'email_present': bool(user.email),
            'display_name': getattr(user, 'display_name', None),
            'birth_date': user.birth_date.isoformat() if user.birth_date else None,
            'phone_number': user.phone_number,
            'email_verified': user.email_verified,
            'is_verified': user.is_verified,
            'verification_status': user.verification_status,
            'is_premium': user.is_premium,
            'premium_until': (
                user.premium_until.isoformat() if user.premium_until else None
            ),
            'notification_settings': user.notification_settings,
            'date_joined': user.date_joined.isoformat() if user.date_joined else None,
            'last_login': user.last_login.isoformat() if user.last_login else None,
        },
        'profile': _serialize_profile(profile) if profile else None,
        'generated_at': timezone.now().isoformat(),
        'schema_version': '1.0',
    }
    return data


def _serialize_profile(profile):
    """Serialize the fields exposed by the current Profile schema."""
    return {
        'gender': profile.gender,
        'bio': profile.bio,
        'city': profile.city,
        'country': profile.country,
        'latitude': str(profile.latitude) if profile.latitude is not None else None,
        'longitude': str(profile.longitude) if profile.longitude is not None else None,
        'preferred_currency': profile.preferred_currency,
        'hide_exact_location': profile.hide_exact_location,
        'interests': list(profile.interests or []),
        'relationship_types_sought': list(profile.relationship_types_sought or []),
        'age_min_preference': profile.age_min_preference,
        'age_max_preference': profile.age_max_preference,
        'distance_max_km': profile.distance_max_km,
        'genders_sought': list(profile.genders_sought or []),
        'verified_only': profile.verified_only,
        'online_only': profile.online_only,
        'is_hidden': profile.is_hidden,
        'show_online_status': profile.show_online_status,
        'allow_profile_in_discovery': profile.allow_profile_in_discovery,
    }


@shared_task(bind=True, max_retries=3)
def generate_data_export(self, request_id: str):
    """
    Generate a JSON export of the user's data, upload it to temporary storage,
    and email the signed download URL.
    """
    try:
        request_obj = DataExportRequest.objects.select_related('user').get(id=request_id)
    except DataExportRequest.DoesNotExist:
        logger.error(f"DataExportRequest {request_id} not found")
        return

    if request_obj.status not in (DataExportRequest.STATUS_PENDING, DataExportRequest.STATUS_PROCESSING):
        logger.warning(f"Skipping export {request_id}: status is {request_obj.status}")
        return

    request_obj.status = DataExportRequest.STATUS_PROCESSING
    request_obj.save(update_fields=['status'])

    try:
        user = request_obj.user
        profile = getattr(user, 'profile', None)
        payload = _build_export_payload(user, profile)

        json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
        filename = f"export_{user.id}_{request_obj.id}.json"

        # Default: local temporary storage via Django default_storage.
        from django.core.files.storage import default_storage
        path = default_storage.save(
            os.path.join('exports', filename),
            ContentFile(json_bytes),
        )
        url = default_storage.url(path)

        # If Firebase / signed URL storage is configured, prefer its signed URL.
        # The helper below follows the same convention used for media uploads.
        try:
            from firebase_storage.utils import generate_signed_url
            signed_url = generate_signed_url(path, expiration_hours=72)
            if signed_url:
                url = signed_url
        except Exception:  # noqa: BLE001
            # Signed URL/provider details are sensitive operational values.
            logger.warning("Could not generate export signed URL")

        request_obj.download_url = url
        request_obj.status = DataExportRequest.STATUS_READY
        request_obj.completed_at = timezone.now()
        request_obj.expires_at = timezone.now() + timedelta(hours=72)
        request_obj.save(update_fields=['download_url', 'status', 'completed_at', 'expires_at'])

        # TODO: send email via the notification service once it is available.
        # For now, the frontend polls / displays the request status.
        logger.info(f"Export {request_id} ready for user {user.id}")

    except Exception as exc:  # noqa: BLE001
        logger.error("Export generation failed")
        request_obj.status = DataExportRequest.STATUS_FAILED
        request_obj.error_log = 'export_generation_failed'
        request_obj.save(update_fields=['status', 'error_log'])
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, max_retries=2)
def process_account_deletion(self, request_id: str):
    """
    Hard-delete a user account after the grace period has passed and the
    deletion request is still confirmed/cancelled.
    """
    try:
        request_obj = AccountDeletionRequest.objects.select_related('user').get(id=request_id)
    except AccountDeletionRequest.DoesNotExist:
        logger.error(f"AccountDeletionRequest {request_id} not found")
        return

    if request_obj.status == AccountDeletionRequest.STATUS_CANCELLED:
        logger.info(f"Deletion {request_id} was cancelled, aborting")
        return

    if request_obj.status != AccountDeletionRequest.STATUS_CONFIRMED:
        logger.warning(f"Skipping deletion {request_id}: status is {request_obj.status}")
        return

    grace_deadline = request_obj.confirmed_at + timedelta(hours=request_obj.grace_period_hours)
    if timezone.now() < grace_deadline:
        # Reschedule for the end of the grace period.
        delay = (grace_deadline - timezone.now()).total_seconds()
        logger.info(f"Grace period not over for {request_id}, rescheduling in {delay:.0f}s")
        raise self.retry(countdown=max(delay, 1))

    try:
        user = request_obj.user
        request_obj.status = AccountDeletionRequest.STATUS_PROCESSING
        request_obj.save(update_fields=['status'])

        # Rows cascade on account deletion, but private object stores do not.
        # Verify object deletion before removing the only database purge handles.
        _delete_private_kyc_objects_for_user(user)
        _delete_profile_media_for_user(user)

        # Anonymize/delete related data.  Custom logic can be expanded here.
        _cleanup_user_data(user)

        user_id = user.id
        user.delete()

        request_obj.status = AccountDeletionRequest.STATUS_COMPLETED
        request_obj.completed_at = timezone.now()
        request_obj.save(update_fields=['status', 'completed_at'])

        logger.info(f"Account {user_id} deleted via request {request_id}")

    except Exception as exc:  # noqa: BLE001
        logger.error("Account deletion failed")
        request_obj.status = AccountDeletionRequest.STATUS_CONFIRMED
        request_obj.save(update_fields=['status'])
        raise self.retry(exc=exc, countdown=300)


def _cleanup_user_data(user):
    """
    Remove or anonymize user-related records before account deletion.
    Profile and related model instances use CASCADE, so deleting the User is
    sufficient for most rows; explicit cleanup is added for records that do not
    cascade automatically (conversations, messages, etc.).
    """
    try:
        from messaging.models import Conversation, Message
        Message.objects.filter(sender=user).update(sender=None)
        Conversation.objects.filter(participants=user).delete()
    except Exception:  # noqa: BLE001
        logger.warning("Could not clean messaging data during account deletion")


def _delete_private_kyc_objects_for_user(user):
    """Verify removal of every KYC object before its database rows cascade."""
    from profiles.models import KycDocument
    from profiles.private_storage import private_object_storage

    keys = list(
        KycDocument.objects.filter(attempt__user=user)
        .exclude(scan_status=KycDocument.PURGED)
        .values_list('opaque_storage_key', flat=True)
    )
    for key in keys:
        # ``delete`` verifies absence and deliberately exposes no object detail
        # through its exception or logs.
        if not private_object_storage.delete(scope='kyc', key=key):
            raise RuntimeError('KYC private object deletion was not verified')


def _delete_profile_media_for_user(user):
    """Remove profile-media objects before ProfilePhoto rows cascade."""
    from profiles.models import ProfilePhoto
    from profiles.photo_storage import profile_photo_storage

    for photo in ProfilePhoto.objects.filter(profile__user=user).iterator():
        profile_photo_storage.delete_photo(photo)


# ---------------------------------------------------------------------------
# Private KYC storage lifecycle.  Task arguments are opaque database UUIDs;
# object keys, documents and medical data are never logged or sent to Celery.
# ---------------------------------------------------------------------------


def _quarantine_kyc_document(*, document_id, reason_code, now):
    from profiles.models import KycDocument, KycUploadIntent

    with transaction.atomic():
        document = KycDocument.objects.select_for_update().get(id=document_id)
        if document.scan_status in {KycDocument.ACCEPTED, KycDocument.PURGED}:
            return
        document.scan_status = KycDocument.QUARANTINED
        document.quarantine_reason_code = reason_code
        document.scan_completed_at = now
        document.purge_after = now + timedelta(
            hours=settings.KYC_QUARANTINE_RETENTION_HOURS,
        )
        document.next_purge_attempt_at = now
        document.save(update_fields=[
            'scan_status',
            'quarantine_reason_code',
            'scan_completed_at',
            'purge_after',
            'next_purge_attempt_at',
            'updated_at',
        ])
        KycUploadIntent.objects.filter(
            document=document,
            status=KycUploadIntent.ISSUED,
        ).update(status=KycUploadIntent.EXPIRED)


@shared_task(bind=True, max_retries=5, default_retry_delay=30)
def verify_kyc_upload(self, upload_id: str):
    """Verify one direct upload before it can be used by KYC submission."""
    from profiles.kyc import _safe_audit_event, _transition_attempt_for_documents
    from profiles.models import KycDocument, KycUploadIntent
    from profiles.private_storage import (
        PrivateObjectIntegrityError,
        PrivateObjectMalwareDetected,
        PrivateObjectNotFound,
        PrivateStorageUnavailable,
        canonical_mime_type,
        private_object_storage,
        scan_antivirus,
        validate_document_binary,
    )

    now = timezone.now()
    with transaction.atomic():
        intent = (
            KycUploadIntent.objects.select_for_update()
            .select_related('attempt')
            .filter(id=upload_id)
            .first()
        )
        if intent is None or intent.document_id is None:
            return 'missing'
        document = KycDocument.objects.select_for_update().filter(id=intent.document_id).first()
        if document is None:
            return 'missing'
        if intent.status == KycUploadIntent.CONSUMED and document.scan_status == KycDocument.ACCEPTED:
            return 'accepted'
        if intent.status != KycUploadIntent.ISSUED or not intent.upload_confirmed_at:
            return 'not_ready'
        if intent.expires_at <= now:
            document_id = document.id
        else:
            document_id = None
            document.scan_status = KycDocument.SCANNING
            document.scan_attempts += 1
            document.scan_started_at = now
            document.save(update_fields=[
                'scan_status', 'scan_attempts', 'scan_started_at', 'updated_at',
            ])

    if document_id is not None:
        _quarantine_kyc_document(
            document_id=document_id,
            reason_code='upload_expired',
            now=now,
        )
        return 'expired'

    try:
        metadata = private_object_storage.metadata(
            scope='kyc', key=intent.opaque_object_key,
        )
        if metadata.size_bytes != intent.declared_size_bytes:
            raise PrivateObjectIntegrityError()
        if canonical_mime_type(metadata.content_type) != canonical_mime_type(intent.declared_mime_type):
            raise PrivateObjectIntegrityError()
        data = private_object_storage.download(scope='kyc', key=intent.opaque_object_key)
        if len(data) != intent.declared_size_bytes:
            raise PrivateObjectIntegrityError()
        if hashlib.sha256(data).hexdigest() != intent.declared_sha256.lower():
            raise PrivateObjectIntegrityError()
        detected_mime_type = validate_document_binary(
            data=data,
            expected_mime_type=intent.declared_mime_type,
        )
        scan_antivirus(data)
    except PrivateStorageUnavailable:
        raise self.retry(
            countdown=min(300, 30 * (2 ** self.request.retries)),
        ) from None
    except PrivateObjectNotFound:
        _quarantine_kyc_document(
            document_id=document_id or intent.document_id,
            reason_code='object_missing',
            now=timezone.now(),
        )
        return 'quarantined'
    except PrivateObjectMalwareDetected:
        _quarantine_kyc_document(
            document_id=document_id or intent.document_id,
            reason_code='malware_detected',
            now=timezone.now(),
        )
        return 'quarantined'
    except PrivateObjectIntegrityError:
        _quarantine_kyc_document(
            document_id=document_id or intent.document_id,
            reason_code='technical_validation_failed',
            now=timezone.now(),
        )
        return 'quarantined'

    completed_at = timezone.now()
    with transaction.atomic():
        intent = (
            KycUploadIntent.objects.select_for_update()
            .select_related('attempt')
            .get(id=upload_id)
        )
        document = KycDocument.objects.select_for_update().get(id=intent.document_id)
        if intent.status == KycUploadIntent.CONSUMED and document.scan_status == KycDocument.ACCEPTED:
            return 'accepted'
        if intent.status != KycUploadIntent.ISSUED or intent.expires_at <= completed_at:
            return 'stale'
        document.sha256 = intent.declared_sha256.lower()
        document.size_bytes = metadata.size_bytes
        document.detected_mime_type = detected_mime_type
        document.scan_status = KycDocument.ACCEPTED
        document.scan_completed_at = completed_at
        document.quarantine_reason_code = ''
        document.purge_after = completed_at + timedelta(days=settings.KYC_DOCUMENT_RETENTION_DAYS)
        document.next_purge_attempt_at = None
        document.save(update_fields=[
            'sha256', 'size_bytes', 'detected_mime_type', 'scan_status',
            'scan_completed_at', 'quarantine_reason_code', 'purge_after',
            'next_purge_attempt_at', 'updated_at',
        ])
        intent.status = KycUploadIntent.CONSUMED
        intent.used_at = completed_at
        intent.save(update_fields=['status', 'used_at'])
        _transition_attempt_for_documents(intent.attempt)
        _safe_audit_event(
            attempt=intent.attempt,
            actor=None,
            event_type='upload_technically_accepted',
            metadata={
                'document_type': document.document_type,
                'scan_status': document.scan_status,
            },
        )
    logger.info('KYC upload technically accepted')
    return 'accepted'


@shared_task(bind=True, max_retries=8, default_retry_delay=60)
def purge_kyc_document(self, document_id: str):
    """Delete one private object, then persist a verified purge marker."""
    from profiles.models import KycDocument
    from profiles.private_storage import PrivateStorageUnavailable, private_object_storage

    now = timezone.now()
    with transaction.atomic():
        document = KycDocument.objects.select_for_update().filter(id=document_id).first()
        if document is None or document.scan_status == KycDocument.PURGED:
            return 'already_purged'
        if document.purge_after and document.purge_after > now:
            return 'not_due'
        key = document.opaque_storage_key
        document.purge_attempts += 1
        document.next_purge_attempt_at = now + timedelta(minutes=5)
        document.save(update_fields=['purge_attempts', 'next_purge_attempt_at', 'updated_at'])

    try:
        deleted = private_object_storage.delete(scope='kyc', key=key)
    except PrivateStorageUnavailable:
        raise self.retry(
            countdown=min(3600, 60 * (2 ** self.request.retries)),
        ) from None
    if not deleted:
        raise self.retry(countdown=min(3600, 60 * (2 ** self.request.retries)))

    with transaction.atomic():
        document = KycDocument.objects.select_for_update().filter(id=document_id).first()
        if document is None:
            return 'deleted_with_row_removed'
        document.scan_status = KycDocument.PURGED
        document.purged_at = timezone.now()
        document.deletion_verified_at = document.purged_at
        document.next_purge_attempt_at = None
        document.save(update_fields=[
            'scan_status', 'purged_at', 'deletion_verified_at',
            'next_purge_attempt_at', 'updated_at',
        ])
    logger.info('KYC private object purge verified')
    return 'purged'


@shared_task
def expire_kyc_upload_intents(batch_size=100):
    """Expire abandoned upload declarations and schedule their private cleanup."""
    from profiles.models import KycDocument, KycUploadIntent

    now = timezone.now()
    intent_ids = list(
        KycUploadIntent.objects.filter(
            status=KycUploadIntent.ISSUED,
            expires_at__lte=now,
        ).values_list('id', flat=True)[:batch_size]
    )
    scheduled = 0
    for intent_id in intent_ids:
        with transaction.atomic():
            intent = (
                KycUploadIntent.objects.select_for_update()
                .filter(id=intent_id, status=KycUploadIntent.ISSUED)
                .first()
            )
            if intent is None or intent.expires_at > now:
                continue
            intent.status = KycUploadIntent.EXPIRED
            intent.save(update_fields=['status'])
            document = None
            if intent.document_id:
                document = KycDocument.objects.select_for_update().filter(id=intent.document_id).first()
            if document is not None and document.scan_status != KycDocument.PURGED:
                document.scan_status = KycDocument.QUARANTINED
                document.quarantine_reason_code = 'upload_expired'
                document.purge_after = now
                document.next_purge_attempt_at = now
                document.save(update_fields=[
                    'scan_status', 'quarantine_reason_code', 'purge_after',
                    'next_purge_attempt_at', 'updated_at',
                ])
                transaction.on_commit(lambda doc_id=str(document.id): purge_kyc_document.delay(doc_id))
                scheduled += 1
    return scheduled


@shared_task
def purge_due_kyc_documents(batch_size=100):
    """Dispatch idempotent purge jobs for due documents in bounded batches."""
    from profiles.models import KycDocument

    now = timezone.now()
    document_ids = list(
        KycDocument.objects.filter(
            purge_after__lte=now,
            scan_status__in=[
                KycDocument.ISSUED,
                KycDocument.UPLOADED,
                KycDocument.SCANNING,
                KycDocument.QUARANTINED,
                KycDocument.ACCEPTED,
            ],
        ).filter(
            Q(next_purge_attempt_at__isnull=True) | Q(next_purge_attempt_at__lte=now),
        ).values_list('id', flat=True)[:batch_size]
    )
    for document_id in document_ids:
        purge_kyc_document.delay(str(document_id))
    return len(document_ids)


@shared_task
def expire_verified_kyc_attempts(batch_size=100):
    """Persist KYC expiry and schedule verified deletion of its raw evidence.

    ``has_active_kyc`` already fails closed on ``expires_at`` at request time.
    This bounded task makes that loss of right observable in the authoritative
    attempt/projection too, frees the one-open-attempt slot for re-verification
    and starts the legally configured purge workflow without logging evidence.
    """
    from profiles.kyc import _safe_audit_event, sync_legacy_verification_projection
    from profiles.models import KycAttempt, KycDocument

    now = timezone.now()
    attempt_ids = list(
        KycAttempt.objects.filter(
            status=KycAttempt.VERIFIED,
            expires_at__lte=now,
        ).values_list('id', flat=True)[:batch_size]
    )
    expired = 0
    for attempt_id in attempt_ids:
        with transaction.atomic():
            attempt = (
                KycAttempt.objects.select_for_update()
                .filter(
                    id=attempt_id,
                    status=KycAttempt.VERIFIED,
                    expires_at__lte=now,
                )
                .first()
            )
            if attempt is None:
                continue
            attempt.status = KycAttempt.EXPIRED
            attempt.is_open = False
            attempt.save(update_fields=['status', 'is_open', 'updated_at'])
            sync_legacy_verification_projection(attempt, now)
            _safe_audit_event(
                attempt=attempt,
                actor=None,
                event_type='kyc_expired',
                metadata={'status': attempt.status},
            )

            document_ids = list(
                KycDocument.objects.select_for_update().filter(
                    attempt=attempt,
                ).exclude(
                    scan_status=KycDocument.PURGED,
                ).values_list('id', flat=True)
            )
            if document_ids:
                KycDocument.objects.filter(id__in=document_ids).update(
                    purge_after=now,
                    next_purge_attempt_at=now,
                )
                transaction.on_commit(
                    lambda ids=tuple(str(doc_id) for doc_id in document_ids): [
                        purge_kyc_document.delay(document_id)
                        for document_id in ids
                    ],
                )
            expired += 1
    return expired


def _cleanup_unlinked_private_profile_keys(keys):
    """Delete provisional copies and prove their absence before forgetting keys."""
    from profiles.private_storage import (
        PrivateObjectIntegrityError,
        PrivateStorageUnavailable,
        private_object_storage,
    )

    try:
        for key in keys:
            if key and not private_object_storage.delete(scope='profile', key=key):
                return False
    except (PrivateObjectIntegrityError, PrivateStorageUnavailable):
        return False
    return True


def _record_unlinked_private_profile_copy(photo_id, main_key, thumbnail_key):
    """Retain opaque cleanup handles if compensation itself cannot be verified."""
    from profiles.models import ProfilePhoto

    with transaction.atomic():
        photo = ProfilePhoto.objects.select_for_update().filter(id=photo_id).first()
        if photo is None or photo.storage_state == ProfilePhoto.PRIVATE:
            return
        photo.storage_key = main_key or ''
        photo.thumbnail_storage_key = thumbnail_key or ''
        photo.storage_state = ProfilePhoto.MIGRATION_FAILED
        photo.save(update_fields=[
            'storage_key', 'thumbnail_storage_key', 'storage_state',
        ])


@shared_task(bind=True, max_retries=8, default_retry_delay=60)
def migrate_legacy_profile_photo(self, photo_id: str):
    """Copy, verify, switch and delete one historical public profile photo."""
    from profiles.models import ProfilePhoto
    from profiles.private_storage import (
        PrivateObjectIntegrityError,
        PrivateStorageUnavailable,
        PrivateObjectNotFound,
        delete_legacy_profile_object,
        detect_binary_mime_type,
        download_legacy_profile_object,
        legacy_profile_object_path,
        private_object_storage,
        validate_document_binary,
    )

    with transaction.atomic():
        photo = (
            ProfilePhoto.objects.select_for_update()
            .select_related('profile')
            .filter(id=photo_id)
            .first()
        )
        if photo is None or photo.storage_state == ProfilePhoto.PRIVATE:
            return 'already_private'
        if photo.storage_state == ProfilePhoto.MIGRATION_FAILED:
            return 'manual_intervention_required'
        if not photo.legacy_source_verified:
            return 'unsupported_legacy_reference'
        legacy_main = legacy_profile_object_path(
            photo.photo_url, owner_id=photo.profile.user_id,
        )
        legacy_thumbnail = legacy_profile_object_path(
            photo.thumbnail_url, owner_id=photo.profile.user_id,
        )
        if not legacy_main or not legacy_thumbnail:
            photo.storage_state = ProfilePhoto.MIGRATION_FAILED
            photo.save(update_fields=['storage_state'])
            return 'unsupported_legacy_reference'
        copied = photo.storage_state == ProfilePhoto.MIGRATION_COPIED
        main_key = photo.storage_key
        thumbnail_key = photo.thumbnail_storage_key

    provisional_keys = []
    private_copy_verified = copied
    try:
        if not copied:
            main_data = download_legacy_profile_object(legacy_main)
            thumbnail_data = download_legacy_profile_object(legacy_thumbnail)
            main_content_type = detect_binary_mime_type(main_data)
            thumbnail_content_type = detect_binary_mime_type(thumbnail_data)
            if not main_content_type.startswith('image/') or not thumbnail_content_type.startswith('image/'):
                raise PrivateObjectIntegrityError()
            validate_document_binary(
                data=main_data, expected_mime_type=main_content_type,
            )
            validate_document_binary(
                data=thumbnail_data, expected_mime_type=thumbnail_content_type,
            )
            main_key = private_object_storage.new_key('profile')
            thumbnail_key = private_object_storage.new_key('profile')
            # Track candidate keys before each write: a provider timeout can
            # occur after bytes were accepted, so they remain recoverable.
            provisional_keys.append(main_key)
            private_object_storage.put_bytes(
                scope='profile', key=main_key, data=main_data, content_type=main_content_type,
            )
            provisional_keys.append(thumbnail_key)
            private_object_storage.put_bytes(
                scope='profile', key=thumbnail_key, data=thumbnail_data, content_type=thumbnail_content_type,
            )
            main_metadata = private_object_storage.metadata(scope='profile', key=main_key)
            thumbnail_metadata = private_object_storage.metadata(scope='profile', key=thumbnail_key)
            if (
                main_metadata.size_bytes != len(main_data)
                or thumbnail_metadata.size_bytes != len(thumbnail_data)
                or private_object_storage.download(scope='profile', key=main_key) != main_data
                or private_object_storage.download(scope='profile', key=thumbnail_key) != thumbnail_data
            ):
                raise PrivateObjectIntegrityError()
            with transaction.atomic():
                photo = ProfilePhoto.objects.select_for_update().get(id=photo_id)
                if photo.storage_state != ProfilePhoto.LEGACY_PUBLIC:
                    return 'state_changed'
                photo.storage_key = main_key
                photo.thumbnail_storage_key = thumbnail_key
                photo.storage_state = ProfilePhoto.MIGRATION_COPIED
                photo.save(update_fields=[
                    'storage_key', 'thumbnail_storage_key', 'storage_state',
                ])
            private_copy_verified = True
        else:
            # A retry may follow a failed legacy deletion.  Do not delete the
            # source unless both private objects still exist and are valid
            # images; otherwise leave the row fail-closed for an operator.
            if not main_key or not thumbnail_key:
                raise PrivateObjectIntegrityError()
            for key in (main_key, thumbnail_key):
                metadata = private_object_storage.metadata(scope='profile', key=key)
                data = private_object_storage.download(scope='profile', key=key)
                content_type = detect_binary_mime_type(data)
                if not content_type.startswith('image/') or metadata.size_bytes != len(data):
                    raise PrivateObjectIntegrityError()
                validate_document_binary(data=data, expected_mime_type=content_type)

        if not delete_legacy_profile_object(legacy_main):
            raise PrivateStorageUnavailable()
        if not delete_legacy_profile_object(legacy_thumbnail):
            raise PrivateStorageUnavailable()
    except PrivateStorageUnavailable:
        if not private_copy_verified and provisional_keys:
            if not _cleanup_unlinked_private_profile_keys(provisional_keys):
                _record_unlinked_private_profile_copy(
                    photo_id, main_key, thumbnail_key,
                )
                return 'private_cleanup_unverified'
        raise self.retry(
            countdown=min(3600, 60 * (2 ** self.request.retries)),
        ) from None
    except PrivateObjectNotFound:
        if not private_copy_verified and provisional_keys:
            if not _cleanup_unlinked_private_profile_keys(provisional_keys):
                _record_unlinked_private_profile_copy(
                    photo_id, main_key, thumbnail_key,
                )
                return 'private_cleanup_unverified'
        with transaction.atomic():
            ProfilePhoto.objects.filter(
                id=photo_id,
                storage_state__in=[
                    ProfilePhoto.LEGACY_PUBLIC,
                    ProfilePhoto.MIGRATION_COPIED,
                ],
            ).update(storage_state=ProfilePhoto.MIGRATION_FAILED)
        return 'source_or_copy_missing'
    except PrivateObjectIntegrityError:
        if not private_copy_verified and provisional_keys:
            if not _cleanup_unlinked_private_profile_keys(provisional_keys):
                _record_unlinked_private_profile_copy(
                    photo_id, main_key, thumbnail_key,
                )
                return 'private_cleanup_unverified'
        with transaction.atomic():
            ProfilePhoto.objects.filter(
                id=photo_id,
                storage_state__in=[
                    ProfilePhoto.LEGACY_PUBLIC,
                    ProfilePhoto.MIGRATION_COPIED,
                ],
            ).update(storage_state=ProfilePhoto.MIGRATION_FAILED)
        return 'verification_failed'

    with transaction.atomic():
        photo = ProfilePhoto.objects.select_for_update().filter(id=photo_id).first()
        if photo is None:
            return 'row_removed'
        photo.photo_url = ''
        photo.thumbnail_url = ''
        photo.storage_state = ProfilePhoto.PRIVATE
        photo.legacy_source_verified = False
        photo.private_migrated_at = timezone.now()
        photo.legacy_deleted_at = photo.private_migrated_at
        photo.save(update_fields=[
            'photo_url', 'thumbnail_url', 'storage_state', 'legacy_source_verified', 'private_migrated_at',
            'legacy_deleted_at',
        ])
    logger.info('Legacy profile photo migrated to private storage')
    return 'migrated'


@shared_task
def migrate_legacy_profile_photos(batch_size=100):
    """Dispatch bounded, idempotent migrations; failed rows need an operator."""
    from profiles.models import ProfilePhoto

    photo_ids = list(
        ProfilePhoto.objects.filter(
            storage_state__in=[
                ProfilePhoto.LEGACY_PUBLIC,
                ProfilePhoto.MIGRATION_COPIED,
            ],
            legacy_source_verified=True,
        ).values_list('id', flat=True)[:batch_size]
    )
    for photo_id in photo_ids:
        migrate_legacy_profile_photo.delay(str(photo_id))
    return len(photo_ids)
