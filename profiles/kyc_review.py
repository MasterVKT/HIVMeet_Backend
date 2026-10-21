"""Human-only internal KYC review controls.

This module deliberately never returns object keys, signed URLs, selfie
challenges, medical content, or a review comment.  Document bytes can be read
only by the explicitly development-only, in-memory fixture helper below.  It
provides the privilege, MFA, assignment and atomic-decision boundaries used by
the restricted internal interface.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import struct
from datetime import timedelta
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import PermissionDenied

from .kyc import KYC_VALIDITY, KycIdempotencyConflict, KycStateConflict, _safe_audit_event, sync_legacy_verification_projection
from .models import (
    KycAttempt,
    KycDecisionEmailDelivery,
    KycDocument,
    KycReviewAssignment,
    KycReviewDecision,
    KycReviewerMfaAssertion,
    KycReviewerMfaDevice,
)
from .private_storage import private_object_storage


KYC_REVIEWER_GROUP = 'kyc_reviewer'
KYC_SUPERVISOR_GROUP = 'kyc_supervisor'
MFA_ASSERTION_TTL = timedelta(minutes=5)
TOTP_PERIOD_SECONDS = 30
logger = logging.getLogger('hivmeet.kyc_review')
DECISION_REASON_CODES = {
    KycReviewDecision.VERIFIED: {'verified_human_review'},
    KycReviewDecision.REJECTED: {
        'identity_unreadable', 'medical_document_outdated',
        'selfie_challenge_invalid', 'document_inconsistent',
    },
    KycReviewDecision.REVOKED: {'manual_revocation', 'policy_revocation'},
}


class KycReviewAccessDenied(PermissionDenied):
    default_detail = _('Internal KYC reviewer access is required.')
    default_code = 'forbidden'


def reviewer_role(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return ''
    names = set(user.groups.filter(
        name__in=[KYC_REVIEWER_GROUP, KYC_SUPERVISOR_GROUP]
    ).values_list('name', flat=True))
    if KYC_SUPERVISOR_GROUP in names:
        return KYC_SUPERVISOR_GROUP
    if KYC_REVIEWER_GROUP in names:
        return KYC_REVIEWER_GROUP
    return ''


def _fernet():
    value = getattr(settings, 'KYC_REVIEW_ENCRYPTION_KEY', '').strip()
    if value:
        try:
            return Fernet(value.encode('ascii'))
        except (ValueError, TypeError):
            raise KycReviewAccessDenied() from None
    if not (settings.DEBUG or getattr(settings, 'TESTING', False)):
        raise KycReviewAccessDenied()
    material = hashlib.sha256(
        f'kyc-review-development:{settings.SECRET_KEY}'.encode('utf-8')
    ).digest()
    return Fernet(base64.urlsafe_b64encode(material))


def _totp_counter(now=None):
    now = now or timezone.now()
    return int(now.timestamp()) // TOTP_PERIOD_SECONDS


def _totp_code(secret, counter):
    digest = hmac.new(
        base64.b32decode(secret + '=' * (-len(secret) % 8)), struct.pack('>Q', counter), hashlib.sha1,
    ).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f'{value % 1_000_000:06d}'


def _decrypt_secret(device):
    try:
        return _fernet().decrypt(device.secret_ciphertext.encode('ascii')).decode('ascii')
    except (InvalidToken, UnicodeError):
        raise KycReviewAccessDenied() from None


def _matching_totp_counter(device, code, now=None):
    if not isinstance(code, str) or not code.isdigit() or len(code) != 6:
        return None
    secret = _decrypt_secret(device)
    current = _totp_counter(now)
    for counter in (current - 1, current, current + 1):
        if hmac.compare_digest(_totp_code(secret, counter), code):
            return counter
    return None


def begin_mfa_enrollment(*, user):
    """Bootstrap only a local development reviewer TOTP device."""
    if not reviewer_role(user) or not (settings.DEBUG or getattr(settings, 'TESTING', False)):
        raise KycReviewAccessDenied()
    if KycReviewerMfaDevice.objects.filter(user=user, confirmed_at__isnull=False).exists():
        raise KycStateConflict()
    secret = base64.b32encode(secrets.token_bytes(20)).decode('ascii').rstrip('=')
    ciphertext = _fernet().encrypt(secret.encode('ascii')).decode('ascii')
    device, _ = KycReviewerMfaDevice.objects.update_or_create(
        user=user,
        defaults={'secret_ciphertext': ciphertext, 'confirmed_at': None, 'last_totp_counter': None},
    )
    label = quote('HIVMeet KYC reviewer', safe='')
    uri = f'otpauth://totp/{label}?secret={secret}&issuer=HIVMeet&period=30&digits=6'
    return device, uri


@transaction.atomic
def confirm_mfa_enrollment(*, user, code, now=None):
    if not reviewer_role(user):
        raise KycReviewAccessDenied()
    device = KycReviewerMfaDevice.objects.select_for_update().filter(user=user).first()
    if device is None or device.confirmed_at is not None:
        raise KycStateConflict()
    counter = _matching_totp_counter(device, code, now)
    if counter is None:
        raise KycReviewAccessDenied()
    device.confirmed_at = now or timezone.now()
    device.last_totp_counter = counter
    device.save(update_fields=['confirmed_at', 'last_totp_counter', 'updated_at'])


@transaction.atomic
def verify_reviewer_mfa(*, user, code, now=None):
    if not reviewer_role(user):
        raise KycReviewAccessDenied()
    now = now or timezone.now()
    device = KycReviewerMfaDevice.objects.select_for_update().filter(user=user).first()
    if device is None or device.confirmed_at is None:
        raise KycReviewAccessDenied()
    counter = _matching_totp_counter(device, code, now)
    if counter is None or (device.last_totp_counter is not None and counter <= device.last_totp_counter):
        raise KycReviewAccessDenied()
    device.last_totp_counter = counter
    device.save(update_fields=['last_totp_counter', 'updated_at'])
    raw_token = secrets.token_urlsafe(32)
    KycReviewerMfaAssertion.objects.filter(user=user, expires_at__lte=now).delete()
    KycReviewerMfaAssertion.objects.create(
        user=user,
        token_hash=make_password(raw_token),
        expires_at=now + MFA_ASSERTION_TTL,
    )
    return raw_token, now + MFA_ASSERTION_TTL


def require_reviewer_mfa(*, user, assertion):
    role = reviewer_role(user)
    if not role or not isinstance(assertion, str) or not assertion:
        raise KycReviewAccessDenied()
    now = timezone.now()
    for candidate in KycReviewerMfaAssertion.objects.filter(
        user=user, expires_at__gt=now,
    ).only('token_hash'):
        if check_password(assertion, candidate.token_hash):
            return role
    raise KycReviewAccessDenied()


def _decision_fingerprint(*, attempt_id, idempotency_key):
    return hmac.new(
        settings.SECRET_KEY.encode('utf-8'),
        f'kyc-review-decision:v1:{attempt_id}:{idempotency_key}'.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def _request_fingerprint(*, decision, reason_code, internal_comment):
    return hmac.new(
        settings.SECRET_KEY.encode('utf-8'),
        f'kyc-review-request:v1:{decision}:{reason_code}:{internal_comment}'.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def _assigned_case_or_denied(*, actor, role, attempt_id):
    if role not in {KYC_REVIEWER_GROUP, KYC_SUPERVISOR_GROUP}:
        raise KycReviewAccessDenied()
    assignment = KycReviewAssignment.objects.select_for_update().select_related(
        'attempt', 'attempt__user', 'reviewer', 'supervisor',
    ).filter(attempt_id=attempt_id, closed_at__isnull=True).first()
    if assignment is None:
        raise KycReviewAccessDenied()
    if role == KYC_REVIEWER_GROUP and assignment.reviewer_id != actor.id:
        raise KycReviewAccessDenied()
    if role == KYC_SUPERVISOR_GROUP and assignment.supervisor_id != actor.id:
        raise KycReviewAccessDenied()
    return assignment


@transaction.atomic
def assign_kyc_case(*, supervisor, attempt_id, reviewer_id, now=None):
    if reviewer_role(supervisor) != KYC_SUPERVISOR_GROUP:
        raise KycReviewAccessDenied()
    attempt = KycAttempt.objects.select_for_update().filter(
        id=attempt_id, status=KycAttempt.PENDING_REVIEW, is_open=True,
    ).first()
    reviewer = supervisor.__class__.objects.filter(id=reviewer_id, is_active=True).first()
    if attempt is None or reviewer is None or not reviewer_role(reviewer):
        raise KycStateConflict()
    assignment, created = KycReviewAssignment.objects.get_or_create(
        attempt=attempt,
        defaults={'reviewer': reviewer, 'supervisor': supervisor},
    )
    if not created:
        if assignment.closed_at is not None:
            raise KycStateConflict()
        assignment.reviewer = reviewer
        assignment.supervisor = supervisor
        assignment.save(update_fields=['reviewer', 'supervisor'])
    _safe_audit_event(
        attempt=attempt, actor=supervisor, event_type='review_case_assigned',
        metadata={'status': attempt.status}, actor_role=KYC_SUPERVISOR_GROUP,
    )
    return assignment


@transaction.atomic
def issue_reviewer_document_url(*, actor, role, attempt_id, document_id, now=None):
    now = now or timezone.now()
    assignment = _assigned_case_or_denied(actor=actor, role=role, attempt_id=attempt_id)
    document = KycDocument.objects.filter(
        id=document_id, attempt=assignment.attempt,
        scan_status=KycDocument.ACCEPTED,
    ).first()
    if document is None:
        raise KycReviewAccessDenied()
    expires_at = now + timedelta(seconds=settings.KYC_REVIEW_DOCUMENT_URL_TTL_SECONDS)
    url = private_object_storage.issue_reviewer_read_url(
        key=document.opaque_storage_key, expires_at=expires_at,
    )
    _safe_audit_event(
        attempt=assignment.attempt, actor=actor, event_type='review_document_accessed',
        metadata={'document_type': document.document_type}, actor_role=role,
    )
    return url, expires_at


@transaction.atomic
def read_reviewer_document_for_development(*, actor, role, attempt_id, document_id):
    """Read synthetic development evidence from a protected local adapter."""
    if not (
        (settings.DEBUG or getattr(settings, 'TESTING', False))
        and settings.KYC_STORAGE_BACKEND in {'memory', 'local'}
    ):
        raise KycReviewAccessDenied()
    assignment = _assigned_case_or_denied(actor=actor, role=role, attempt_id=attempt_id)
    document = KycDocument.objects.filter(
        id=document_id, attempt=assignment.attempt,
        scan_status=KycDocument.ACCEPTED,
    ).first()
    if document is None:
        raise KycReviewAccessDenied()
    metadata = private_object_storage.metadata(scope='kyc', key=document.opaque_storage_key)
    content = private_object_storage.download(scope='kyc', key=document.opaque_storage_key)
    _safe_audit_event(
        attempt=assignment.attempt, actor=actor, event_type='review_document_accessed',
        metadata={'document_type': document.document_type}, actor_role=role,
    )
    return content, metadata.content_type


@transaction.atomic
def decide_kyc_case(*, actor, role, attempt_id, decision, reason_code,
                    internal_comment, idempotency_key, now=None):
    now = now or timezone.now()
    if reviewer_role(actor) != role:
        raise KycReviewAccessDenied()
    fingerprint = _decision_fingerprint(
        attempt_id=attempt_id, idempotency_key=idempotency_key,
    )
    request_fingerprint = _request_fingerprint(
        decision=decision, reason_code=reason_code, internal_comment=internal_comment,
    )
    existing = KycReviewDecision.objects.filter(idempotency_fingerprint=fingerprint).first()
    if existing is not None:
        if existing.attempt_id == attempt_id and existing.decided_by_id == actor.id and existing.request_fingerprint == request_fingerprint:
            return existing, True
        raise KycIdempotencyConflict()
    assignment = _assigned_case_or_denied(actor=actor, role=role, attempt_id=attempt_id)
    attempt = assignment.attempt
    if attempt.status != KycAttempt.PENDING_REVIEW:
        raise KycStateConflict()
    if decision not in {KycReviewDecision.VERIFIED, KycReviewDecision.REJECTED, KycReviewDecision.REVOKED}:
        raise KycStateConflict()
    if reason_code not in DECISION_REASON_CODES[decision]:
        raise KycStateConflict()
    comment_ciphertext = ''
    if internal_comment:
        comment_ciphertext = _fernet().encrypt(internal_comment.encode('utf-8')).decode('ascii')
    record = KycReviewDecision.objects.create(
        attempt=attempt, assignment=assignment, decided_by=actor,
        decision=decision, reason_code=reason_code,
        internal_comment_ciphertext=comment_ciphertext,
        idempotency_fingerprint=fingerprint, request_fingerprint=request_fingerprint,
    )
    attempt.status = KycAttempt.VERIFIED if decision == KycReviewDecision.VERIFIED else KycAttempt.REJECTED
    attempt.rejection_reason_code = '' if decision == KycReviewDecision.VERIFIED else reason_code
    attempt.reviewed_at = now
    attempt.expires_at = now + KYC_VALIDITY if decision == KycReviewDecision.VERIFIED else None
    attempt.is_open = False
    attempt.save(update_fields=['status', 'rejection_reason_code', 'reviewed_at', 'expires_at', 'is_open', 'updated_at'])
    assignment.closed_at = now
    assignment.save(update_fields=['closed_at'])
    attempt.documents.filter(purged_at__isnull=True).update(
        purge_after=now, next_purge_attempt_at=now,
    )
    sync_legacy_verification_projection(attempt, now)
    _safe_audit_event(
        attempt=attempt, actor=actor, event_type='review_decision_recorded',
        metadata={'status': attempt.status, 'reason_code': reason_code}, actor_role=role,
    )
    from notifications.models import Notification
    Notification.objects.create(
        user=attempt.user, type='system', title=_('Verification update'),
        body=_('Your verification status has been updated.'),
        data={'event': 'verification_update'},
    )
    delivery = KycDecisionEmailDelivery.objects.create(decision=record)

    # The email is only queued after the decision, its KYC projection and the
    # generic in-app notification have committed together.  A decision replay
    # returns before this point, so it can never create another delivery row.
    transaction.on_commit(
        lambda delivery_id=str(delivery.id): _queue_kyc_decision_email(delivery_id),
    )
    return record, False


def _queue_kyc_decision_email(delivery_id):
    """Import lazily to keep the decision transaction independent of Celery."""
    from .tasks import send_kyc_decision_email

    try:
        send_kyc_decision_email.delay(delivery_id)
    except Exception:
        # The decision and its pending delivery row are already committed.  Beat
        # will recover this row, so a broker outage cannot roll back or mask a
        # human KYC decision.
        logger.error('KYC decision email queue unavailable')
