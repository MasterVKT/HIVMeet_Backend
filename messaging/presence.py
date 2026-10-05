"""Single server-authoritative presence service.

Presence is an account-level aggregation of foreground device sessions. A
connection refreshes its own row every 30 seconds; rows are considered online
for 90 seconds. Consumers never expose a device identifier and always apply
the profile owner's visibility preference before returning a snapshot.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .models import DevicePresenceSession

User = get_user_model()


class PresenceService:
    HEARTBEAT_INTERVAL_SECONDS = 30
    EXPIRY_SECONDS = 90
    _RETENTION = timedelta(days=7)

    @classmethod
    def _cutoff(cls):
        return timezone.now() - timedelta(seconds=cls.EXPIRY_SECONDS)

    @classmethod
    def heartbeat(cls, user, session_id: str) -> dict[str, Any]:
        """Record one foreground-device heartbeat and return its snapshot."""
        if not session_id:
            raise ValueError('A presence session id is required.')

        now = timezone.now()
        with transaction.atomic():
            # Lock the account as a stable serialization point for concurrent
            # notification and conversation sockets belonging to one user.
            locked_user = User.objects.select_for_update().get(pk=user.pk)
            session, created = DevicePresenceSession.objects.get_or_create(
                user=locked_user,
                session_id=session_id,
                defaults={
                    'last_heartbeat_at': now,
                    'disconnected_at': None,
                },
            )
            if not created:
                DevicePresenceSession.objects.filter(pk=session.pk).update(
                    last_heartbeat_at=now,
                    disconnected_at=None,
                )
            User.objects.filter(pk=locked_user.pk).update(last_active=now)

            # Rows are retained briefly for an accurate last-seen value,
            # then pruned during normal traffic. No client sees session ids.
            DevicePresenceSession.objects.filter(
                user=locked_user,
                disconnected_at__lt=now - cls._RETENTION,
            ).delete()

        return cls.snapshot_for(locked_user)

    @classmethod
    def disconnect(cls, user, session_id: str) -> dict[str, Any]:
        """End exactly one device session without affecting sibling devices."""
        if not session_id:
            return cls.snapshot_for(user)

        now = timezone.now()
        DevicePresenceSession.objects.filter(
            user=user,
            session_id=session_id,
            disconnected_at__isnull=True,
        ).update(disconnected_at=now, last_heartbeat_at=now)
        User.objects.filter(pk=user.pk).update(last_active=now)
        return cls.snapshot_for(user)

    @classmethod
    def is_online(cls, user) -> bool:
        return DevicePresenceSession.objects.filter(
            user=user,
            disconnected_at__isnull=True,
            last_heartbeat_at__gte=cls._cutoff(),
        ).exists()

    @classmethod
    def snapshot_for(cls, subject) -> dict[str, Any]:
        """Return the privacy-safe presence shape used by REST and WebSocket."""
        now = timezone.now()
        profile = getattr(subject, 'profile', None)
        visible = bool(profile and profile.show_online_status)
        if not visible:
            return {
                'visibility': False,
                'is_online': False,
                'last_active': None,
                'server_timestamp': now,
            }

        sessions = DevicePresenceSession.objects.filter(user=subject)
        last_active = sessions.aggregate(last=Max('last_heartbeat_at'))['last']
        is_online = sessions.filter(
            disconnected_at__isnull=True,
            last_heartbeat_at__gte=now - timedelta(seconds=cls.EXPIRY_SECONDS),
        ).exists()
        return {
            'visibility': True,
            'is_online': is_online,
            'last_active': last_active,
            'server_timestamp': now,
        }

    @classmethod
    def event_payload(cls, subject) -> dict[str, Any]:
        """Canonical WebSocket payload. It contains no private device facts."""
        snapshot = cls.snapshot_for(subject)
        return {
            'user_id': str(subject.pk),
            'visibility': snapshot['visibility'],
            'is_online': snapshot['is_online'],
            'last_active': (
                snapshot['last_active'].isoformat()
                if snapshot['last_active'] is not None
                else None
            ),
            'server_timestamp': snapshot['server_timestamp'].isoformat(),
        }
