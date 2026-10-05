"""KYC state, authorisation and privacy-safe transition helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.permissions import BasePermission

from .models import KycAttempt, KycAuditEvent, KycDocument, KycUploadIntent
from .private_storage import private_object_storage, private_storage_configuration_errors


KYC_CHALLENGE_TTL = timedelta(minutes=30)
KYC_VALIDITY = timedelta(days=180)
KYC_ATTEMPT_DAILY_LIMIT = 5
KYC_UPLOAD_INTENT_TTL = timedelta(seconds=getattr(settings, 'KYC_STORAGE_UPLOAD_TTL_SECONDS', 600))


class KycStateConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = _('This KYC action is not valid for the current state.')
    default_code = 'invalid_state'


class KycIdempotencyConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = _('This idempotency key was already used for a different KYC request.')
    default_code = 'idempotency_conflict'


class KycExpired(APIException):
    status_code = status.HTTP_410_GONE
    default_detail = _('This KYC challenge or upload intent has expired.')
    default_code = 'challenge_expired'


class KycUploadIntentExpired(APIException):
    status_code = status.HTTP_410_GONE
    default_detail = _('This KYC upload intent has expired.')
    default_code = 'intent_expired'


class KycRateLimited(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = _('Too many KYC attempts. Please try again later.')
    default_code = 'rate_limited'


class KycStorageUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = _('Secure KYC storage is not available yet.')
    default_code = 'dependency_unavailable'


class KycLegacyEndpointDeprecated(APIException):
    status_code = status.HTTP_410_GONE
    default_detail = _('This legacy KYC endpoint is no longer available.')
    default_code = 'kyc_legacy_endpoint_deprecated'


class KycRequired(PermissionDenied):
    default_detail = _('An active verification is required for this feature.')
    default_code = 'kyc_required'


def has_active_kyc(user, now=None) -> bool:
    """Return the sole authoritative social-access decision."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    now = now or timezone.now()
    return KycAttempt.objects.filter(
        user=user,
        status=KycAttempt.VERIFIED,
        expires_at__gt=now,
    ).exists()


class HasActiveKycVerification(BasePermission):
    """DRF permission for every social or effective-Premium entry point."""

    message = _('An active verification is required for this feature.')

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not has_active_kyc(request.user):
            raise KycRequired()
        return True


def protect_view_with_active_kyc(view):
    """Attach the DRF KYC permission while declaring an API URL pattern."""
    view_class = getattr(view, 'cls', None)
    if view_class is None:
        raise TypeError('KYC-protected routes must be DRF views.')
    permissions = list(getattr(view_class, 'permission_classes', ()))
    if HasActiveKycVerification not in permissions:
        permissions.append(HasActiveKycVerification)
        view_class.permission_classes = permissions
    return view


def _challenge_code(attempt):
    """Derive a replay-safe code without storing the code itself."""
    material = (
        f'{attempt.id}:{attempt.challenge_nonce}:{attempt.challenge_idempotency_key}'
    ).encode('utf-8')
    digest = hmac.new(
        settings.SECRET_KEY.encode('utf-8'),
        material,
        hashlib.sha256,
    ).hexdigest().upper()
    return digest[:10]


def _audit_idempotency_fingerprint(idempotency_key):
    """Return a non-reversible audit correlation value for a client key.

    A client-provided idempotency key is operational data, not a KYC document
    attribute, but audit events must still never preserve arbitrary client
    input verbatim. This keyed fingerprint lets retry handling correlate a
    request without making the supplied value exportable from audit storage.
    """
    material = f'kyc-audit-idempotency:v1:{idempotency_key}'.encode('utf-8')
    digest = hmac.new(
        settings.SECRET_KEY.encode('utf-8'),
        material,
        hashlib.sha256,
    ).hexdigest()
    return f'v1:{digest[:32]}'


def _safe_audit_event(*, attempt, actor, event_type, metadata=None):
    """Persist only whitelisted technical metadata."""
    safe_metadata = {}
    for key, value in (metadata or {}).items():
        if (
            key in {
            'idempotency_key',
            'idempotent_replay',
            'origin',
            'previous_status',
            'status',
            'document_type',
            'scan_status',
            'reason_code',
        }
        and isinstance(value, (str, bool, int, float))
        ):
            safe_metadata[key] = (
                _audit_idempotency_fingerprint(value)
                if key == 'idempotency_key'
                else value
            )
    KycAuditEvent.objects.create(
        attempt=attempt,
        actor=actor,
        actor_role=getattr(actor, 'role', '') if actor else '',
        event_type=event_type,
        metadata=safe_metadata,
    )


