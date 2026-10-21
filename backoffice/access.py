"""Capacités du back-office et barrière d'accès.

Les capacités sont des **constantes de code**, pas des permissions Django:
``has_perm`` accorde tout à un superuser, ce qui violerait la règle « aucun accès
implicite » (en particulier pour le KYC). Un superuser sans groupe n'a rien.

Barrière complète (``evaluate_gate``), dans cet ordre :
authentifié + actif + staff → session MFA vérifiée et non expirée → capacité.
"""

from __future__ import annotations

import enum
import time

from . import roles, session as bo_session
from .roles import (
    GROUP_ADMIN, GROUP_KYC_REVIEWER, GROUP_KYC_SUPERVISOR, GROUP_MODERATOR, GROUP_SUPPORT,
)

# ── Capacités ────────────────────────────────────────────────────────────────
DASHBOARD = 'dashboard'
USERS_VIEW = 'users.view'
USERS_VIEW_PII = 'users.view_pii'
USERS_DEACTIVATE = 'users.deactivate'
USERS_REACTIVATE = 'users.reactivate'
STAFF_MANAGE = 'staff.manage'
REPORTS_MANAGE = 'reports.manage'
MODERATION_FEED = 'moderation.feed'
MODERATION_PHOTOS = 'moderation.photos'
CMS_EDIT = 'cms.edit'
PAYMENTS_VIEW = 'payments.view'
PAYMENTS_RECONCILE = 'payments.reconcile'
PAYMENTS_FULFIL_DEFERRED = 'payments.fulfil_deferred'
GDPR_VIEW = 'gdpr.view'
GDPR_ACT = 'gdpr.act'
AUDIT_VIEW = 'audit.view'
KYC_REVIEW = 'kyc.review'
KYC_SUPERVISE = 'kyc.supervise'

_ALL_STAFF = frozenset({
    GROUP_ADMIN, GROUP_MODERATOR, GROUP_SUPPORT, GROUP_KYC_REVIEWER, GROUP_KYC_SUPERVISOR,
})
_ADMIN = frozenset({GROUP_ADMIN})
_ADMIN_MOD = frozenset({GROUP_ADMIN, GROUP_MODERATOR})
_ADMIN_SUPPORT = frozenset({GROUP_ADMIN, GROUP_SUPPORT})

# Matrice capacité → groupes autorisés (voir skill ``backoffice-security``).
CAPABILITY_GROUPS: dict[str, frozenset[str]] = {
    DASHBOARD: _ALL_STAFF,
    USERS_VIEW: frozenset({GROUP_ADMIN, GROUP_MODERATOR, GROUP_SUPPORT}),
    USERS_VIEW_PII: _ADMIN,
    USERS_DEACTIVATE: _ADMIN_MOD,
    USERS_REACTIVATE: _ADMIN,
    STAFF_MANAGE: _ADMIN,
    REPORTS_MANAGE: _ADMIN_MOD,
    MODERATION_FEED: _ADMIN_MOD,
    MODERATION_PHOTOS: _ADMIN_MOD,
    CMS_EDIT: _ADMIN_MOD,
    PAYMENTS_VIEW: _ADMIN_SUPPORT,
    PAYMENTS_RECONCILE: _ADMIN_SUPPORT,
    PAYMENTS_FULFIL_DEFERRED: _ADMIN,
    GDPR_VIEW: _ADMIN_SUPPORT,
    GDPR_ACT: _ADMIN,
    AUDIT_VIEW: _ADMIN,
    KYC_REVIEW: frozenset({GROUP_KYC_REVIEWER, GROUP_KYC_SUPERVISOR}),
    KYC_SUPERVISE: frozenset({GROUP_KYC_SUPERVISOR}),
}


def has_capability(user, capability: str) -> bool:
    """Vrai si ``user`` (actif, staff) appartient à un groupe autorisé.

    Un superuser n'a **aucun** accès implicite.
    """
    if not (user.is_authenticated and user.is_active and user.is_staff):
        return False
    allowed = CAPABILITY_GROUPS.get(capability)
    if not allowed:
        return False
    return bool(allowed & roles.user_groups(user))


# ── Politique des vues (deny by default) ─────────────────────────────────────
PUBLIC = 'public'


def public_view(view):
    """Marque une vue accessible sans barrière (connexion, MFA, déconnexion)."""
    view.backoffice_public = True
    return view


def requires(capability: str):
    """Décorateur de vue fonction: déclare la capacité requise."""
    def decorator(view):
        view.backoffice_capability = capability
        return view
    return decorator


class BackofficeView:
    """Mixin pour vues basées sur classes: déclarer ``capability``.

    Une vue sans ``capability`` (et non publique) est refusée par le middleware.
    """

    capability: str | None = None


def view_policy(view_func) -> str | None:
    """``PUBLIC``, le nom d'une capacité, ou ``None`` (vue non classée → refus)."""
    # ``as_view()`` renvoie une fonction portant ``view_class``: lire les deux.
    candidates = [view_func]
    view_class = getattr(view_func, 'view_class', None)
    if view_class is not None:
        candidates.append(view_class)
    for obj in candidates:
        if getattr(obj, 'backoffice_public', False):
            return PUBLIC
    for obj in candidates:
        capability = getattr(obj, 'capability', None) or getattr(obj, 'backoffice_capability', None)
        if capability:
            return capability
    return None


# ── Barrière ─────────────────────────────────────────────────────────────────
class Gate(enum.Enum):
    OK = 'ok'
    ANONYMOUS = 'anonymous'
    FORBIDDEN = 'forbidden'
    MFA_REQUIRED = 'mfa_required'
    SESSION_EXPIRED = 'session_expired'


def evaluate_gate(request, capability: str, now: float | None = None) -> Gate:
    user = request.user
    if not user.is_authenticated:
        return Gate.ANONYMOUS
    if not (user.is_active and user.is_staff):
        return Gate.FORBIDDEN
    state = bo_session.session_status(request.session, time.time() if now is None else now)
    if state == bo_session.EXPIRED:
        return Gate.SESSION_EXPIRED
    if state == bo_session.MFA_REQUIRED:
        return Gate.MFA_REQUIRED
    if not has_capability(user, capability):
        return Gate.FORBIDDEN
    return Gate.OK
