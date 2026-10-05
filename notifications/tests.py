"""
Tests for notifications app.

Couvre :
- Création de Notification sur like/match (signals)
- Fix args inversés send_like_notification (destinataire correct)
- Fix gate premium : non-premium reçoit une notif anonymisée
- REST endpoints : list, unread-count, mark-read, read-all
- Helper FCM : purge de tokens invalides
"""
import json
import uuid
from unittest.mock import MagicMock, patch

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from matching.models import Like, Match
from notifications.consumers import UserNotificationConsumer
from notifications.models import Notification
from notifications.payloads import like_payload, match_payload, message_payload

User = get_user_model()

_DEFAULT_BIRTH_DATE = '1990-01-01'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(email, display_name, is_premium=False):
    user = User.objects.create_user(
        email=email,
        password='testpass123',
        display_name=display_name,
        birth_date=_DEFAULT_BIRTH_DATE,
    )
    user.is_premium = is_premium
    user.save(update_fields=['is_premium'])
    return user


def jwt_header(user):
    token = str(AccessToken.for_user(user))
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------

class TestPayloads(TestCase):

    def test_match_payload_keys(self):
        p = match_payload('match-uuid', 'Alice', 'user-uuid')
        self.assertEqual(p['type'], 'new_match')
        self.assertIn('notification_id', p)
        self.assertIn('match_id', p)
        self.assertIn('from_user_id', p)
        # Toutes les valeurs doivent être des strings
        for v in p.values():
            self.assertIsInstance(v, str)

    def test_like_payload_premium_reveals_identity(self):
        p = like_payload('like-id', False, 'Bob', 'bob-id', recipient_is_premium=True)
        self.assertEqual(p['type'], 'like')
        self.assertEqual(p['from_user_id'], 'bob-id')
        self.assertIn('Bob', p['body'])

    def test_like_payload_non_premium_anonymised(self):
        p = like_payload('like-id', False, 'Bob', 'bob-id', recipient_is_premium=False)
        self.assertEqual(p['from_user_id'], '')
        self.assertNotIn('Bob', p['body'])

    def test_super_like_payload(self):
        p = like_payload('sl-id', True, 'Carol', 'carol-id', recipient_is_premium=True)
        self.assertEqual(p['type'], 'super_like')
        self.assertIn('Super', p['title'])

    def test_message_payload_keys(self):
        p = message_payload('msg-id', 'conv-id', 'Dave', 'dave-id', 'Hello world')
        self.assertEqual(p['type'], 'new_message')
        self.assertEqual(p['message_id'], 'msg-id')
        self.assertEqual(p['conversation_id'], 'conv-id')
        self.assertEqual(p['from_user_id'], 'dave-id')
        self.assertEqual(p['body'], 'Hello world')
        for value in p.values():
            self.assertIsInstance(value, str)

    def test_message_payload_preview_truncated(self):
        long_text = 'x' * 200
        p = message_payload('msg-id', 'conv-id', 'Dave', 'dave-id', long_text)
        self.assertLessEqual(len(p['body']), 80)


# ---------------------------------------------------------------------------
# FCM helper — purge
# ---------------------------------------------------------------------------