def sync_legacy_verification_projection(attempt, now=None):
    """Mirror safe status dates into legacy fields without trusting documents."""
    from .models import Verification

    now = now or timezone.now()
    verification, _ = Verification.objects.get_or_create(user=attempt.user)
    verification.status = attempt.status
    verification.submitted_at = attempt.submitted_at
    verification.reviewed_at = attempt.reviewed_at
    verification.expires_at = attempt.expires_at
    verification.save(
        update_fields=[
            'status',
            'submitted_at',
            'reviewed_at',
            'expires_at',
            'updated_at',
        ]
    )
    user_status = (
        'verified'
        if attempt.status == KycAttempt.VERIFIED
        and attempt.expires_at is not None
        and attempt.expires_at > now
        else 'rejected'
        if attempt.status == KycAttempt.REJECTED
        else 'expired'
        if attempt.status == KycAttempt.EXPIRED
        else 'pending'
        if attempt.status
        in {
            KycAttempt.PENDING_ID,
            KycAttempt.PENDING_MEDICAL,
            KycAttempt.PENDING_SELFIE,
            KycAttempt.PENDING_REVIEW,
        }
        else 'not_started'
    )
    is_verified = user_status == 'verified'
    if (
        attempt.user.is_verified != is_verified
        or attempt.user.verification_status != user_status
    ):
        attempt.user.is_verified = is_verified
        attempt.user.verification_status = user_status
        attempt.user.save(update_fields=['is_verified', 'verification_status'])


def _issue_challenge(attempt, idempotency_key, now):
    attempt.challenge_nonce = secrets.token_urlsafe(24)
    attempt.challenge_idempotency_key = idempotency_key
    attempt.challenge_expires_at = now + KYC_CHALLENGE_TTL
    attempt.challenge_used_at = None
    challenge_code = _challenge_code(attempt)
    attempt.challenge_hash = make_password(challenge_code)
    return challenge_code


@transaction.atomic
def start_or_resume_kyc_attempt(*, user, consent_version, idempotency_key, now=None):
    """Start one locked attempt or replay the exact start request safely."""
    now = now or timezone.now()
    day_start = timezone.localtime(now).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    # Locking the account serialises first-start requests before a conditional
    # unique constraint can surface a database-specific race to the client.
    user.__class__.objects.select_for_update().get(pk=user.pk)
    issued_today = KycAuditEvent.objects.filter(
        attempt__user_id=user.pk,
        event_type__in=['attempt_started', 'challenge_reissued'],
        created_at__gte=day_start,
    ).count()
    attempt = (
        KycAttempt.objects.select_for_update()
        .filter(user=user, is_open=True)
        .order_by('-created_at')
        .first()
    )
    if attempt is not None:
        if (
            attempt.challenge_idempotency_key == idempotency_key
            and attempt.challenge_expires_at
            and attempt.challenge_expires_at > now
        ):
            if attempt.consent_version != consent_version:
                raise KycIdempotencyConflict()
            return attempt, _challenge_code(attempt), True
        if (
            attempt.status == KycAttempt.PENDING_REVIEW
            or attempt.challenge_used_at is not None
        ):
            raise KycStateConflict()
        if issued_today >= KYC_ATTEMPT_DAILY_LIMIT:
            raise KycRateLimited()

        previous_status = attempt.status
        attempt.status = KycAttempt.PENDING_ID
        attempt.consent_version = consent_version
        attempt.origin = KycAttempt.ORIGIN_USER_START
        challenge_code = _issue_challenge(attempt, idempotency_key, now)
        attempt.save(
            update_fields=[
                'status',
                'consent_version',
                'origin',
                'challenge_nonce',
                'challenge_idempotency_key',
                'challenge_expires_at',
                'challenge_used_at',
                'challenge_hash',
                'updated_at',
            ]
        )
        _safe_audit_event(
            attempt=attempt,
            actor=user,
            event_type='challenge_reissued',
            metadata={'previous_status': previous_status, 'status': attempt.status},
        )
        sync_legacy_verification_projection(attempt, now)
        return attempt, challenge_code, False

    if issued_today >= KYC_ATTEMPT_DAILY_LIMIT:
        raise KycRateLimited()

    attempt = KycAttempt(
        user=user,
        status=KycAttempt.PENDING_ID,
        origin=KycAttempt.ORIGIN_USER_START,
        consent_version=consent_version,
        is_open=True,
    )
    attempt.save()
    challenge_code = _issue_challenge(attempt, idempotency_key, now)
    attempt.save(
        update_fields=[
            'challenge_nonce',
            'challenge_idempotency_key',
            'challenge_expires_at',
            'challenge_hash',
            'updated_at',
        ]
    )
    _safe_audit_event(
        attempt=attempt,
        actor=user,
        event_type='attempt_started',
        metadata={'origin': attempt.origin, 'status': attempt.status},
    )
    sync_legacy_verification_projection(attempt, now)
    return attempt, challenge_code, False


