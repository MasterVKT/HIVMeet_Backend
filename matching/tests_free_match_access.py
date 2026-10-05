"""High-risk contract tests for the monthly Free match allowance."""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from rest_framework_simplejwt.tokens import AccessToken

from matching.free_access import FreeMatchAccessService
from matching.models import Like, Match, MonthlyFreeAccess
from messaging.consumers import ConversationConsumer
from messaging.services import MessageService
from subscriptions.utils import invalidate_premium_status_cache


User = get_user_model()


@override_settings(
    HIVMEET_FREE_MATCH_ACCESS_ENABLED=True,
    SECURE_SSL_REDIRECT=False,
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
)
class FreeMatchAccessContractTests(TestCase):
    def setUp(self):
        cache.clear()
        self.alice = User.objects.create_user(
            email='free-alice@example.test', password='Secret123!',
            display_name='Alice', birth_date=date(1990, 1, 1),
        )
        self.bob = User.objects.create_user(
            email='free-bob@example.test', password='Secret123!',
            display_name='Bob', birth_date=date(1991, 1, 1),
        )
        self.client = APIClient()

    def _match(self):
        return Match.objects.create(user1=self.alice, user2=self.bob)

    def _make_premium(self, user):
        user.is_premium = True
        user.premium_until = timezone.now() + timedelta(days=30)
        user.save(update_fields=['is_premium', 'premium_until'])
        invalidate_premium_status_cache(user)

    def test_free_like_reveal_is_explicit_and_idempotent_for_retries(self):
        like = Like.objects.create(from_user=self.bob, to_user=self.alice)
        self.client.force_authenticate(self.alice)

        response = self.client.post('/api/v1/matches/likes-received/reveal/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['profile']['user_id'], str(self.bob.id))
        self.assertFalse(response.data['already_revealed'])

        retry = self.client.post('/api/v1/matches/likes-received/reveal/')
        self.assertEqual(retry.status_code, status.HTTP_200_OK)
        self.assertEqual(retry.data['profile']['user_id'], str(self.bob.id))
        self.assertTrue(retry.data['already_revealed'])
        consumptions = MonthlyFreeAccess.objects.filter(user=self.alice)
        self.assertEqual(consumptions.count(), 1)
        self.assertEqual(consumptions.get().revealed_like_id, like.id)

    def test_free_like_reveal_never_bypasses_a_block(self):
        Like.objects.create(from_user=self.bob, to_user=self.alice)
        self.alice.blocked_users.add(self.bob)
        self.client.force_authenticate(self.alice)

        response = self.client.post('/api/v1/matches/likes-received/reveal/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['error'], 'no_received_like')
        self.assertFalse(MonthlyFreeAccess.objects.exists())

    def test_free_free_match_consumes_both_tokens_atomically(self):
        match = self._match()

        FreeMatchAccessService.initialize_new_match(match)

        match.refresh_from_db()
        self.assertEqual(match.access_level, Match.ACCESS_FREE_LIMITED)
        self.assertEqual(
            set(MonthlyFreeAccess.objects.values_list('user_id', flat=True)),
            {self.alice.id, self.bob.id},
        )
        self.assertEqual(
            FreeMatchAccessService.state_for(match, self.alice)['free_messages_remaining'],
            10,
        )

    def test_free_free_match_stays_locked_without_spending_other_token(self):
        MonthlyFreeAccess.objects.create(
            user=self.alice,
            month_start=FreeMatchAccessService.month_start(),
            purpose=MonthlyFreeAccess.LIKE_REVEAL,
        )
        match = self._match()

        FreeMatchAccessService.initialize_new_match(match)

        match.refresh_from_db()
        self.assertEqual(match.access_level, Match.ACCESS_LOCKED)
        self.assertEqual(MonthlyFreeAccess.objects.filter(user=self.bob).count(), 0)
        self.assertFalse(
            FreeMatchAccessService.state_for(match, self.bob)['can_view_profile']
        )

        # Deep links receive the same policy as the match card.
        self.client.force_authenticate(self.alice)
        response = self.client.get(f'/api/v1/user-profiles/{self.bob.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_locked_match_can_be_retried_after_next_utc_month(self):
        current_month = FreeMatchAccessService.month_start()
        MonthlyFreeAccess.objects.create(
            user=self.alice,
            month_start=current_month,
            purpose=MonthlyFreeAccess.LIKE_REVEAL,
        )
        match = self._match()
        FreeMatchAccessService.initialize_new_match(match)
        match.refresh_from_db()
        self.assertEqual(match.access_level, Match.ACCESS_LOCKED)

        next_month = (current_month.replace(day=28) + timedelta(days=4)).replace(day=1)
        with patch.object(FreeMatchAccessService, 'month_start', return_value=next_month):
            FreeMatchAccessService.retry_unlock(self.alice, match)

        match.refresh_from_db()
        self.assertEqual(match.access_level, Match.ACCESS_FREE_LIMITED)
        self.assertEqual(
            MonthlyFreeAccess.objects.filter(month_start=next_month).count(), 2
        )

    def test_premium_free_match_is_full_without_free_token(self):
        self._make_premium(self.alice)
        match = self._match()

        FreeMatchAccessService.initialize_new_match(match)

        match.refresh_from_db()
        self.assertEqual(match.access_level, Match.ACCESS_FULL)
        self.assertFalse(MonthlyFreeAccess.objects.exists())

    def test_ten_text_messages_are_independent_and_idempotent(self):
        match = self._match()
        FreeMatchAccessService.initialize_new_match(match)

        for number in range(10):
            message, error = MessageService.send_message(
                sender=self.alice,
                match=match,
                content=f'message {number}',
                client_message_id=f'alice-{number}',
            )
            self.assertIsNotNone(message)
            self.assertIsNone(error)

        match.refresh_from_db()
        self.assertEqual(match.user1_free_messages_sent, 10)
        duplicate, duplicate_error = MessageService.send_message(
            sender=self.alice,
            match=match,
            content='retry',
            client_message_id='alice-0',
        )
        self.assertIsNotNone(duplicate)
        self.assertIsNone(duplicate_error)
        match.refresh_from_db()
        self.assertEqual(match.user1_free_messages_sent, 10)

        blocked, error = MessageService.send_message(
            sender=self.alice,
            match=match,
            content='eleventh',
            client_message_id='alice-10',
        )
        self.assertIsNone(blocked)
        self.assertEqual(error.code, 'free_message_limit_reached')

        # The other participant has their own quota and remains able to send.
        incoming, error = MessageService.send_message(
            sender=self.bob,
            match=match,
            content='Bob still has ten messages',
            client_message_id='bob-0',
        )
        self.assertIsNotNone(incoming)
        self.assertIsNone(error)
        match.refresh_from_db()
        self.assertEqual(match.user2_free_messages_sent, 1)

        # An active premium upgrade takes effect immediately.
        self._make_premium(self.alice)
        permitted, error = MessageService.send_message(
            sender=self.alice,
            match=match,
            content='premium removes the cap',
            client_message_id='alice-premium',
        )
        self.assertIsNotNone(permitted)
        self.assertIsNone(error)

    def test_rest_limit_returns_stable_403_code(self):
        match = self._match()
        FreeMatchAccessService.initialize_new_match(match)
        for number in range(10):
            MessageService.send_message(
                self.alice, match, f'used {number}', client_message_id=f'used-{number}'
            )

        self.client.force_authenticate(self.alice)
        response = self.client.post(
            f'/api/v1/conversations/{match.id}/messages/',
            {
                'content': 'blocked by server',
                'type': 'text',
                'client_message_id': 'blocked-rest',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error'], 'free_message_limit_reached')


@override_settings(
    HIVMEET_FREE_MATCH_ACCESS_ENABLED=True,
    SECURE_SSL_REDIRECT=False,
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
)
class FreeMatchAccessWebSocketTests(TransactionTestCase):
    """The WebSocket route must use the same server-side message allowance."""

    def setUp(self):
        cache.clear()
        self.alice = User.objects.create_user(
            email='free-ws-alice@example.test', password='Secret123!',
            display_name='Alice WS', birth_date=date(1990, 1, 1),
        )
        self.bob = User.objects.create_user(
            email='free-ws-bob@example.test', password='Secret123!',
            display_name='Bob WS', birth_date=date(1991, 1, 1),
        )
        self.match = Match.objects.create(user1=self.alice, user2=self.bob)
        FreeMatchAccessService.initialize_new_match(self.match)

    def _token(self, user):
        return str(AccessToken.for_user(user))

    def test_websocket_rejects_the_eleventh_free_text_message(self):
        for number in range(10):
            message, error = MessageService.send_message(
                self.alice,
                self.match,
                f'used {number}',
                client_message_id=f'websocket-used-{number}',
            )
            self.assertIsNotNone(message)
            self.assertIsNone(error)

        async def scenario():
            communicator = WebsocketCommunicator(
                ConversationConsumer.as_asgi(),
                f'/ws/conversations/{self.match.id}/?token={self._token(self.alice)}',
            )
            communicator.scope['url_route'] = {
                'kwargs': {'conversation_id': str(self.match.id)}
            }
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.send_json_to({
                'type': 'message.send',
                'content': 'blocked by the same Free limit',
                'client_message_id': 'websocket-blocked',
            })
            # A presence event can be queued before the rejection.
            for _ in range(3):
                event = await communicator.receive_json_from(timeout=1)
                if event.get('type') == 'error':
                    self.assertEqual(event['code'], 'free_message_limit_reached')
                    break
            else:
                self.fail('The WebSocket did not return the Free limit code.')
            await communicator.disconnect()

        async_to_sync(scenario)()

    def test_locked_match_denies_history_and_websocket_connection(self):
        # ``setUp`` creates an unlocked Free-Free match. Remove that unrelated
        # state so this test controls exactly one consumed token and one match.
        MonthlyFreeAccess.objects.all().delete()
        MonthlyFreeAccess.objects.create(
            user=self.alice,
            month_start=FreeMatchAccessService.month_start(),
            purpose=MonthlyFreeAccess.LIKE_REVEAL,
        )
        locked_match = self.match
        locked_match.access_level = Match.ACCESS_LOCKED
        locked_match.save(update_fields=['access_level', 'updated_at'])
        self.assertEqual(locked_match.access_level, Match.ACCESS_LOCKED)

        client = APIClient()
        client.force_authenticate(self.bob)
        rest_response = client.get(
            f'/api/v1/conversations/{locked_match.id}/messages/'
        )
        self.assertEqual(rest_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(rest_response.data['error'], 'free_match_locked')

        async def scenario():
            communicator = WebsocketCommunicator(
                ConversationConsumer.as_asgi(),
                f'/ws/conversations/{locked_match.id}/?token={self._token(self.bob)}',
            )
            communicator.scope['url_route'] = {
                'kwargs': {'conversation_id': str(locked_match.id)}
            }
            connected, close_code = await communicator.connect()
            self.assertFalse(connected)
            self.assertEqual(close_code, 4003)

        async_to_sync(scenario)()
