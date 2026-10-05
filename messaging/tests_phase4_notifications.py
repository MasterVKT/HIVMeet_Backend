"""Phase 4 regression tests for message push delivery."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from matching.models import Match
from messaging.presence import PresenceService
from messaging.tasks import FCMTemporaryDeliveryError, send_message_notification

User = get_user_model()


class MessagePushTaskContractTests(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            email='phase4-sender@example.test',
            password='testpass123',
            display_name='Sender',
            birth_date=timezone.localdate() - timedelta(days=30 * 365),
        )
        self.recipient = User.objects.create_user(
            email='phase4-recipient@example.test',
            password='testpass123',
            display_name='Recipient',
            birth_date=timezone.localdate() - timedelta(days=30 * 365),
        )
        self.match = Match.objects.create(user1=self.sender, user2=self.recipient)
        self.recipient.fcm_tokens = [{'token': 'phase4-token'}]
        self.recipient.save(update_fields=['fcm_tokens'])

    def _send(self):
        return send_message_notification(
            self.recipient.id,
            self.sender.id,
            'A private preview',
            str(self.match.id),
            message_id='message-phase4',
            notification_id='notification-phase4',
        )

    @patch('messaging.tasks.send_fcm_to_user')
    def test_online_recipient_still_receives_push(self, send_fcm):
        """General presence must never be mistaken for an open conversation."""
        PresenceService.heartbeat(self.recipient, 'phase4-online-device')
        send_fcm.return_value = {
            'success': 1,
            'failure': 0,
            'purged': 0,
            'retryable': False,
        }

        self._send()

        send_fcm.assert_called_once()
        self.assertEqual(send_fcm.call_args.args[0].id, self.recipient.id)
        self.assertEqual(
            send_fcm.call_args.kwargs['data']['conversation_id'], str(self.match.id)
        )

    @patch('messaging.tasks.send_fcm_to_user')
    def test_message_preference_still_blocks_push(self, send_fcm):
        self.recipient.notification_settings = {'new_message_notifications': False}
        self.recipient.save(update_fields=['notification_settings'])

        self._send()

        send_fcm.assert_not_called()

    @patch('messaging.tasks.send_fcm_to_user')
    def test_known_temporary_failure_uses_bounded_retry(self, send_fcm):
        send_fcm.return_value = {
            'success': 0,
            'failure': 1,
            'purged': 0,
            'retryable': True,
        }
        with patch.object(
            send_message_notification,
            'retry',
            side_effect=FCMTemporaryDeliveryError('scheduled'),
        ) as retry:
            with self.assertRaises(FCMTemporaryDeliveryError):
                self._send()

        retry.assert_called_once()
        self.assertEqual(retry.call_args.kwargs['countdown'], 2)
