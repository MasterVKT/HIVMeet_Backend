"""Wire contract for persistent Premium read alerts."""

from __future__ import annotations

import json

from asgiref.sync import async_to_sync
from django.test import TestCase

from .consumers import UserNotificationConsumer


class PersistedReadAlertConsumerTests(TestCase):
    def test_message_read_alert_keeps_the_canonical_notification_id(self):
        consumer = UserNotificationConsumer()
        sent = []

        async def capture(text_data=None, **kwargs):
            sent.append(json.loads(text_data))

        consumer.send = capture
        async_to_sync(consumer.message_read_alert)({
            'type': 'message_read_alert',
            'notification_id': '11111111-1111-5111-8111-111111111111',
            'conversation_id': 'conversation-id',
            'reader_id': 'reader-id',
            'reader_name': 'Reader',
            'representative_message_id': 'message-id',
            'message_count': 3,
            'read_at': '2026-09-28T12:00:00+00:00',
        })

        self.assertEqual(sent, [{
            'type': 'message_read',
            'notification_id': '11111111-1111-5111-8111-111111111111',
            'conversation_id': 'conversation-id',
            'reader_id': 'reader-id',
            'reader_name': 'Reader',
            'representative_message_id': 'message-id',
            'message_count': 3,
            'read_at': '2026-09-28T12:00:00+00:00',
        }])