class TestFCMHelper(TestCase):

    def _make_user_with_tokens(self, tokens):
        user = make_user(f'fcm_{uuid.uuid4().hex[:6]}@test.com', 'FCM User')
        user.fcm_tokens = [{'token': t} for t in tokens]
        user.save(update_fields=['fcm_tokens'])
        return user

    @patch('notifications.fcm.messaging.send_each_for_multicast')
    def test_invalid_token_purged(self, mock_send):
        """Token marqué registration-token-not-registered doit être retiré."""
        from firebase_admin import messaging as fb_msg
        from notifications.fcm import send_fcm_to_user

        valid_token = 'valid-token-123'
        invalid_token = 'invalid-token-456'
        user = self._make_user_with_tokens([valid_token, invalid_token])

        # Simuler une réponse FCM : valid ok, invalid → erreur
        ok_resp = MagicMock(success=True, exception=None)
        err_resp = MagicMock(success=False)
        err_resp.exception = MagicMock()
        err_resp.exception.code = 'registration-token-not-registered'

        mock_response = MagicMock()
        mock_response.responses = [ok_resp, err_resp]
        mock_response.success_count = 1
        mock_response.failure_count = 1
        mock_send.return_value = mock_response

        notif = fb_msg.Notification(title='Test', body='Body')
        result = send_fcm_to_user(user, notification=notif, data={'type': 'test'})

        user.refresh_from_db()
        remaining_tokens = [t['token'] for t in user.fcm_tokens]
        self.assertIn(valid_token, remaining_tokens)
        self.assertNotIn(invalid_token, remaining_tokens)
        self.assertEqual(result['purged'], 1)

    @patch('notifications.fcm.messaging.send_each_for_multicast')
    def test_transient_complete_failure_is_retryable_without_purging_token(self, mock_send):
        """Known temporary FCM failures retain the token and request a retry."""
        from firebase_admin import messaging as fb_msg
        from notifications.fcm import send_fcm_to_user

        token = 'temporary-token-789'
        user = self._make_user_with_tokens([token])
        response = MagicMock(success=False)
        response.exception = MagicMock(code='UNAVAILABLE')
        mock_send.return_value = MagicMock(
            responses=[response], success_count=0, failure_count=1,
        )

        with self.assertLogs('hivmeet.notifications.fcm', level='WARNING') as logs:
            result = send_fcm_to_user(
                user, notification=fb_msg.Notification(title='Test', body='Body'), data={},
            )

        user.refresh_from_db()
        self.assertTrue(result['retryable'])
        self.assertEqual(user.fcm_tokens, [{'token': token}])
        output = '\n'.join(logs.output)
        self.assertIn('code=unavailable', output)
        self.assertNotIn(token, output)

    @patch('notifications.fcm.messaging.send_each_for_multicast')
    def test_invalid_argument_does_not_purge_a_token_without_specific_proof(self, mock_send):
        """A malformed payload must not be mistaken for an invalid token."""
        from firebase_admin import messaging as fb_msg
        from notifications.fcm import send_fcm_to_user

        token = 'keep-on-invalid-argument'
        user = self._make_user_with_tokens([token])
        response = MagicMock(success=False)
        response.exception = MagicMock(code='INVALID_ARGUMENT')
        mock_send.return_value = MagicMock(
            responses=[response], success_count=0, failure_count=1,
        )

        result = send_fcm_to_user(
            user, notification=fb_msg.Notification(title='Test', body='Body'), data={},
        )

        user.refresh_from_db()
        self.assertFalse(result['retryable'])
        self.assertEqual(result['purged'], 0)
        self.assertEqual(user.fcm_tokens, [{'token': token}])

    @patch('notifications.fcm.messaging.send_each_for_multicast')
    def test_no_tokens_returns_early(self, mock_send):
        """Utilisateur sans token → pas d'appel FCM."""
        from firebase_admin import messaging as fb_msg
        from notifications.fcm import send_fcm_to_user

        user = self._make_user_with_tokens([])
        notif = fb_msg.Notification(title='Test', body='Body')
        result = send_fcm_to_user(user, notification=notif, data={})
        mock_send.assert_not_called()
        self.assertEqual(result['success'], 0)


# ---------------------------------------------------------------------------
# Signals — création Notification + fix args inversés
# ---------------------------------------------------------------------------

class TestMatchSignalNotification(TestCase):

    def setUp(self):
        self.user1 = make_user('u1@test.com', 'User1')
        self.user2 = make_user('u2@test.com', 'User2')

    @patch('matching.tasks.send_match_notification.delay')
    def test_match_creates_notification_for_both_users(self, mock_task):
        match = Match.objects.create(user1=self.user1, user2=self.user2)
        notifs = Notification.objects.filter(type='new_match')
        self.assertEqual(notifs.count(), 2)
        recipients = set(notifs.values_list('user_id', flat=True))
        self.assertIn(self.user1.id, recipients)
        self.assertIn(self.user2.id, recipients)

    @patch('matching.tasks.send_match_notification.delay')
    def test_match_notification_data_has_correct_keys(self, mock_task):
        match = Match.objects.create(user1=self.user1, user2=self.user2)
        notif = Notification.objects.filter(user=self.user1, type='new_match').first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.data['type'], 'new_match')
        self.assertIn('match_id', notif.data)
        self.assertIn('from_user_id', notif.data)