def serialize_safe_kyc_status(*, user, now=None):
    """Build a response without keys, URLs, hashes or document content."""
    now = now or timezone.now()
    attempt = (
        KycAttempt.objects.filter(user=user)
        .prefetch_related('documents')
        .order_by('-created_at')
        .first()
    )
    states = {
        KycDocument.IDENTITY_DOCUMENT: 'missing',
        KycDocument.MEDICAL_DOCUMENT: 'missing',
        KycDocument.SELFIE_WITH_CODE: 'missing',
    }
    if attempt is None:
        return {
            'attempt_id': None,
            'status': KycAttempt.NOT_STARTED,
            'documents': [
                {'type': document_type, 'state': state}
                for document_type, state in states.items()
            ],
            'expires_at': None,
            'submitted_at': None,
            'rejection_reason_code': None,
        }
    state_map = {
        KycDocument.ISSUED: 'intent_issued',
        KycDocument.UPLOADED: 'uploaded',
        KycDocument.SCANNING: 'processing',
        KycDocument.QUARANTINED: 'processing',
        KycDocument.ACCEPTED: 'accepted',
        KycDocument.PURGED: 'missing',
    }
    for document in attempt.documents.all():
        states[document.document_type] = state_map[document.scan_status]
    public_status = attempt.status
    if (
        public_status == KycAttempt.VERIFIED
        and (attempt.expires_at is None or attempt.expires_at <= now)
    ):
        public_status = KycAttempt.EXPIRED
    return {
        'attempt_id': str(attempt.id),
        'status': public_status,
        'documents': [
            {'type': document_type, 'state': state}
            for document_type, state in states.items()
        ],
        'expires_at': attempt.expires_at,
        'submitted_at': attempt.submitted_at,
        'rejection_reason_code': attempt.rejection_reason_code or None,
    }


def validate_selfie_challenge(*, attempt, submitted_code, now=None):
    """Validate a one-use expiry-bound challenge without leaking its value."""
    now = now or timezone.now()
    if not attempt.challenge_expires_at or attempt.challenge_expires_at <= now:
        raise KycExpired()
    if attempt.challenge_used_at is not None:
        raise KycStateConflict()
    if not attempt.challenge_hash or not check_password(
        submitted_code, attempt.challenge_hash
    ):
        raise KycStateConflict()
    attempt.challenge_used_at = now


def accepted_documents_for_attempt(attempt):
    return {
        document.document_type: document
        for document in attempt.documents.filter(scan_status=KycDocument.ACCEPTED)
    }


def _transition_attempt_for_documents(attempt):
    """Expose only the next missing technical evidence state to the applicant."""
    accepted_types = set(
        attempt.documents.filter(scan_status=KycDocument.ACCEPTED).values_list(
            'document_type', flat=True,
        )
    )
    if KycDocument.IDENTITY_DOCUMENT not in accepted_types:
        next_status = KycAttempt.PENDING_ID
    elif KycDocument.MEDICAL_DOCUMENT not in accepted_types:
        next_status = KycAttempt.PENDING_MEDICAL
    elif KycDocument.SELFIE_WITH_CODE not in accepted_types:
        next_status = KycAttempt.PENDING_SELFIE
    else:
        return
    if attempt.status != next_status:
        attempt.status = next_status
        attempt.save(update_fields=['status', 'updated_at'])
        sync_legacy_verification_projection(attempt)


