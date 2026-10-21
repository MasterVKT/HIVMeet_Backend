"""Groupes du back-office.

Les groupes ``kyc_reviewer`` / ``kyc_supervisor`` existent déjà (migration
``profiles.0014``) et gardent leur sémantique d'origine. Les noms sont
dupliqués ici sous forme de littéraux pour ne pas coupler ce module au code de
l'application; un test vérifie qu'ils restent identiques.
"""

from __future__ import annotations

from django.contrib.auth.models import Group

GROUP_ADMIN = 'backoffice_admin'
GROUP_MODERATOR = 'backoffice_moderator'
GROUP_SUPPORT = 'backoffice_support'
GROUP_KYC_REVIEWER = 'kyc_reviewer'
GROUP_KYC_SUPERVISOR = 'kyc_supervisor'

# Groupes créés par ``backoffice`` (les groupes KYC appartiennent à ``profiles``).
OWNED_GROUPS = (GROUP_ADMIN, GROUP_MODERATOR, GROUP_SUPPORT)
ALL_GROUPS = OWNED_GROUPS + (GROUP_KYC_REVIEWER, GROUP_KYC_SUPERVISOR)


def ensure_backoffice_groups() -> None:
    """Crée les groupes propres au back-office (idempotent).

    Source unique partagée par la migration de données et les tests, car les
    migrations sont désactivées dans ``test_settings``.
    """
    for name in OWNED_GROUPS:
        Group.objects.get_or_create(name=name)


def user_groups(user) -> frozenset[str]:
    """Noms des groupes *du back-office* de ``user`` (mis en cache sur l'objet)."""
    if not getattr(user, 'is_authenticated', False):
        return frozenset()
    cached = getattr(user, '_bo_groups', None)
    if cached is None:
        names = user.groups.filter(name__in=ALL_GROUPS).values_list('name', flat=True)
        cached = frozenset(names)
        user._bo_groups = cached
    return cached
