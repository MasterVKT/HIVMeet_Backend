"""WebSocket media contract regression test for messaging remediation."""

from datetime import date
from unittest.mock import patch

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from authentication.models import User
from hivmeet_backend.asgi import application
from matching.models import Match
from messaging.models import Message


@override_settings(
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}
)
class WebSocketMediaRemediationTests(TransactionTestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            email='ws-media-sender@example.com',
            password='TestPass123!',
            display_name='Media Sender',
            birth_date=date(1990, 1, 1),
            email_verified=True,
        )
        self.recipient = User.objects.create_user(
            email='ws-media-recipient@example.com',
            password='TestPass123!',
            display_name='Media Recipient',
            birth_date=date(1991, 1, 1),
            email_verified=True,
        )
        self.match = Match.objects.create(
            user1=self.sender,
            user2=self.recipient,
            status=Match.ACTIVE,
        )

    def test_message_created_preserves_all_persisted_media_fields(self):
        async def scenario():
            token = str(RefreshToken.for_user(self.recipient).access_token)
            communicator = WebsocketCommunicator(
                application,
                f'/ws/conversations/{self.match.id}/',
                headers=[(b'authorization', f'Bearer {token}'.encode())],
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            with patch('messaging.signals.send_message_notification.delay'):
                message = await database_sync_to_async(Message.objects.create)(
                    match=self.match,
                    sender=self.sender,
                    content='Media caption',
                    message_type=Message.IMAGE,
                    media_url='https://media.example.test/messages/image.jpg',
                    media_thumbnail_url='https://media.example.test/messages/image-thumb.jpg',
                    client_message_id='websocket-media-client-id',
                )

            event = None
            for _ in range(5):
                candidate = await communicator.receive_json_from(timeout=2)
                if candidate.get('type') == 'message.created':
                    event = candidate
                    break
            self.assertIsNotNone(event)
            self.assertEqual(event['message_id'], str(message.id))
            self.assertEqual(event['media_url'], message.media_url)
            self.assertEqual(event['media_type'], Message.IMAGE)
            self.assertEqual(event['media_thumbnail_url'], message.media_thumbnail_url)
            await communicator.disconnect()

        async_to_sync(scenario)()