class TestLikeSignalNotification(TestCase):

    def setUp(self):
        self.liker = make_user('liker@test.com', 'Liker')
        self.recipient_premium = make_user('r_premium@test.com', 'RecPremium', is_premium=True)
        self.recipient_free = make_user('r_free@test.com', 'RecFree', is_premium=False)

    @patch('matching.tasks.send_like_notification.delay')
    def test_like_notification_goes_to_recipient_not_liker(self, mock_delay):
        """Fix args inversés : la notif doit partir vers to_user (destinataire)."""
        with self.captureOnCommitCallbacks(execute=True):
            Like.objects.create(
                from_user=self.liker,
                to_user=self.recipient_premium,
                like_type=Like.REGULAR,
            )
        # Destinataire, likeur, type, puis UUID Notification canonique.
        args = mock_delay.call_args[0]
        self.assertEqual(str(args[0]), str(self.recipient_premium.id))
        self.assertEqual(str(args[1]), str(self.liker.id))
        notification = Notification.objects.get(
            user=self.recipient_premium,
            type='like',
        )
        self.assertEqual(args[3], str(notification.id))
        self.assertEqual(notification.data['notification_id'], str(notification.id))

    @patch('matching.tasks.send_like_notification.delay')
    def test_like_creates_notification_in_db(self, mock_delay):
        Like.objects.create(
            from_user=self.liker,
            to_user=self.recipient_premium,
            like_type=Like.REGULAR,
        )
        notif = Notification.objects.filter(
            user=self.recipient_premium, type='like'
        ).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.data['from_user_id'], str(self.liker.id))
        self.assertEqual(notif.data['notification_id'], str(notif.id))

    @patch('matching.tasks.send_like_notification.delay')
    def test_like_notification_non_premium_anonymised(self, mock_delay):
        """Non-premium → from_user_id vide dans la notification persistée."""
        Like.objects.create(
            from_user=self.liker,
            to_user=self.recipient_free,
            like_type=Like.REGULAR,
        )
        notif = Notification.objects.filter(
            user=self.recipient_free, type='like'
        ).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.data['from_user_id'], '')

    @patch('matching.tasks.send_like_notification.delay')
    def test_super_like_creates_super_like_notification(self, mock_delay):
        Like.objects.create(
            from_user=self.liker,
            to_user=self.recipient_premium,
            like_type=Like.SUPER,
        )
        notif = Notification.objects.filter(
            user=self.recipient_premium, type='super_like'
        ).first()
        self.assertIsNotNone(notif)


# ---------------------------------------------------------------------------
# send_like_notification task — gate premium
# ---------------------------------------------------------------------------

class TestSendLikeNotificationTask(TestCase):

    def setUp(self):
        self.liker = make_user('liker2@test.com', 'Liker2')
        self.recipient_premium = make_user('rp2@test.com', 'RecP2', is_premium=True)
        self.recipient_free = make_user('rf2@test.com', 'RecF2', is_premium=False)
        # Ajouter des tokens FCM fictifs
        for u in [self.recipient_premium, self.recipient_free]:
            u.fcm_tokens = [{'token': f'token_{u.id}'}]
            u.save(update_fields=['fcm_tokens'])

    @patch('matching.tasks.send_fcm_to_user')
    def test_non_premium_still_receives_notification(self, mock_fcm):
        """Gate premium supprimé : le non-premium doit recevoir la notif."""
        from matching.tasks import send_like_notification
        send_like_notification(
            str(self.recipient_free.id),
            str(self.liker.id),
            False,
            str(uuid.uuid4()),
        )
        mock_fcm.assert_called_once()
        # Vérifier que from_user_id est vide dans data
        call_kwargs = mock_fcm.call_args
        data_sent = call_kwargs.kwargs.get('data') or call_kwargs[1].get('data', {})
        self.assertEqual(data_sent.get('from_user_id', 'NOT_SET'), '')

    @patch('matching.tasks.send_fcm_to_user')
    def test_premium_receives_notification_with_identity(self, mock_fcm):
        """Premium → from_user_id renseigné."""
        from matching.tasks import send_like_notification
        send_like_notification(
            str(self.recipient_premium.id),
            str(self.liker.id),
            False,
            str(uuid.uuid4()),
        )
        mock_fcm.assert_called_once()
        call_kwargs = mock_fcm.call_args
        data_sent = call_kwargs.kwargs.get('data') or call_kwargs[1].get('data', {})
        self.assertEqual(data_sent.get('from_user_id'), str(self.liker.id))
        self.assertRegex(
            data_sent.get('notification_id', ''),
            r'^[0-9a-f-]{36}$',
        )

    @patch('matching.tasks.send_fcm_to_user')
    def test_disabled_like_notifications_skip_fcm(self, mock_fcm):
        """Préférence désactivée → pas de push."""
        from matching.tasks import send_like_notification
        self.recipient_free.notification_settings = {'profile_like_notifications': False}
        self.recipient_free.save(update_fields=['notification_settings'])
        send_like_notification(
            str(self.recipient_free.id),
            str(self.liker.id),
            False,
            str(uuid.uuid4()),
        )
        mock_fcm.assert_not_called()


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