@transaction.atomic
def issue_kyc_upload_intent(*, user, values, now=None):
    """Persist one opaque upload declaration before issuing a non-persisted URL."""
    now = now or timezone.now()
    if private_storage_configuration_errors('kyc'):
        raise KycStorageUnavailable()
    attempt = (
        KycAttempt.objects.select_for_update()
        .filter(id=values['attempt_id'], user=user, is_open=True)
        .first()
    )
    if attempt is None or attempt.status not in {
        KycAttempt.PENDING_ID,
        KycAttempt.PENDING_MEDICAL,
        KycAttempt.PENDING_SELFIE,
    }:
        raise KycStateConflict()

    existing = (
        KycUploadIntent.objects.select_for_update()
        .filter(attempt=attempt, idempotency_key=values['idempotency_key'])
        .first()
    )
    if existing is not None:
        same_request = (
            existing.document_type == values['document_type']
            and existing.declared_mime_type == values['mime_type']
            and existing.declared_size_bytes == values['size_bytes']
            and existing.declared_sha256.lower() == values['sha256'].lower()
        )
        if not same_request:
            raise KycIdempotencyConflict()
        if existing.status != KycUploadIntent.ISSUED or existing.expires_at <= now:
            raise KycUploadIntentExpired()
        return existing, True

    document = (
        KycDocument.objects.select_for_update()
        .filter(attempt=attempt, document_type=values['document_type'])
        .first()
    )
    if document is not None and document.scan_status != KycDocument.PURGED:
        # A previous object is retained until deletion is verified. Allowing a
        # replacement before that point would lose the only purge handle.
        raise KycStateConflict()

    opaque_key = private_object_storage.new_key('kyc')
    if document is None:
        document = KycDocument.objects.create(
            attempt=attempt,
            document_type=values['document_type'],
            opaque_storage_key=opaque_key,
            scan_status=KycDocument.ISSUED,
            purge_after=now + timedelta(hours=settings.KYC_QUARANTINE_RETENTION_HOURS),
        )
    else:
        document.opaque_storage_key = opaque_key
        document.sha256 = ''
        document.size_bytes = None
        document.detected_mime_type = ''
        document.scan_status = KycDocument.ISSUED
        document.scan_attempts = 0
        document.scan_started_at = None
        document.scan_completed_at = None
        document.quarantine_reason_code = ''
        document.purge_after = now + timedelta(hours=settings.KYC_QUARANTINE_RETENTION_HOURS)
        document.next_purge_attempt_at = None
        document.purge_attempts = 0
        document.purged_at = None
        document.deletion_verified_at = None
        document.save()

    intent = KycUploadIntent.objects.create(
        attempt=attempt,
        document=document,
        document_type=values['document_type'],
        declared_mime_type=values['mime_type'],
        declared_size_bytes=values['size_bytes'],
        declared_sha256=values['sha256'].lower(),
        idempotency_key=values['idempotency_key'],
        opaque_object_key=opaque_key,
        expires_at=now + KYC_UPLOAD_INTENT_TTL,
    )
    _safe_audit_event(
        attempt=attempt,
        actor=user,
        event_type='upload_intent_issued',
        metadata={
            'document_type': intent.document_type,
            'status': intent.status,
        },
    )
    return intent, False


def serialize_kyc_upload_intent(intent, *, replay=False):
    """Return a transient PUT URL without retaining it in a database or audit log."""
    upload_url = private_object_storage.issue_upload_url(
        key=intent.opaque_object_key,
        content_type=intent.declared_mime_type,
        content_length=intent.declared_size_bytes,
        expires_at=intent.expires_at,
    )
    return {
        'upload_id': str(intent.id),
        'expires_at': intent.expires_at,
        'required_headers': {
            'Content-Type': intent.declared_mime_type,
            'Content-Length': str(intent.declared_size_bytes),
        },
        'upload_url': upload_url,
        'idempotent_replay': replay,
    }


