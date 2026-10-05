"""Regression tests for persisted Premium read-receipt alerts."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from matching.models import Match
from messaging.models import Message
from messaging.services import MessageService
from messaging.tasks import send_read_notification
from notifications.models import Notification
from subscriptions.utils import invalidate_premium_status_cache


User = get_user_model()


class PersistedReadAlertTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            email='read-alert-author@example.test',
            password='TestPass123!',
            display_name='Author',
            birth_date=date(1990, 1, 1),
        )
        self.reader = User.objects.create_user(
            email='read-alert-reader@example.test',
            password='TestPass123!',
            display_name='Reader',
            birth_date=date(1991, 1, 1),
        )
        self.match = Match.objects.create(
            user1=self.author,
            user2=self.reader,
            status=Match.ACTIVE,
        )

    def _make_author_premium(self, preference=None):
        self.author.is_premium = True
        self.author.premium_until = timezone.now() + timedelta(days=30)
        settings = {}
        if preference is not None:
            settings['message_read_notifications'] = preference
        self.author.notification_settings = settings
        self.author.save(update_fields=[
            'is_premium', 'premium_until', 'notification_settings',
        ])
        invalidate_premium_status_cache(self.author)

    def _mark_read(self, *messages):
        self.match.user2_unread_count = len(messages)
        self.match.save(update_fields=['user2_unread_count'])
        channel_layer = MagicMock()
        with patch('messaging.services.get_channel_layer', return_value=channel_layer), \
                patch('messaging.services.async_to_sync', side_effect=lambda fn: fn), \
                patch('messaging.services.send_read_notification.delay') as enqueue:
            with self.captureOnCommitCallbacks(execute=True):
                receipt = MessageService.mark_messages_as_read(
                    user=self.reader,
                    match=self.match,
                )
        return receipt, channel_layer, enqueue

    def test_missing_premium_preference_defaults_to_persisted_batch_alert(self):
        self._make_author_premium()
        message = Message.objects.create(
            match=self.match,
            sender=self.author,
            content='Private text must not enter the alert payload.',
            status=Message.SENT,
        )

        receipt, channel_layer, enqueue = self._mark_read(message)

        self.assertEqual(receipt.messages_marked, 1)
        alert = Notification.objects.get(user=self.author, type='message_read')
        self.assertEqual(alert.body, '')
        self.assertEqual(alert.data['conversation_id'], str(self.match.id))
        self.assertEqual(alert.data['reader_id'], str(self.reader.id))
        self.assertEqual(alert.data['representative_message_id'], str(message.id))
        self.assertEqual(alert.data['message_count'], 1)
        self.assertNotIn('content', alert.data)
        self.assertNotIn('preview', alert.data)
        enqueue.assert_called_once()
        self.assertEqual(enqueue.call_args.kwargs['notification_id'], str(alert.id))
        self.assertEqual(channel_layer.group_send.call_count, 3)
        self.assertEqual(
            channel_layer.group_send.call_args_list[-1].args[1]['type'],
            'message_read_alert',
        )

        _, _, second_enqueue = self._mark_read(message)
        self.assertEqual(Notification.objects.filter(
            user=self.author, type='message_read',
        ).count(), 1)
        second_enqueue.assert_not_called()

    def test_batch_creates_exactly_one_alert_with_batch_metadata(self):
        self._make_author_premium()
        first = Message.objects.create(
            match=self.match, sender=self.author, content='First', status=Message.SENT,
        )
        second = Message.objects.create(
            match=self.match, sender=self.author, content='Second', status=Message.SENT,
        )

        receipt, _, enqueue = self._mark_read(first, second)

        self.assertEqual(receipt.messages_marked, 2)
        alert = Notification.objects.get(user=self.author, type='message_read')
        self.assertEqual(alert.data['message_count'], 2)
        self.assertEqual(alert.data['representative_message_id'], str(second.id))
        enqueue.assert_called_once()

    def test_free_or_explicitly_opted_out_author_keeps_receipts_without_alert(self):
        message = Message.objects.create(
            match=self.match, sender=self.author, content='Unread', status=Message.SENT,
        )
        _, free_layer, free_enqueue = self._mark_read(message)
        self.assertEqual(free_layer.group_send.call_count, 2)
        free_enqueue.assert_not_called()
        self.assertFalse(Notification.objects.filter(type='message_read').exists())

        message.status = Message.SENT
        message.read_at = None
        message.save(update_fields=['status', 'read_at'])
        self._make_author_premium(preference=False)
        _, opt_out_layer, opt_out_enqueue = self._mark_read(message)
        self.assertEqual(opt_out_layer.group_send.call_count, 2)
        opt_out_enqueue.assert_not_called()
        self.assertFalse(Notification.objects.filter(type='message_read').exists())

    def test_fcm_uses_the_persisted_uuid_and_failure_keeps_the_alert(self):
        self._make_author_premium()
        self.author.fcm_tokens = [{'token': 'read-alert-token'}]
        self.author.save(update_fields=['fcm_tokens'])
        alert = Notification.objects.create(
            user=self.author,
            type='message_read',
            title='Message read',
            body='',
            data={
                'type': 'message_read',
                'notification_id': 'placeholder',
                'conversation_id': str(self.match.id),
                'reader_id': str(self.reader.id),
                'reader_name': self.reader.display_name,
                'representative_message_id': 'message-id',
                'message_count': 2,
                'read_at': timezone.now().isoformat(),
            },
        )

        with patch('messaging.tasks.send_fcm_to_user', side_effect=RuntimeError):
            send_read_notification(
                self.author.id,
                self.reader.id,
                str(self.match.id),
                'message-id',
                notification_id=str(alert.id),
            )

        self.assertTrue(Notification.objects.filter(id=alert.id).exists())

        with patch('messaging.tasks.send_fcm_to_user') as send_fcm:
            send_read_notification(
                self.author.id,
                self.reader.id,
                str(self.match.id),
                'message-id',
                notification_id=str(alert.id),
            )
        self.assertEqual(send_fcm.call_args.kwargs['data']['notification_id'], str(alert.id))
        self.assertEqual(send_fcm.call_args.kwargs['data']['message_count'], '2')
