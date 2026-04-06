"""
WebSocket integration tests for real-time messaging.
"""

import uuid

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from authentication.models import User
from hivmeet_backend.asgi import application
from matching.models import Match
from messaging.models import Message


@override_settings(
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }
)
class WebSocketMessagingTests(TransactionTestCase):
    """Deterministic WebSocket tests for conversation events."""

    reset_sequences = True

    def setUp(self):
        self.user1 = User.objects.create_user(
            email="ws_user1@example.com",
            password="testpass123",
            display_name="WS User 1",
            birth_date=timezone.datetime(1995, 1, 1).date(),
            email_verified=True,
        )
        self.user2 = User.objects.create_user(
            email="ws_user2@example.com",
            password="testpass123",
            display_name="WS User 2",
            birth_date=timezone.datetime(1996, 1, 1).date(),
            email_verified=True,
        )
        self.user3 = User.objects.create_user(
            email="ws_user3@example.com",
            password="testpass123",
            display_name="WS User 3",
            birth_date=timezone.datetime(1997, 1, 1).date(),
            email_verified=True,
        )

        self.match = Match.objects.create(user1=self.user1, user2=self.user2, status=Match.ACTIVE)

    def _access_token(self, user: User) -> str:
        return str(RefreshToken.for_user(user).access_token)

    def test_connect_with_valid_header_token(self):
        async def scenario():
            token = self._access_token(self.user1)
            communicator = WebsocketCommunicator(
                application,
                f"/ws/conversations/{self.match.id}/",
                headers=[(b"authorization", f"Bearer {token}".encode())],
            )

            connected, response = await communicator.connect()
            self.assertTrue(connected)
            self.assertIsNone(response)
            await communicator.disconnect()

        async_to_sync(scenario)()

    def test_reject_connection_with_invalid_token(self):
        async def scenario():
            communicator = WebsocketCommunicator(
                application,
                f"/ws/conversations/{self.match.id}/",
                headers=[(b"authorization", b"Bearer invalid.token.value")],
            )

            connected, code = await communicator.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4000)

        async_to_sync(scenario)()

    def test_connect_with_query_token_fallback(self):
        async def scenario():
            token = self._access_token(self.user2)
            communicator = WebsocketCommunicator(
                application,
                f"/ws/conversations/{self.match.id}/?token={token}",
            )

            connected, response = await communicator.connect()
            self.assertTrue(connected)
            self.assertIsNone(response)
            await communicator.disconnect()

        async_to_sync(scenario)()

    def test_reject_user_outside_match(self):
        async def scenario():
            token = self._access_token(self.user3)
            communicator = WebsocketCommunicator(
                application,
                f"/ws/conversations/{self.match.id}/",
                headers=[(b"authorization", f"Bearer {token}".encode())],
            )

            connected, code = await communicator.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4001)

        async_to_sync(scenario)()

    def test_typing_events_are_broadcast_to_other_participant(self):
        async def scenario():
            token1 = self._access_token(self.user1)
            token2 = self._access_token(self.user2)

            comm1 = WebsocketCommunicator(
                application,
                f"/ws/conversations/{self.match.id}/",
                headers=[(b"authorization", f"Bearer {token1}".encode())],
            )
            comm2 = WebsocketCommunicator(
                application,
                f"/ws/conversations/{self.match.id}/",
                headers=[(b"authorization", f"Bearer {token2}".encode())],
            )

            connected1, _ = await comm1.connect()
            connected2, _ = await comm2.connect()
            self.assertTrue(connected1)
            self.assertTrue(connected2)

            await comm1.send_json_to({"type": "typing.start"})
            first_event = await comm2.receive_json_from(timeout=1)
            if first_event.get("type") == "presence.update":
                first_event = await comm2.receive_json_from(timeout=1)

            self.assertEqual(first_event["type"], "typing.indicator")
            self.assertEqual(first_event["status"], "typing")
            self.assertEqual(first_event["user_id"], str(self.user1.id))

            await comm1.send_json_to({"type": "typing.stop"})
            stop_event = await comm2.receive_json_from(timeout=1)
            self.assertEqual(stop_event["type"], "typing.indicator")
            self.assertEqual(stop_event["status"], "stopped")
            self.assertEqual(stop_event["user_id"], str(self.user1.id))

            try:
                await comm1.disconnect()
            except BaseException:
                pass
            try:
                await comm2.disconnect()
            except BaseException:
                pass

        async_to_sync(scenario)()

    def test_message_send_broadcasts_and_persists(self):
        async def scenario():
            token1 = self._access_token(self.user1)
            token2 = self._access_token(self.user2)
            client_message_id = str(uuid.uuid4())

            async def receive_until_message_created(communicator, timeout=10.0):
                deadline = timezone.now().timestamp() + timeout
                while timezone.now().timestamp() < deadline:
                    try:
                        event = await communicator.receive_json_from(timeout=2)
                    except BaseException:
                        continue
                    if event.get("type") == "message.created":
                        return event
                self.fail("Did not receive message.created event in time")

            comm1 = WebsocketCommunicator(
                application,
                f"/ws/conversations/{self.match.id}/",
                headers=[(b"authorization", f"Bearer {token1}".encode())],
            )
            comm2 = WebsocketCommunicator(
                application,
                f"/ws/conversations/{self.match.id}/",
                headers=[(b"authorization", f"Bearer {token2}".encode())],
            )

            connected1, _ = await comm1.connect()
            connected2, _ = await comm2.connect()
            self.assertTrue(connected1)
            self.assertTrue(connected2)

            await comm1.send_json_to(
                {
                    "type": "message.send",
                    "content": "Hello WebSocket",
                    "client_message_id": client_message_id,
                }
            )

            sender_deadline = timezone.now().timestamp() + 2.0
            while timezone.now().timestamp() < sender_deadline:
                try:
                    sender_event = await comm1.receive_json_from(timeout=1)
                except BaseException:
                    continue
                if sender_event.get("type") == "error":
                    self.fail(f"Sender received websocket error: {sender_event}")

            event_receiver = await receive_until_message_created(comm2)

            self.assertEqual(event_receiver["type"], "message.created")
            self.assertEqual(event_receiver["content"], "Hello WebSocket")
            self.assertEqual(event_receiver["sender_id"], str(self.user1.id))
            self.assertEqual(event_receiver["client_message_id"], client_message_id)

            try:
                await comm1.disconnect()
            except BaseException:
                pass
            try:
                await comm2.disconnect()
            except BaseException:
                pass

        async_to_sync(scenario)()

        messages = Message.objects.filter(
            match=self.match,
            sender=self.user1,
            content="Hello WebSocket",
        )
        self.assertEqual(messages.count(), 1)