@transaction.atomic
def mark_kyc_upload_complete(*, user, upload_id, now=None):
    """Claim a user-owned direct upload and schedule the technical scan once."""
    now = now or timezone.now()
    intent = (
        KycUploadIntent.objects.select_for_update()
        # ``document`` is nullable to preserve pre-phase-2 audit rows.  PostgreSQL
        # cannot lock the nullable side of an outer join, so lock it separately.
        .select_related('attempt')
        .filter(id=upload_id, attempt__user=user, attempt__is_open=True)
        .first()
    )
    if intent is None or intent.document_id is None:
        raise KycStateConflict()
    if intent.status == KycUploadIntent.CONSUMED:
        return intent, True
    if intent.status != KycUploadIntent.ISSUED or intent.expires_at <= now:
        raise KycUploadIntentExpired()
    document = KycDocument.objects.select_for_update().filter(id=intent.document_id).first()
    if document is None:
        raise KycStateConflict()
    if document.scan_status not in {KycDocument.ISSUED, KycDocument.UPLOADED, KycDocument.SCANNING}:
        raise KycStateConflict()
    replay = intent.upload_confirmed_at is not None
    if not replay:
        intent.upload_confirmed_at = now
        intent.scan_enqueued_at = now
        intent.save(update_fields=['upload_confirmed_at', 'scan_enqueued_at'])
        document.scan_status = KycDocument.UPLOADED
        document.save(update_fields=['scan_status', 'updated_at'])
        _safe_audit_event(
            attempt=intent.attempt,
            actor=user,
            event_type='upload_scan_requested',
            metadata={'document_type': intent.document_type, 'status': document.scan_status},
        )
    return intent, replay


def _has_matching_consumed_upload_intents(*, attempt, upload_ids):
    """Verify the three opaque intent identifiers without exposing object data."""
    required = {
        KycDocument.IDENTITY_DOCUMENT: upload_ids['identity_upload_id'],
        KycDocument.MEDICAL_DOCUMENT: upload_ids['medical_upload_id'],
        KycDocument.SELFIE_WITH_CODE: upload_ids['selfie_upload_id'],
    }
    if len(set(required.values())) != len(required):
        return False
    intents = list(
        KycUploadIntent.objects.select_for_update().filter(
            id__in=required.values(),
            attempt=attempt,
            status=KycUploadIntent.CONSUMED,
        )
    )
    by_id = {intent.id: intent for intent in intents}
    return len(by_id) == len(required) and all(
        by_id.get(intent_id) is not None
        and by_id[intent_id].document_type == document_type
        for document_type, intent_id in required.items()
    )


@transaction.atomic
def submit_kyc_attempt(*, user, attempt_id, upload_ids, selfie_challenge_code, idempotency_key, now=None):
    """Transition to review only after phase-2 technical acceptance."""
    now = now or timezone.now()
    attempt = (
        KycAttempt.objects.select_for_update()
        .filter(id=attempt_id, user=user, is_open=True)
        .first()
    )
    if attempt is None:
        raise KycStateConflict()
    if attempt.status == KycAttempt.PENDING_REVIEW:
        event = attempt.audit_events.filter(event_type='attempt_submitted').last()
        if (
            event
            # The raw-value branch only supports event rows written before
            # the fingerprinting change. New events retain no client key.
            and event.metadata.get('idempotency_key') in {
                idempotency_key,
                _audit_idempotency_fingerprint(idempotency_key),
            }
            and _has_matching_consumed_upload_intents(
                attempt=attempt,
                upload_ids=upload_ids,
            )
            and attempt.challenge_hash
            and check_password(selfie_challenge_code, attempt.challenge_hash)
        ):
            return attempt, True
        raise KycIdempotencyConflict()
    if attempt.status not in {
        KycAttempt.PENDING_ID,
        KycAttempt.PENDING_MEDICAL,
        KycAttempt.PENDING_SELFIE,
    }:
        raise KycStateConflict()

    if not _has_matching_consumed_upload_intents(
        attempt=attempt,
        upload_ids=upload_ids,
    ):
        raise KycStateConflict()
    required = {
        KycDocument.IDENTITY_DOCUMENT: upload_ids['identity_upload_id'],
        KycDocument.MEDICAL_DOCUMENT: upload_ids['medical_upload_id'],
        KycDocument.SELFIE_WITH_CODE: upload_ids['selfie_upload_id'],
    }
    if set(accepted_documents_for_attempt(attempt)) != set(required):
        raise KycStateConflict()

    validate_selfie_challenge(
        attempt=attempt,
        submitted_code=selfie_challenge_code,
        now=now,
    )
    attempt.status = KycAttempt.PENDING_REVIEW
    attempt.submitted_at = now
    attempt.save(
        update_fields=[
            'status',
            'submitted_at',
            'challenge_used_at',
            'updated_at',
        ]
    )
    _safe_audit_event(
        attempt=attempt,
        actor=user,
        event_type='attempt_submitted',
        metadata={'idempotency_key': idempotency_key, 'status': attempt.status},
    )
    sync_legacy_verification_projection(attempt, now)
    return attempt, False
