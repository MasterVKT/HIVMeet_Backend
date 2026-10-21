"""Écriture du journal d'audit (seul point d'entrée).

- ``action`` doit figurer dans ``ALLOWED_ACTIONS`` (toute nouvelle action est
  ajoutée ici, avec sa phase).
- ``metadata`` est filtrée: clés en liste blanche, valeurs scalaires courtes.
  Jamais d'email, de jeton, de secret ni de donnée de santé.
- À appeler dans la transaction de l'action (``transaction.atomic``).
"""

from __future__ import annotations

import logging

from . import lockout
from .models import StaffAuditLog

logger = logging.getLogger('hivmeet.backoffice')

ALLOWED_ACTIONS = frozenset({
    # Phase 1 — authentification et barrière d'accès
    'auth.password_ok',
    'auth.login_failed',
    'auth.locked',
    'auth.logout',
    'auth.session_expired',
    'access.denied',
})

ALLOWED_METADATA_KEYS = frozenset({
    'reason_code',
    'identifier_hash',
    'kind',
    'path',
    'capability',
    'status',
    'count',
})

_MAX_VALUE_LENGTH = 128


def _clean_metadata(metadata: dict | None) -> dict:
    cleaned = {}
    for key, value in (metadata or {}).items():
        if key not in ALLOWED_METADATA_KEYS:
            logger.warning('audit metadata key dropped: %s', key)
            continue
        if isinstance(value, bool) or value is None or isinstance(value, int):
            cleaned[key] = value
        elif isinstance(value, str):
            cleaned[key] = value[:_MAX_VALUE_LENGTH]
        else:
            logger.warning('audit metadata value dropped for key: %s', key)
    return cleaned


def record(*, action: str, actor=None, request=None, target_type: str = '',
           target_id: str = '', reason: str = '', metadata: dict | None = None) -> StaffAuditLog:
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f'Unknown audit action: {action}')
    actor_ref = ''
    if actor is not None and getattr(actor, 'pk', None) is not None:
        actor_ref = str(actor.pk)
    else:
        actor = None
    return StaffAuditLog.objects.create(
        actor=actor,
        actor_ref=actor_ref,
        action=action,
        target_type=target_type[:32],
        target_id=str(target_id)[:64],
        reason=reason,
        metadata=_clean_metadata(metadata),
        ip_hash=lockout.ip_hash(request) if request is not None else '',
    )
