from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from matching.models import Match
from messaging.presence import PresenceService
from messaging.services import _recipient_has_active_client


User = get_user_model()


class PresenceServiceContractTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(
            email='viewer-presence@example.test',
            password='testpass123',
            display_name='Viewer',
            birth_date=timezone.localdate() - timedelta(days=30 * 365),
        )
        self.subject = User.objects.create_user(
            email='subject-presence@example.test',
            password='testpass123',
            display_name='Subject',
            birth_date=timezone.localdate() - timedelta(days=31 * 365),
        )
        self.match = Match.objects.create(user1=self.subject, user2=self.viewer)
        self.client = APIClient()
        self.client.force_authenticate(self.viewer)
        self.subject.profile.show_online_status = True
        self.subject.profile.save(update_fields=['show_online_status'])

    def test_two_device_sessions_keep_presence_online_until_last_disconnect(self):
        PresenceService.heartbeat(self.subject, 'device-a')
        PresenceService.heartbeat(self.subject, 'device-b')

        PresenceService.disconnect(self.subject, 'device-a')
        snapshot = PresenceService.snapshot_for(self.subject)

        self.assertTrue(snapshot['visibility'])
        self.assertTrue(snapshot['is_online'])
        self.assertTrue(_recipient_has_active_client(self.subject.id, self.match.id))

        PresenceService.disconnect(self.subject, 'device-b')
        snapshot = PresenceService.snapshot_for(self.subject)
        self.assertFalse(snapshot['is_online'])

    def test_expired_heartbeat_is_offline_after_ninety_seconds(self):
        PresenceService.heartbeat(self.subject, 'device-a')
        self.subject.presence_sessions.update(
            last_heartbeat_at=timezone.now() - timedelta(seconds=91)
        )

        self.assertFalse(PresenceService.is_online(self.subject))

    def test_hidden_status_never_exposes_last_seen(self):
        PresenceService.heartbeat(self.subject, 'device-a')
        self.subject.profile.show_online_status = False
        self.subject.profile.save(update_fields=['show_online_status'])

        response = self.client.get(
            f'/api/v1/conversations/{self.match.id}/presence/'
        )

        self.assertEqual(response.status_code, 200)
        participant = response.data['participant']
        self.assertFalse(participant['visibility'])
        self.assertFalse(participant['is_online'])
        self.assertIsNone(participant['last_active'])
        self.assertIn('server_timestamp', response.data)

    def test_event_payload_uses_the_canonical_privacy_safe_shape(self):
        PresenceService.heartbeat(self.subject, 'device-a')

        payload = PresenceService.event_payload(self.subject)

        self.assertEqual(
            set(payload),
            {
                'user_id',
                'visibility',
                'is_online',
                'last_active',
                'server_timestamp',
            },
        )
        self.assertEqual(payload['user_id'], str(self.subject.id))
        self.assertTrue(payload['visibility'])
        self.assertTrue(payload['is_online'])