class TestNotificationEndpoints(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = make_user('api_user@test.com', 'APIUser')
        self.other = make_user('other@test.com', 'Other')
        self.client.credentials(**jwt_header(self.user))

        # Créer quelques notifications
        Notification.objects.create(
            user=self.user, type='like', title='Like !', body='', is_read=False,
            data={'type': 'like', 'notification_id': 'like_1'},
        )
        Notification.objects.create(
            user=self.user, type='new_match', title='Match !', body='', is_read=True,
            data={'type': 'new_match', 'notification_id': 'match_1'},
        )
        Notification.objects.create(
            user=self.other, type='like', title='Other like', body='', is_read=False,
            data={'type': 'like', 'notification_id': 'like_2'},
        )

    def test_list_returns_own_notifications_only(self):
        resp = self.client.get('/api/v1/notifications/', secure=True)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids_returned = {n['type'] for n in resp.data['results']}
        # 2 notifs pour self.user
        self.assertEqual(resp.data['count'], 2)

    def test_list_unread_filter(self):
        resp = self.client.get('/api/v1/notifications/?unread=true', secure=True)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)
        self.assertFalse(resp.data['results'][0]['is_read'])

    def test_unread_count(self):
        resp = self.client.get('/api/v1/notifications/unread-count/', secure=True)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['unread_count'], 1)

    def test_mark_read(self):
        notif = Notification.objects.filter(user=self.user, is_read=False).first()
        url = f'/api/v1/notifications/{notif.id}/read/'
        resp = self.client.put(url, secure=True)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['is_read'])
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    def test_mark_read_other_user_404(self):
        other_notif = Notification.objects.filter(user=self.other).first()
        url = f'/api/v1/notifications/{other_notif.id}/read/'
        resp = self.client.put(url, secure=True)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_read_all(self):
        resp = self.client.put('/api/v1/notifications/read-all/', secure=True)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['marked_read'], 1)
        self.assertEqual(Notification.objects.filter(user=self.user, is_read=False).count(), 0)

    def test_unauthenticated_denied(self):
        self.client.credentials()
        resp = self.client.get('/api/v1/notifications/', secure=True)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# UserNotificationConsumer — contrat des événements user_{id}
# ---------------------------------------------------------------------------

