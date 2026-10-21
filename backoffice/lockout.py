"""Verrouillage par compteurs en cache (fenêtre fixe).

Les identifiants (email, IP) ne sont jamais stockés en clair: clés HMAC-hachées.
Le compteur est indépendant de l'existence du compte (pas d'énumération).
En production le cache doit être partagé (Redis): voir ``backoffice.checks``.
"""

from __future__ import annotations

import hashlib
import hmac

from django.conf import settings
from django.core.cache import cache


def _key_material(label: str) -> bytes:
    return hashlib.sha256(f'{settings.SECRET_KEY}|backoffice|{label}'.encode()).digest()


def hash_identifier(value: str) -> str:
    """HMAC-SHA256 tronqué de l'identifiant normalisé (minuscule, sans espaces)."""
    digest = hmac.new(_key_material('identifier'), value.strip().lower().encode(), hashlib.sha256)
    return digest.hexdigest()[:32]


def _cache_key(kind: str, identifier: str) -> str:
    return f'bo:lock:{kind}:{hash_identifier(identifier)}'


def failures(kind: str, identifier: str) -> int:
    return cache.get(_cache_key(kind, identifier), 0)


def is_locked(kind: str, identifier: str, limit: int) -> bool:
    return failures(kind, identifier) >= limit


def register_failure(kind: str, identifier: str, window: int) -> int:
    """Incrémente le compteur (la fenêtre démarre au premier échec)."""
    key = _cache_key(kind, identifier)
    cache.add(key, 0, timeout=window)
    try:
        return cache.incr(key)
    except ValueError:  # clé expirée entre add et incr
        cache.set(key, 1, timeout=window)
        return 1


def clear(kind: str, identifier: str) -> None:
    cache.delete(_cache_key(kind, identifier))


def client_ip(request) -> str:
    """Adresse du client. ``X-Forwarded-For`` n'est lue que si un proxy de
    confiance l'ajoute en dernier (``BACKOFFICE_TRUST_X_FORWARDED_FOR``)."""
    if settings.BACKOFFICE_TRUST_X_FORWARDED_FOR:
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if forwarded:
            return forwarded.split(',')[-1].strip()
    return request.META.get('REMOTE_ADDR', '') or 'unknown'


def ip_hash(request) -> str:
    digest = hmac.new(_key_material('ip'), client_ip(request).encode(), hashlib.sha256)
    return digest.hexdigest()[:32]
