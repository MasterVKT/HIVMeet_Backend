"""Regression coverage for the 2026-07-26 messaging remediation plan."""

from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, close_old_connections
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from matching.models import Match
from messaging.consumers import ConversationConsumer
from messaging.models import ConversationHiddenState, Message
from messaging.services import MessageService
from notifications.consumers import UserNotificationConsumer
from profiles.models import KycAttempt


User = get_user_model()


@override_settings(
    SECURE_SSL_REDIRECT=False,
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
)
class MessagingRemediationApiTests(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            email='remediation-u1@example.com',
            password='TestPass123!',
            display_name='Remediation User One',
            birth_date=date(1990, 1, 1),
        )
        self.user2 = User.objects.create_user(
            email='remediation-u2@example.com',
            password='TestPass123!',
            display_name='Remediation User Two',
            birth_date=date(1991, 1, 1),
        )
        self.user3 = User.objects.create_user(
            email='remediation-u3@example.com',
            password='TestPass123!',
            display_name='Remediation User Three',
            birth_date=date(1992, 1, 1),
        )
        self.match = Match.objects.create(
            user1=self.user1,
            user2=self.user2,
            status=Match.ACTIVE,
        )
        for user in (self.user1, self.user2, self.user3):
            KycAttempt.objects.create(
                user=user,
                status=KycAttempt.VERIFIED,
                is_open=False,
                expires_at=timezone.now() + timedelta(days=1),
            )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _messages_url(self, conversation_id=None):
        return reverse(
            'api:messaging:conversation-messages',
            kwargs={'conversation_id': conversation_id or self.match.id},
        )

    def test_list_and_message_query_parameters_are_strictly_validated(self):
        self._auth(self.user1)
        list_url = reverse('api:messaging:conversation-list')
        for query in (
            {'status': 'unexpected'},
            {'page': 0},
            {'page_size': 'abc'},
        ):
            response = self.client.get(list_url, query)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn('error', response.data)
            self.assertIn('details', response.data)

        for query in (
            {'limit': 0},
            {'page_size': 'abc'},
            {'before_message_id': 'not-a-uuid'},
        ):
            response = self.client.get(self._messages_url(), query)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn('error', response.data)
            self.assertIn('details', response.data)

    def test_partial_read_recalculates_exact_unread_count_and_keeps_unread_list(self):
        first = Message.objects.create(
            match=self.match,
            sender=self.user1,
            content='First incoming',
            status=Message.SENT,
        )
        second = Message.objects.create(
            match=self.match,
            sender=self.user1,
            content='Second incoming',
            status=Message.SENT,
        )
        base_time = timezone.now()
        Message.objects.filter(pk=first.pk).update(created_at=base_time)
        Message.objects.filter(pk=second.pk).update(created_at=base_time + timedelta(seconds=1))
        self.match.user2_unread_count = 2
        self.match.last_message_at = base_time + timedelta(seconds=1)
        self.match.save(update_fields=['user2_unread_count', 'last_message_at'])

        self._auth(self.user2)
        read_url = reverse('api:messaging:mark-as-read', kwargs={'conversation_id': self.match.id})
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.put(
                read_url,
                {'last_read_message_id': str(first.id)},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['messages_marked'], 1)
        self.assertEqual(response.data['unread_count_for_me'], 1)
        first.refresh_from_db()
        second.refresh_from_db()
        self.match.refresh_from_db()
        self.assertEqual(first.status, Message.READ)
        self.assertEqual(second.status, Message.SENT)
        self.assertEqual(self.match.user2_unread_count, 1)

        unread_response = self.client.get(
            reverse('api:messaging:conversation-list'),
            {'status': 'unread'},
        )
        self.assertEqual(unread_response.status_code, status.HTTP_200_OK)
        self.assertEqual(unread_response.data['count'], 1)

    def test_read_cursor_from_sender_is_rejected_without_state_change(self):
        incoming = Message.objects.create(
            match=self.match,
            sender=self.user1,
            content='Incoming',
            status=Message.SENT,
        )
        own_message = Message.objects.create(
            match=self.match,
            sender=self.user2,
            content='Own message',
            status=Message.SENT,
        )
        self.match.user2_unread_count = 1
        self.match.save(update_fields=['user2_unread_count'])

        self._auth(self.user2)
        response = self.client.put(
            reverse('api:messaging:mark-as-read', kwargs={'conversation_id': self.match.id}),
            {'last_read_message_id': str(own_message.id)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        incoming.refresh_from_db()
        self.match.refresh_from_db()
        self.assertEqual(incoming.status, Message.SENT)
        self.assertEqual(self.match.user2_unread_count, 1)

    def test_equal_timestamps_have_stable_disjoint_conversation_pages(self):
        second_match = Match.objects.create(
            user1=self.user1,
            user2=self.user3,
            status=Match.ACTIVE,
        )
        Message.objects.create(match=self.match, sender=self.user2, content='One')
        Message.objects.create(match=second_match, sender=self.user3, content='Two')
        same_time = timezone.now()
        Match.objects.filter(pk__in=[self.match.pk, second_match.pk]).update(
            last_message_at=same_time
        )

        self._auth(self.user1)
        list_url = reverse('api:messaging:conversation-list')
        first_page = self.client.get(list_url, {'page': 1, 'page_size': 1})
        second_page = self.client.get(list_url, {'page': 2, 'page_size': 1})

        self.assertEqual(first_page.status_code, status.HTTP_200_OK)
        self.assertEqual(second_page.status_code, status.HTTP_200_OK)
        first_id = first_page.data['results'][0]['conversation_id']
        second_id = second_page.data['results'][0]['conversation_id']
        self.assertNotEqual(first_id, second_id)
        self.assertEqual(first_page.data['next'].split('page=')[1][0], '2')

    def test_idempotency_key_is_scoped_to_match_sender_and_reveals_media_conversation(self):
        first, first_error = MessageService.send_message(
            sender=self.user1,
            match=self.match,
            content='First sender',
            client_message_id='shared-client-id',
        )
        second, second_error = MessageService.send_message(
            sender=self.user2,
            match=self.match,
            content='Second sender',
            client_message_id='shared-client-id',
        )
        self.assertIsNone(first_error)
        self.assertIsNone(second_error)
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(
            Message.objects.filter(match=self.match, client_message_id='shared-client-id').count(),
            2,
        )

        ConversationHiddenState.objects.create(match=self.match, user=self.user2)
        with patch(
            'messaging.services.check_feature_availability',
            return_value={'available': True, 'reason': 'ok'},
        ):
            media, media_error = MessageService.send_message(
                sender=self.user1,
                match=self.match,
                content='',
                message_type=Message.IMAGE,
                media_file_path='messages/test-image.jpg',
                media_url='/media/messages/test-image.jpg',
                client_message_id='media-reappearance',
            )
        self.assertIsNone(media_error)
        self.assertEqual(media.message_type, Message.IMAGE)
        self.assertFalse(
            ConversationHiddenState.objects.filter(match=self.match, user=self.user2).exists()
        )


@override_settings(
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}
)
class MessagingRemediationTransactionTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.sender = User.objects.create_user(
            email='rollback-sender@example.com',
            password='TestPass123!',
            display_name='Rollback Sender',
            birth_date=date(1990, 1, 1),
        )
        self.recipient = User.objects.create_user(
            email='rollback-recipient@example.com',
            password='TestPass123!',
            display_name='Rollback Recipient',
            birth_date=date(1991, 1, 1),
        )
        self.match = Match.objects.create(
            user1=self.sender,
            user2=self.recipient,
            status=Match.ACTIVE,
        )

    def test_failed_business_write_rolls_back_message_counter_visibility_and_dispatch(self):
        with patch(
            'messaging.services.ConversationHiddenState.objects.filter',
            side_effect=RuntimeError('injected business failure'),
        ), patch('messaging.signals.dispatch_new_message_after_commit') as dispatch:
            with self.assertRaises(RuntimeError):
                MessageService.send_message(
                    sender=self.sender,
                    match=self.match,
                    content='Must not commit',
                    client_message_id='rollback-client-id',
                )

        self.match.refresh_from_db()
        self.assertFalse(Message.objects.filter(match=self.match).exists())
        self.assertEqual(self.match.user2_unread_count, 0)
        self.assertIsNone(self.match.last_message_at)
        self.assertFalse(
            ConversationHiddenState.objects.filter(match=self.match, user=self.recipient).exists()
        )
        dispatch.assert_not_called()


@override_settings(
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}
)
class DeliveryReceiptWebSocketTests(TransactionTestCase):
    """End-to-end coverage of the ``delivered`` transition over real sockets.

    Uses ``TransactionTestCase`` because both consumers reach the database
    through ``database_sync_to_async``, i.e. from a worker thread that would
    not see the uncommitted data of a plain ``TestCase``.
    """

    reset_sequences = True

    def setUp(self):
        self.sender = User.objects.create_user(
            email='delivery-sender@example.com',
            password='TestPass123!',
            display_name='Delivery Sender',
            birth_date=date(1990, 1, 1),
        )
        self.recipient = User.objects.create_user(
            email='delivery-recipient@example.com',
            password='TestPass123!',
            display_name='Delivery Recipient',
            birth_date=date(1991, 1, 1),
        )
        self.match = Match.objects.create(
            user1=self.sender, user2=self.recipient, status=Match.ACTIVE
        )
        for user in (self.sender, self.recipient):
            KycAttempt.objects.create(
                user=user,
                status=KycAttempt.VERIFIED,
                is_open=False,
                expires_at=timezone.now() + timedelta(days=1),
            )
        self.message = Message.objects.create(
            match=self.match,
            sender=self.sender,
            content='Hello',
            status=Message.SENT,
        )

    def _token(self, user):
        return str(AccessToken.for_user(user))

    def test_conversation_socket_connect_marks_incoming_delivered(self):
        async def scenario():
            communicator = WebsocketCommunicator(
                ConversationConsumer.as_asgi(),
                f"/ws/conversations/{self.match.id}/?token={self._token(self.recipient)}",
            )
            communicator.scope['url_route'] = {
                'kwargs': {'conversation_id': str(self.match.id)}
            }
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.disconnect()

        async_to_sync(scenario)()

        self.message.refresh_from_db()
        self.assertEqual(self.message.status, Message.DELIVERED)
        self.assertIsNotNone(self.message.delivered_at)

    def test_notifications_socket_connect_marks_incoming_delivered(self):
        async def scenario():
            communicator = WebsocketCommunicator(
                UserNotificationConsumer.as_asgi(),
                f"/ws/notifications/?token={self._token(self.recipient)}",
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.disconnect()

        async_to_sync(scenario)()

        self.message.refresh_from_db()
        self.assertEqual(self.message.status, Message.DELIVERED)

    def test_notifications_socket_answers_ping_with_pong(self):
        async def scenario():
            communicator = WebsocketCommunicator(
                UserNotificationConsumer.as_asgi(),
                f"/ws/notifications/?token={self._token(self.recipient)}",
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.send_json_to({'type': 'ping'})
            response = await communicator.receive_json_from(timeout=5)
            await communicator.disconnect()
            return response

        response = async_to_sync(scenario)()
        self.assertEqual(response['type'], 'pong')
        self.assertIn('timestamp', response)

    def test_notifications_socket_rejects_connection_without_token(self):
        async def scenario():
            communicator = WebsocketCommunicator(
                UserNotificationConsumer.as_asgi(), "/ws/notifications/"
            )
            connected, _ = await communicator.connect()
            await communicator.disconnect()
            return connected

        self.assertFalse(async_to_sync(scenario)())

    def test_sender_receives_delivery_receipt_on_personal_group(self):
        """The author's ticks must flip without the chat being open."""

        async def scenario():
            sender_socket = WebsocketCommunicator(
                UserNotificationConsumer.as_asgi(),
                f"/ws/notifications/?token={self._token(self.sender)}",
            )
            connected, _ = await sender_socket.connect()
            self.assertTrue(connected)

            recipient_socket = WebsocketCommunicator(
                UserNotificationConsumer.as_asgi(),
                f"/ws/notifications/?token={self._token(self.recipient)}",
            )
            connected, _ = await recipient_socket.connect()
            self.assertTrue(connected)

            received = await sender_socket.receive_json_from(timeout=5)
            await sender_socket.disconnect()
            await recipient_socket.disconnect()
            return received

        event = async_to_sync(scenario)()
        self.assertEqual(event['type'], 'message_delivered')
        self.assertEqual(event['conversation_id'], str(self.match.id))
        self.assertEqual(event['message_ids'], [str(self.message.id)])

    def test_database_constraint_rejects_duplicate_idempotency_key_for_same_sender(self):
        Message.objects.create(
            match=self.match,
            sender=self.sender,
            content='First',
            client_message_id='database-unique-key',
        )
        with self.assertRaises(IntegrityError):
            Message.objects.create(
                match=self.match,
                sender=self.sender,
                content='Duplicate',
                client_message_id='database-unique-key',
            )

    @skipUnless(connection.vendor == 'postgresql', 'requires PostgreSQL row locking')
    def test_concurrent_same_client_retry_creates_one_message_and_one_increment(self):
        barrier = Barrier(2)

        def send_retry():
            close_old_connections()
            try:
                sender = User.objects.get(pk=self.sender.pk)
                match = Match.objects.get(pk=self.match.pk)
                barrier.wait(timeout=10)
                message, error = MessageService.send_message(
                    sender=sender,
                    match=match,
                    content='Concurrent retry',
                    client_message_id='concurrent-client-id',
                )
                return str(message.id) if message else None, error
            finally:
                close_old_connections()

        with patch('messaging.signals.dispatch_new_message_after_commit'):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(send_retry), executor.submit(send_retry)]
                results = [future.result(timeout=20) for future in futures]

        message_ids = {message_id for message_id, error in results if error is None}
        self.assertEqual(len(message_ids), 1)
        self.assertEqual(
            Message.objects.filter(
                match=self.match,
                sender=self.sender,
                client_message_id='concurrent-client-id',
            ).count(),
            1,
        )
        self.match.refresh_from_db()
        self.assertEqual(self.match.user2_unread_count, 1)

    @skipUnless(connection.vendor == 'postgresql', 'requires PostgreSQL row locking')
    def test_concurrent_send_and_partial_read_leave_exact_unread_count(self):
        first = Message.objects.create(
            match=self.match,
            sender=self.sender,
            content='Already visible',
            status=Message.SENT,
        )
        self.match.user2_unread_count = 1
        self.match.save(update_fields=['user2_unread_count'])
        barrier = Barrier(2)

        def send_message():
            close_old_connections()
            try:
                sender = User.objects.get(pk=self.sender.pk)
                match = Match.objects.get(pk=self.match.pk)
                barrier.wait(timeout=10)
                return MessageService.send_message(
                    sender=sender,
                    match=match,
                    content='Concurrent incoming',
                    client_message_id='concurrent-send-and-read',
                )
            finally:
                close_old_connections()

        def read_first_message():
            close_old_connections()
            try:
                recipient = User.objects.get(pk=self.recipient.pk)
                match = Match.objects.get(pk=self.match.pk)
                barrier.wait(timeout=10)
                return MessageService.mark_messages_as_read(
                    recipient,
                    match,
                    str(first.id),
                )
            finally:
                close_old_connections()

        with patch('messaging.signals.dispatch_new_message_after_commit'):
            with ThreadPoolExecutor(max_workers=2) as executor:
                send_future = executor.submit(send_message)
                read_future = executor.submit(read_first_message)
                send_result = send_future.result(timeout=20)
                read_result = read_future.result(timeout=20)

        self.assertIsNone(send_result[1])
        self.assertGreaterEqual(read_result.messages_marked, 1)
        self.match.refresh_from_db()
        actual_unread = Message.objects.filter(
            match=self.match,
            sender=self.sender,
            status__in=[Message.SENT, Message.DELIVERED],
        ).count()
        self.assertEqual(self.match.user2_unread_count, actual_unread)

    @skipUnless(connection.vendor == 'postgresql', 'requires PostgreSQL row locking')
    def test_concurrent_media_retry_creates_one_message_and_cleans_duplicate_blob(self):
        barrier = Barrier(2)

        def send_media_retry(sequence):
            close_old_connections()
            try:
                sender = User.objects.get(pk=self.sender.pk)
                match = Match.objects.get(pk=self.match.pk)
                upload = SimpleUploadedFile(
                    f'concurrent-{sequence}.jpg',
                    b'media-retry-content',
                    content_type='image/jpeg',
                )
                barrier.wait(timeout=10)
                return MessageService.create_media_message(
                    sender=sender,
                    match=match,
                    media_file=upload,
                    media_type=Message.IMAGE,
                    client_message_id='concurrent-media-client-id',
                )
            finally:
                close_old_connections()

        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root), patch(
            'messaging.services.check_feature_availability',
            return_value={'available': True, 'reason': 'ok'},
        ), patch('messaging.signals.dispatch_new_message_after_commit'):
            with ThreadPoolExecutor(max_workers=2) as executor:
                first_future = executor.submit(send_media_retry, 1)
                second_future = executor.submit(send_media_retry, 2)
                first = first_future.result(timeout=20)
                second = second_future.result(timeout=20)

            self.assertEqual(first.id, second.id)
            persisted = Message.objects.get(pk=first.pk)
            self.assertTrue(default_storage.exists(persisted.media_file_path))

        self.assertEqual(
            Message.objects.filter(
                match=self.match,
                sender=self.sender,
                client_message_id='concurrent-media-client-id',
            ).count(),
            1,
        )
        self.match.refresh_from_db()
        self.assertEqual(self.match.user2_unread_count, 1)