class TestUserNotificationConsumerEvents(TestCase):
    """Vérifie le payload émis vers le client pour chaque type d'événement.

    Les handlers sont appelés directement : ce qui compte ici est le contrat
    JSON attendu par NotificationWebSocketService côté Flutter, pas la
    mécanique Channels.
    """

    def setUp(self):
        self.consumer = UserNotificationConsumer()
        self.sent = []

        async def _capture(text_data=None, **kwargs):
            self.sent.append(json.loads(text_data))

        self.consumer.send = _capture

    def _last_payload(self):
        self.assertTrue(self.sent, 'aucun message envoyé au client')
        return self.sent[-1]

    def test_new_message_payload_contract(self):
        async_to_sync(self.consumer.new_message)({
            'type': 'new_message',
            'conversation_id': 'conv-1',
            'message_id': 'msg-1',
            'from_user_id': 'user-1',
            'preview': 'Salut',
            'unread_count': 3,
        })

        self.assertEqual(self._last_payload(), {
            'type': 'new_message',
            'conversation_id': 'conv-1',
            'message_id': 'msg-1',
            'from_user_id': 'user-1',
            'preview': 'Salut',
            'unread_count': 3,
        })

    def test_new_message_payload_keeps_canonical_metadata_when_present(self):
        async_to_sync(self.consumer.new_message)({
            'type': 'new_message',
            'conversation_id': 'conv-1',
            'message_id': 'msg-1',
            'from_user_id': 'user-1',
            'sender_name': 'Alice',
            'preview': 'Salut',
            'notification_id': 'notification-1',
            'unread_count': 3,
        })

        self.assertEqual(self._last_payload(), {
            'type': 'new_message',
            'conversation_id': 'conv-1',
            'message_id': 'msg-1',
            'from_user_id': 'user-1',
            'sender_name': 'Alice',
            'preview': 'Salut',
            'notification_id': 'notification-1',
            'unread_count': 3,
        })

    def test_message_read_payload_contract(self):
        async_to_sync(self.consumer.message_read)({
            'type': 'message_read',
            'conversation_id': 'conv-1',
            'reader_id': 'user-2',
            'message_ids': ['msg-1', 'msg-2'],
            'read_at': '2026-07-31T00:00:00+00:00',
        })

        self.assertEqual(self._last_payload(), {
            'type': 'message_read',
            'conversation_id': 'conv-1',
            'reader_id': 'user-2',
            'message_ids': ['msg-1', 'msg-2'],
            'read_at': '2026-07-31T00:00:00+00:00',
        })

    def test_message_delivered_payload_contract(self):
        async_to_sync(self.consumer.message_delivered)({
            'type': 'message_delivered',
            'conversation_id': 'conv-1',
            'message_ids': ['msg-1'],
            'delivered_at': '2026-07-31T00:00:00+00:00',
        })

        payload = self._last_payload()
        self.assertEqual(payload['type'], 'message_delivered')
        self.assertEqual(payload['message_ids'], ['msg-1'])

    def test_incoming_call_payload_contract(self):
        call = {
            'id': 'call-1',
            'caller_id': 'user-1',
            'caller_name': 'Alice',
            'call_type': 'audio',
            'match_id': 'conv-1',
        }
        async_to_sync(self.consumer.incoming_call)({'type': 'incoming_call', 'call': call})

        self.assertEqual(self._last_payload(), {'type': 'incoming_call', 'call': call})

    def test_call_update_payload_contract(self):
        call = {'id': 'call-1', 'status': 'ended', 'end_reason': 'ended_by_caller'}
        async_to_sync(self.consumer.call_update)({'type': 'call_update', 'call': call})

        self.assertEqual(self._last_payload(), {'type': 'call_update', 'call': call})

    def test_ping_receives_pong(self):
        async_to_sync(self.consumer.receive)(text_data=json.dumps({'type': 'ping'}))

        payload = self._last_payload()
        self.assertEqual(payload['type'], 'pong')
        self.assertIn('timestamp', payload)

    def test_invalid_json_returns_error_frame(self):
        async_to_sync(self.consumer.receive)(text_data='not-json')

        self.assertEqual(self._last_payload()['code'], 'INVALID_JSON')

    def test_unknown_client_message_is_ignored(self):
        async_to_sync(self.consumer.receive)(text_data=json.dumps({'type': 'nope'}))

        self.assertEqual(self.sent, [])

    def test_empty_frame_is_ignored(self):
        async_to_sync(self.consumer.receive)(text_data='')

        self.assertEqual(self.sent, [])

    def test_delivery_sweep_import_has_no_cycle(self):
        """messaging importe notifications au chargement : l'inverse doit rester tardif."""
        from messaging.services import MessageService

        self.assertTrue(hasattr(MessageService, 'mark_incoming_as_delivered'))
        self.assertTrue(hasattr(MessageService, 'broadcast_delivery_receipts'))

    def test_new_match_and_like_contracts_are_unchanged(self):
        async_to_sync(self.consumer.new_match)({
            'type': 'new_match', 'match_id': 'm-1', 'matched_user_id': 'u-2',
        })
        self.assertEqual(self._last_payload(), {
            'type': 'new_match', 'match_id': 'm-1', 'matched_user_id': 'u-2',
        })

        async_to_sync(self.consumer.super_like)({
            'notification_id': 'notification-uuid',
            'from_user_id': 'u-3', 'like_id': 'l-1', 'is_super': 'true',
        })
        self.assertEqual(self._last_payload()['type'], 'super_like')
        self.assertEqual(
            self._last_payload()['notification_id'],
            'notification-uuid',
        )
