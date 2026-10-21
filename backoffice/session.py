"""État de session du back-office.

Clés (toutes dans la session Django du back-office, cookie ``bo_sessionid``):

- ``bo_pending_uid`` / ``bo_pending_at`` : mot de passe validé, TOTP en attente.
  L'utilisateur n'est **pas** authentifié à ce stade (pas de ``login()``).
- ``bo_auth_at``  : début de la session authentifiée (plafond absolu).
- ``bo_mfa_at``   : dernière vérification TOTP (step-up).
- ``bo_last_seen``: dernière activité (inactivité).

La session authentifiée n'est créée qu'à l'étape TOTP (Phase 2): tant qu'elle
n'existe pas, aucune vue protégée n'est atteignable.
"""

from __future__ import annotations

from django.conf import settings

KEY_PENDING_UID = 'bo_pending_uid'
KEY_PENDING_AT = 'bo_pending_at'
KEY_AUTH_AT = 'bo_auth_at'
KEY_MFA_AT = 'bo_mfa_at'
KEY_LAST_SEEN = 'bo_last_seen'

OK = 'ok'
EXPIRED = 'expired'
MFA_REQUIRED = 'mfa_required'


def session_status(session, now: float) -> str:
    """``mfa_required`` sans preuve MFA, ``expired`` si inactif ou trop ancien."""
    auth_at = session.get(KEY_AUTH_AT)
    mfa_at = session.get(KEY_MFA_AT)
    last_seen = session.get(KEY_LAST_SEEN)
    if auth_at is None or mfa_at is None or last_seen is None:
        return MFA_REQUIRED
    if now - last_seen > settings.BACKOFFICE_IDLE_SECONDS:
        return EXPIRED
    if now - auth_at > settings.BACKOFFICE_MAX_SESSION_SECONDS:
        return EXPIRED
    return OK


def touch(session, now: float) -> None:
    session[KEY_LAST_SEEN] = int(now)


def step_up_fresh(session, now: float) -> bool:
    """Vrai si le dernier TOTP date de moins de ``BACKOFFICE_STEP_UP_SECONDS``."""
    mfa_at = session.get(KEY_MFA_AT)
    return mfa_at is not None and now - mfa_at <= settings.BACKOFFICE_STEP_UP_SECONDS


def set_pending(session, user_id, now: float) -> None:
    session[KEY_PENDING_UID] = str(user_id)
    session[KEY_PENDING_AT] = int(now)


def pending_user_id(session, now: float) -> str | None:
    uid = session.get(KEY_PENDING_UID)
    at = session.get(KEY_PENDING_AT)
    if uid is None or at is None:
        return None
    if now - at > settings.BACKOFFICE_PENDING_SECONDS:
        return None
    return uid


def clear_pending(session) -> None:
    session.pop(KEY_PENDING_UID, None)
    session.pop(KEY_PENDING_AT, None)
