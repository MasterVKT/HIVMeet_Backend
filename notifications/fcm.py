"""Privacy-safe FCM delivery with cautious token cleanup and retry signals."""
from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable

from firebase_admin import messaging

logger = logging.getLogger('hivmeet.notifications.fcm')

# Only these codes prove that a registration token itself is unusable.  In
# particular, INVALID_ARGUMENT is deliberately excluded: it can describe an
# invalid message payload rather than an invalid token.
_INVALID_TOKEN_CODES = frozenset({
    'registration-token-not-registered',
    'invalid-registration-token',
    'unregistered',
})

# These service-side errors can succeed without changing the registration token.
_RETRYABLE_CODES = frozenset({
    'unavailable',
    'internal',
    'deadline-exceeded',
    'resource-exhausted',
})


def _correlation_id(value: object) -> str:
    """Return a stable non-reversible identifier suitable for logs."""
    return hashlib.sha256(str(value).encode('utf-8')).hexdigest()[:12]


def _error_code(error: object | None) -> str:
    """Normalize Firebase Admin error codes without logging exception text."""
    raw = getattr(error, 'code', '') if error is not None else ''
    return str(raw or '').strip().lower().replace('_', '-')


def _result(*, success: int = 0, failure: int = 0, purged: int = 0,
            retryable: bool = False) -> dict:
    return {
        'success': success,
        'failure': failure,
        'purged': purged,
        # A caller retries only if all attempted tokens had known temporary
        # errors. This avoids resending to tokens that already succeeded.
        'retryable': retryable,
    }


def _record_response_failures(
    tokens: Iterable[str],
    responses: Iterable[object],
    *,
    subject: str,
) -> tuple[set[str], bool]:
    """Classify individual multicast failures without emitting token values."""
    invalid_tokens: set[str] = set()
    saw_failure = False
    all_failures_retryable = True

    for token, response in zip(tokens, responses):
        if getattr(response, 'success', False):
            continue
        saw_failure = True
        code = _error_code(getattr(response, 'exception', None))
        if code in _INVALID_TOKEN_CODES:
            invalid_tokens.add(token)
            classification = 'invalid_token'
        elif code in _RETRYABLE_CODES:
            classification = 'transient'
        else:
            classification = 'non_retryable'
            all_failures_retryable = False
        logger.warning(
            'FCM response failure: subject=%s code=%s classification=%s',
            subject,
            code or 'unknown',
            classification,
        )

    return invalid_tokens, saw_failure and all_failures_retryable


def send_fcm_to_user(user, *, notification, data, android=None, apns=None) -> dict:
    """Send FCM to a user's current tokens without exposing token values.

    Invalid tokens are removed only for FCM's token-specific invalidation
    codes. The return value carries a retry signal for a *complete* multicast
    failure caused solely by known transient service errors.
    """
    tokens = [entry['token'] for entry in (user.fcm_tokens or [])
              if entry.get('token')]
    subject = _correlation_id(user.id)
    if not tokens:
        logger.debug('No FCM token: subject=%s', subject)
        return _result()

    str_data = {key: str(value) for key, value in (data or {}).items()}
    message = messaging.MulticastMessage(
        notification=notification,
        data=str_data,
        tokens=tokens,
        android=android,
        apns=apns,
    )

    try:
        response = messaging.send_each_for_multicast(message)
    except Exception as exc:
        code = _error_code(exc)
        retryable = code in _RETRYABLE_CODES
        logger.warning(
            'FCM transport failure: subject=%s code=%s classification=%s',
            subject,
            code or 'unknown',
            'transient' if retryable else 'non_retryable',
        )
        return _result(failure=len(tokens), retryable=retryable)

    invalid_tokens, all_failures_retryable = _record_response_failures(
        tokens,
        response.responses,
        subject=subject,
    )
    purged = 0
    if invalid_tokens:
        original_count = len(user.fcm_tokens or [])
        user.fcm_tokens = [
            entry for entry in (user.fcm_tokens or [])
            if entry.get('token') not in invalid_tokens
        ]
        purged = original_count - len(user.fcm_tokens)
        user.save(update_fields=['fcm_tokens'])
        logger.info(
            'Purged invalid FCM tokens: subject=%s count=%s', subject, purged,
        )

    success = int(response.success_count)
    failure = int(response.failure_count)
    retryable = success == 0 and failure > 0 and all_failures_retryable
    logger.info(
        'FCM delivery: subject=%s success=%s failure=%s purged=%s retryable=%s',
        subject,
        success,
        failure,
        purged,
        retryable,
    )
    return _result(
        success=success,
        failure=failure,
        purged=purged,
        retryable=retryable,
    )
