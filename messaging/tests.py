from datetime import date, timedelta
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from matching.models import Match
from messaging.models import Call, ConversationHiddenState, Message
from messaging.signals import dispatch_new_message_after_commit, handle_call_update
from messaging.services import MessageService
from messaging.tasks import send_call_notification, send_message_notification, send_read_notification
from notifications.models import Notification
from profiles.models import KycAttempt, Profile, ProfilePhoto
from subscriptions.models import Subscription, SubscriptionPlan
from subscriptions.utils import invalidate_premium_status_cache


User = get_user_model()


def handle_new_message(sender, instance, created):
    """Exercise the committed-message dispatcher without bypassing on_commit."""
    if created:
        dispatch_new_message_after_commit(instance.id)


@override_settings(
	SECURE_SSL_REDIRECT=False,
	CHANNEL_LAYERS={
		'default': {
			'BACKEND': 'channels.layers.InMemoryChannelLayer',
		}
	},
)
class MessagingApiDeterministicTests(APITestCase):
	def setUp(self):
		self.user1 = User.objects.create_user(
			email='u1@example.com',
			password='TestPass123!',
			display_name='User One',
			birth_date=date(1990, 1, 1),
		)
		self.user2 = User.objects.create_user(
			email='u2@example.com',
			password='TestPass123!',
			display_name='User Two',
			birth_date=date(1991, 1, 1),
		)
		self.user3 = User.objects.create_user(
			email='u3@example.com',
			password='TestPass123!',
			display_name='User Three',
			birth_date=date(1992, 1, 1),
		)

		Profile.objects.filter(user=self.user1).update(city='Paris', country='France')
		Profile.objects.filter(user=self.user2).update(city='Paris', country='France')
		Profile.objects.filter(user=self.user3).update(city='Lyon', country='France')

		self.match = Match.objects.create(user1=self.user1, user2=self.user2, status=Match.ACTIVE)
		for user in (self.user1, self.user2, self.user3):
			KycAttempt.objects.create(
				user=user,
				status=KycAttempt.VERIFIED,
				is_open=False,
				expires_at=timezone.now() + timedelta(days=1),
			)

	def _auth(self, user):
		self.client.force_authenticate(user=user)

	def _enable_read_alert_for_user1(self):
		"""Make the message author eligible for the Premium read-alert channel."""
		self.user1.is_premium = True
		self.user1.premium_until = timezone.now() + timedelta(days=30)
		self.user1.notification_settings = {'message_read_notifications': True}
		self.user1.save(update_fields=['is_premium', 'premium_until', 'notification_settings'])
		invalidate_premium_status_cache(self.user1)

	def _activate_premium(self, user):
		plan = SubscriptionPlan.objects.create(
			plan_id=f'messaging-{str(user.id)[:8]}',
			name='Premium',
			name_en='Premium',
			name_fr='Premium',
			description='Messaging tests',
			description_en='Messaging tests',
			description_fr='Tests messagerie',
			price='7.99',
			currency='EUR',
			billing_interval=SubscriptionPlan.INTERVAL_MONTH,
			media_messaging_enabled=True,
			audio_video_calls_enabled=True,
		)
		now = timezone.now()
		Subscription.objects.create(
			subscription_id=f'messaging-subscription-{user.id}',
			user=user,
			plan=plan,
			status=Subscription.STATUS_ACTIVE,
			current_period_start=now,
			current_period_end=now + timedelta(days=30),
		)
		user.refresh_from_db()

	def _messages_url(self, conversation_id=None):
		return reverse('api:messaging:conversation-messages', kwargs={'conversation_id': conversation_id or self.match.id})

	def test_conversation_list_includes_unread_and_last_message(self):
		Message.objects.create(match=self.match, sender=self.user1, content='Hello', message_type=Message.TEXT)
		self.match.last_message_at = timezone.now()
		self.match.last_message_preview = 'Hello'
		self.match.user2_unread_count = 1
		self.match.save(update_fields=['last_message_at', 'last_message_preview', 'user2_unread_count'])

		self._auth(self.user2)
		response = self.client.get(reverse('api:messaging:conversation-list'))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['count'], 1)
		conversation = response.data['results'][0]
		self.assertEqual(conversation['unread_count_for_me'], 1)
		self.assertIn('other_user', conversation)
		self.assertIn('last_message', conversation)

	def test_conversation_list_unread_status_filters_for_the_authenticated_participant(self):
		"""The same match is unread for only the participant with a counter."""
		Message.objects.create(match=self.match, sender=self.user1, content='Unread for user two')
		self.match.last_message_at = timezone.now()
		self.match.user2_unread_count = 1
		self.match.save(update_fields=['last_message_at', 'user2_unread_count'])

		self._auth(self.user2)
		unread_response = self.client.get(
			reverse('api:messaging:conversation-list'),
			{'status': 'unread'},
		)
		self.assertEqual(unread_response.status_code, status.HTTP_200_OK)
		self.assertEqual(unread_response.data['count'], 1)
		self.assertEqual(unread_response.data['results'][0]['id'], str(self.match.id))

		self._auth(self.user1)
		read_response = self.client.get(
			reverse('api:messaging:conversation-list'),
			{'status': 'unread'},
		)
		self.assertEqual(read_response.status_code, status.HTTP_200_OK)
		self.assertEqual(read_response.data['count'], 0)

	def test_conversation_list_unread_status_keeps_pagination_and_all_status_behavior(self):
		second_match = Match.objects.create(
			user1=self.user1,
			user2=self.user3,
			status=Match.ACTIVE,
		)
		for match, recipient in ((self.match, self.user1), (second_match, self.user1)):
			Message.objects.create(match=match, sender=match.get_other_user(recipient), content='Unread')
			match.last_message_at = timezone.now()
			match.user1_unread_count = 1
			match.save(update_fields=['last_message_at', 'user1_unread_count'])

		self._auth(self.user1)
		url = reverse('api:messaging:conversation-list')
		unread_response = self.client.get(url, {'status': 'unread', 'page': 1, 'page_size': 1})
		second_unread_page = self.client.get(url, {'status': 'unread', 'page': 2, 'page_size': 1})
		all_response = self.client.get(url, {'status': 'all'})
		default_response = self.client.get(url)
		archived_response = self.client.get(url, {'status': 'archived'})

		self.assertEqual(unread_response.status_code, status.HTTP_200_OK)
		self.assertEqual(unread_response.data['count'], 2)
		self.assertEqual(len(unread_response.data['results']), 1)
		self.assertIsNotNone(unread_response.data['next'])
		self.assertEqual(second_unread_page.status_code, status.HTTP_200_OK)
		self.assertEqual(len(second_unread_page.data['results']), 1)
		self.assertIsNotNone(second_unread_page.data['previous'])
		self.assertEqual(all_response.data['count'], 2)
		self.assertEqual(default_response.data['count'], 2)
		self.assertEqual(archived_response.data['count'], 0)

	def test_conversation_list_query_count_is_constant_and_response_is_unchanged(self):
		"""List serialization must not add a query for each conversation."""
		ProfilePhoto.objects.create(
			profile=self.user2.profile,
			photo_url='https://example.test/user2.jpg',
			thumbnail_url='https://example.test/user2-thumb.jpg',
			is_main=True,
		)
		first_message = Message.objects.create(
			match=self.match,
			sender=self.user2,
			content='First conversation',
			message_type=Message.TEXT,
			status=Message.SENT,
		)
		self.match.last_message_at = timezone.now()
		self.match.save(update_fields=['last_message_at'])

		second_match = Match.objects.create(user1=self.user1, user2=self.user3, status=Match.ACTIVE)
		ProfilePhoto.objects.create(
			profile=self.user3.profile,
			photo_url='https://example.test/user3.jpg',
			thumbnail_url='https://example.test/user3-thumb.jpg',
			is_main=True,
		)
		Message.objects.create(
			match=second_match,
			sender=self.user3,
			content='Second conversation',
			message_type=Message.TEXT,
			status=Message.READ,
		)
		second_match.last_message_at = timezone.now() - timedelta(seconds=1)
		second_match.save(update_fields=['last_message_at'])

		self._auth(self.user1)
		url = reverse('api:messaging:conversation-list')
		with CaptureQueriesContext(connection) as one_item_queries:
			one_item_response = self.client.get(url, {'page': 1, 'page_size': 1})
		with CaptureQueriesContext(connection) as two_item_queries:
			two_item_response = self.client.get(url, {'page': 1, 'page_size': 2})

		self.assertEqual(one_item_response.status_code, status.HTTP_200_OK)
		self.assertEqual(two_item_response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(one_item_queries), len(two_item_queries))
		# KYC authorization contributes one bounded request-level query; it
		# must never turn list serialization into an N+1 query pattern.
		self.assertLessEqual(len(two_item_queries), 6)
		conversation = two_item_response.data['results'][0]
		# Legacy raw media references are not delivered; only verified private
		# objects receive an authenticated backend media route.
		self.assertIsNone(conversation['other_user']['main_photo_url'])
		self.assertEqual(conversation['last_message']['message_id'], str(first_message.id))
		self.assertEqual(conversation['last_message']['content_preview'], 'First conversation')
		self.assertFalse(conversation['last_message']['is_read_by_me'])

	def test_send_message_creates_message_and_increments_unread(self):
		self._auth(self.user1)
		payload = {
			'client_message_id': 'client-1',
			'content': 'Salut',
			'type': 'text',
		}
		response = self.client.post(self._messages_url(), payload, format='json')

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.match.refresh_from_db()
		self.assertEqual(self.match.user2_unread_count, 1)
		self.assertEqual(Message.objects.filter(match=self.match).count(), 1)

	def test_send_message_deduplicates_by_client_message_id(self):
		self._auth(self.user1)
		payload = {
			'client_message_id': 'same-id',
			'content': 'One',
			'type': 'text',
		}
		response1 = self.client.post(self._messages_url(), payload, format='json')
		response2 = self.client.post(self._messages_url(), payload, format='json')

		self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response1.data['message_id'], response2.data['message_id'])
		self.assertEqual(Message.objects.filter(match=self.match, client_message_id='same-id').count(), 1)

	def test_get_messages_does_not_mark_received_messages_as_read(self):
		msg = Message.objects.create(match=self.match, sender=self.user1, content='Unread', status=Message.SENT)
		self.match.user2_unread_count = 1
		self.match.save(update_fields=['user2_unread_count'])

		self._auth(self.user2)
		with patch('messaging.services.send_read_notification.delay') as mocked_delay:
			response = self.client.get(self._messages_url())

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		msg.refresh_from_db()
		self.match.refresh_from_db()
		self.assertEqual(msg.status, Message.SENT)
		self.assertIsNone(msg.read_at)
		self.assertEqual(self.match.user2_unread_count, 1)
		mocked_delay.assert_not_called()

	def test_get_messages_cursor_pagination_is_read_only(self):
		older_message = Message.objects.create(
			match=self.match,
			sender=self.user1,
			content='Older unread',
			status=Message.SENT,
		)
		newer_message = Message.objects.create(
			match=self.match,
			sender=self.user1,
			content='Newer unread',
			status=Message.SENT,
		)
		self.match.user2_unread_count = 2
		self.match.save(update_fields=['user2_unread_count'])

		self._auth(self.user2)
		with patch('messaging.services.send_read_notification.delay') as mocked_delay:
			first_page = self.client.get(self._messages_url(), {'limit': 1})
			older_page = self.client.get(
				self._messages_url(),
				{'limit': 1, 'before_message_id': str(newer_message.id)},
			)

		self.assertEqual(first_page.status_code, status.HTTP_200_OK)
		self.assertEqual(first_page.data['results'][0]['message_id'], str(newer_message.id))
		self.assertEqual(older_page.status_code, status.HTTP_200_OK)
		self.assertEqual(older_page.data['results'][0]['message_id'], str(older_message.id))
		older_message.refresh_from_db()
		newer_message.refresh_from_db()
		self.match.refresh_from_db()
		self.assertEqual(older_message.status, Message.SENT)
		self.assertEqual(newer_message.status, Message.SENT)
		self.assertIsNone(older_message.read_at)
		self.assertIsNone(newer_message.read_at)
		self.assertEqual(self.match.user2_unread_count, 2)
		mocked_delay.assert_not_called()

	def test_mark_single_message_as_read_endpoint(self):
		self._enable_read_alert_for_user1()
		msg = Message.objects.create(match=self.match, sender=self.user1, content='Ping', status=Message.SENT)
		self.match.user2_unread_count = 1
		self.match.save(update_fields=['user2_unread_count'])

		self._auth(self.user2)
		url = reverse('api:messaging:mark-single-read', kwargs={'conversation_id': self.match.id, 'message_id': msg.id})
		channel_layer = MagicMock()
		with patch('messaging.services.get_channel_layer', return_value=channel_layer), \
			 patch('messaging.services.async_to_sync', side_effect=lambda fn: fn), \
			 patch('messaging.services.send_read_notification.delay') as mocked_delay:
			with self.captureOnCommitCallbacks(execute=True):
				response = self.client.put(url, {}, format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		msg.refresh_from_db()
		self.assertEqual(msg.status, Message.READ)
		self.assertIsNotNone(msg.read_at)
		mocked_delay.assert_called_once()
		# Conversation group + author receipt + persisted Premium alert.
		self.assertEqual(channel_layer.group_send.call_count, 3)
		conversation_call, personal_call, alert_call = channel_layer.group_send.call_args_list
		self.assertEqual(
			conversation_call.args,
			(
				f'conversation_{self.match.id}',
				{
					'type': 'message_read',
					'reader_id': str(self.user2.id),
					'message_ids': [str(msg.id)],
					'read_at': msg.read_at.isoformat(),
				},
			),
		)
		self.assertEqual(
			personal_call.args,
			(
				f'user_{self.user1.id}',
				{
					'type': 'message_read',
					'conversation_id': str(self.match.id),
					'reader_id': str(self.user2.id),
					'message_ids': [str(msg.id)],
					'read_at': msg.read_at.isoformat(),
				},
			),
		)
		self.assertEqual(alert_call.args[0], f'user_{self.user1.id}')
		self.assertEqual(alert_call.args[1]['type'], 'message_read_alert')
		self.assertIn('notification_id', alert_call.args[1])

	def test_mark_messages_as_read_batch_endpoint(self):
		self._enable_read_alert_for_user1()
		msg1 = Message.objects.create(match=self.match, sender=self.user1, content='One', status=Message.SENT)
		msg2 = Message.objects.create(match=self.match, sender=self.user1, content='Two', status=Message.SENT)
		# Reproduce coarse-clock platforms where sequential messages have the
		# same timestamp while their random UUID order is unrelated to creation.
		same_created_at = timezone.now()
		Message.objects.filter(id__in=(msg1.id, msg2.id)).update(
			created_at=same_created_at,
		)
		self.match.user2_unread_count = 2
		self.match.save(update_fields=['user2_unread_count'])

		self._auth(self.user2)
		url = reverse('api:messaging:mark-as-read', kwargs={'conversation_id': self.match.id})
		channel_layer = MagicMock()
		with patch('messaging.services.get_channel_layer', return_value=channel_layer), \
			 patch('messaging.services.async_to_sync', side_effect=lambda fn: fn), \
			 patch('messaging.services.send_read_notification.delay') as mocked_delay:
			with self.captureOnCommitCallbacks(execute=True):
				response = self.client.put(url, {'last_read_message_id': str(msg2.id)}, format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['messages_marked'], 2)
		mocked_delay.assert_called_once()
		msg1.refresh_from_db()
		msg2.refresh_from_db()
		self.assertEqual(msg1.status, Message.READ)
		self.assertEqual(msg2.status, Message.READ)
		self.assertEqual(msg1.read_at, msg2.read_at)
		self.assertEqual(channel_layer.group_send.call_count, 3)
		group_name, event = channel_layer.group_send.call_args_list[0].args
		self.assertEqual(group_name, f'conversation_{self.match.id}')
		self.assertEqual(event['type'], 'message_read')
		self.assertEqual(event['reader_id'], str(self.user2.id))
		self.assertEqual(set(event['message_ids']), {str(msg1.id), str(msg2.id)})
		self.assertEqual(event['read_at'], msg1.read_at.isoformat())

		personal_group, personal_event = channel_layer.group_send.call_args_list[1].args
		self.assertEqual(personal_group, f'user_{self.user1.id}')
		self.assertEqual(personal_event['type'], 'message_read')
		self.assertEqual(personal_event['conversation_id'], str(self.match.id))
		self.assertEqual(personal_event['reader_id'], str(self.user2.id))
		self.assertEqual(set(personal_event['message_ids']), {str(msg1.id), str(msg2.id)})
		alert_group, alert_event = channel_layer.group_send.call_args_list[2].args
		self.assertEqual(alert_group, f'user_{self.user1.id}')
		self.assertEqual(alert_event['type'], 'message_read_alert')
		self.assertEqual(alert_event['message_count'], 2)

	def test_mark_messages_as_read_succeeds_when_channel_layer_is_unavailable(self):
		msg = Message.objects.create(match=self.match, sender=self.user1, content='Unread', status=Message.SENT)
		self.match.user2_unread_count = 1
		self.match.save(update_fields=['user2_unread_count'])

		self._auth(self.user2)
		url = reverse('api:messaging:mark-as-read', kwargs={'conversation_id': self.match.id})
		with patch('messaging.services.get_channel_layer', return_value=None), \
			 patch('messaging.services.send_read_notification.delay') as mocked_delay:
			with self.captureOnCommitCallbacks(execute=True):
				response = self.client.put(url, {'last_read_message_id': str(msg.id)}, format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['messages_marked'], 1)
		msg.refresh_from_db()
		self.match.refresh_from_db()
		self.assertEqual(msg.status, Message.READ)
		self.assertEqual(self.match.user2_unread_count, 0)
		# Read status is still persisted for Free users; only the Premium push is withheld.
		mocked_delay.assert_not_called()

	def test_mark_messages_as_read_succeeds_when_receipt_broadcast_fails(self):
		self._enable_read_alert_for_user1()
		msg = Message.objects.create(match=self.match, sender=self.user1, content='Unread', status=Message.SENT)
		self.match.user2_unread_count = 1
		self.match.save(update_fields=['user2_unread_count'])

		self._auth(self.user2)
		url = reverse('api:messaging:mark-as-read', kwargs={'conversation_id': self.match.id})
		channel_layer = MagicMock()
		channel_layer.group_send.side_effect = RuntimeError('channel layer unavailable')
		with patch('messaging.services.get_channel_layer', return_value=channel_layer), \
			 patch('messaging.services.async_to_sync', side_effect=lambda fn: fn), \
			 patch('messaging.services.send_read_notification.delay') as mocked_delay:
			with self.captureOnCommitCallbacks(execute=True):
				response = self.client.put(url, {'last_read_message_id': str(msg.id)}, format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['messages_marked'], 1)
		msg.refresh_from_db()
		self.match.refresh_from_db()
		self.assertEqual(msg.status, Message.READ)
		self.assertEqual(self.match.user2_unread_count, 0)
		mocked_delay.assert_called_once()

	def test_mark_single_message_as_read_succeeds_when_receipt_broadcast_fails(self):
		self._enable_read_alert_for_user1()
		msg = Message.objects.create(match=self.match, sender=self.user1, content='Unread', status=Message.SENT)
		self.match.user2_unread_count = 1
		self.match.save(update_fields=['user2_unread_count'])

		self._auth(self.user2)
		url = reverse('api:messaging:mark-single-read', kwargs={'conversation_id': self.match.id, 'message_id': msg.id})
		channel_layer = MagicMock()
		channel_layer.group_send.side_effect = RuntimeError('channel layer unavailable')
		with patch('messaging.services.get_channel_layer', return_value=channel_layer), \
			 patch('messaging.services.async_to_sync', side_effect=lambda fn: fn), \
			 patch('messaging.services.send_read_notification.delay') as mocked_delay:
			with self.captureOnCommitCallbacks(execute=True):
				response = self.client.put(url, {}, format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		msg.refresh_from_db()
		self.match.refresh_from_db()
		self.assertEqual(msg.status, Message.READ)
		self.assertIsNotNone(msg.read_at)
		self.assertEqual(self.match.user2_unread_count, 0)
		mocked_delay.assert_called_once()

	def test_delete_message_soft_delete_sender(self):
		msg = Message.objects.create(match=self.match, sender=self.user1, content='Delete me')
		self._auth(self.user1)
		url = reverse('api:messaging:delete-message', kwargs={'conversation_id': self.match.id, 'message_id': msg.id})
		response = self.client.delete(url)

		self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
		msg.refresh_from_db()
		self.assertTrue(msg.is_deleted_by_sender)

	def test_delete_conversation_hides_it_only_for_requesting_user(self):
		Message.objects.create(match=self.match, sender=self.user1, content='Private history')
		self.match.last_message_at = timezone.now()
		self.match.save(update_fields=['last_message_at'])
		delete_url = reverse('api:messaging:delete-conversation', kwargs={'conversation_id': self.match.id})

		self._auth(self.user1)
		response = self.client.delete(delete_url)

		self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
		self.assertTrue(ConversationHiddenState.objects.filter(match=self.match, user=self.user1).exists())
		self.assertEqual(self.client.get(reverse('api:messaging:conversation-list')).data['count'], 0)

		self._auth(self.user2)
		visible_for_other_participant = self.client.get(reverse('api:messaging:conversation-list'))
		self.assertEqual(visible_for_other_participant.status_code, status.HTTP_200_OK)
		self.assertEqual(visible_for_other_participant.data['count'], 1)

	def test_delete_conversation_is_idempotent_and_requires_membership(self):
		delete_url = reverse('api:messaging:delete-conversation', kwargs={'conversation_id': self.match.id})

		self.assertEqual(self.client.delete(delete_url).status_code, status.HTTP_401_UNAUTHORIZED)

		self._auth(self.user1)
		self.assertEqual(self.client.delete(delete_url).status_code, status.HTTP_204_NO_CONTENT)
		self.assertEqual(self.client.delete(delete_url).status_code, status.HTTP_204_NO_CONTENT)
		self.assertEqual(ConversationHiddenState.objects.filter(match=self.match, user=self.user1).count(), 1)

		self._auth(self.user3)
		self.assertEqual(self.client.delete(delete_url).status_code, status.HTTP_404_NOT_FOUND)

	def test_incoming_message_restores_conversation_hidden_by_recipient(self):
		ConversationHiddenState.objects.create(match=self.match, user=self.user2)

		message, error = MessageService.send_message(
			sender=self.user1,
			match=self.match,
			content='A new message',
			client_message_id='restore-hidden-conversation',
		)

		self.assertIsNone(error)
		self.assertIsNotNone(message)
		self.assertFalse(ConversationHiddenState.objects.filter(match=self.match, user=self.user2).exists())

		self._auth(self.user2)
		response = self.client.get(reverse('api:messaging:conversation-list'))
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['count'], 1)

	def test_outgoing_message_does_not_restore_sender_hidden_conversation(self):
		ConversationHiddenState.objects.create(match=self.match, user=self.user1)

		message, error = MessageService.send_message(
			sender=self.user1,
			match=self.match,
			content='My own follow-up',
			client_message_id='preserve-sender-hidden-conversation',
		)

		self.assertIsNone(error)
		self.assertIsNotNone(message)
		self.assertTrue(ConversationHiddenState.objects.filter(match=self.match, user=self.user1).exists())

	def test_typing_and_presence_flow(self):
		self._auth(self.user1)
		typing_url = reverse('api:messaging:typing-indicator', kwargs={'conversation_id': self.match.id})
		response = self.client.post(typing_url, {'is_typing': True}, format='json')
		self.assertEqual(response.status_code, status.HTTP_200_OK)

		self._auth(self.user2)
		presence_url = reverse('api:messaging:conversation-presence', kwargs={'conversation_id': self.match.id})
		presence = self.client.get(presence_url)

		self.assertEqual(presence.status_code, status.HTTP_200_OK)
		self.assertTrue(presence.data['participant']['is_typing'])

	def test_json_message_endpoint_rejects_legacy_media_payload(self):
		self._auth(self.user1)
		payload = {
			'client_message_id': 'media-1',
			'type': 'image',
			'media_file_path_on_storage': 'messages/file.jpg',
			'content': '',
		}
		response = self.client.post(self._messages_url(), payload, format='json')
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('media_file_path_on_storage', response.data['details'])
		self.assertFalse(Message.objects.filter(match=self.match).exists())

	def test_decommissioned_signed_upload_endpoint_returns_404(self):
		self._auth(self.user1)
		response = self.client.post(
			'/api/v1/conversations/generate-media-upload-url/',
			{'file_name': 'photo.jpg', 'content_type': 'image/jpeg'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

	def test_premium_user_can_send_media_message(self):
		self._activate_premium(self.user1)
		self._auth(self.user1)
		upload = SimpleUploadedFile('photo.jpg', b'\xff\xd8\xffvalid-image-bytes', content_type='image/jpeg')
		with patch('messaging.views.check_feature_availability', return_value={'available': True, 'reason': 'ok'}), patch(
			'messaging.services.check_feature_availability', return_value={'available': True, 'reason': 'ok'}
		):
			response = self.client.post(
				reverse('api:messaging:send-media-message', kwargs={'conversation_id': self.match.id}),
				{
					'media_file': upload,
					'media_type': 'image',
					'text': 'Photo',
					'client_message_id': 'media-2',
				},
			)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data['message_type'], 'image')
		self.assertTrue(response.data['media_url'].endswith(f'/conversations/{self.match.id}/messages/{response.data["message_id"]}/media/'))

	def test_premium_user_cannot_send_unsafe_media_caption(self):
		self._activate_premium(self.user1)
		self._auth(self.user1)
		upload = SimpleUploadedFile('photo.jpg', b'\xff\xd8\xffvalid-image-bytes', content_type='image/jpeg')
		with patch('messaging.views.check_feature_availability', return_value={'available': True, 'reason': 'ok'}), patch(
			'messaging.services.check_feature_availability', return_value={'available': True, 'reason': 'ok'}
		):
			response = self.client.post(
				reverse('api:messaging:send-media-message', kwargs={'conversation_id': self.match.id}),
				{
					'media_file': upload,
					'media_type': 'image',
					'text': '<script>alert(1)</script>',
					'client_message_id': 'media-unsafe-1',
				},
			)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertFalse(Message.objects.filter(match=self.match).exists())

	def test_multipart_media_upload_persists_file_and_returns_its_url(self):
		self._activate_premium(self.user1)
		self._auth(self.user1)
		valid_bytes = b'\xff\xd8\xffpersisted-media-bytes'
		upload = SimpleUploadedFile('photo.jpg', valid_bytes, content_type='image/jpeg')

		with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root), patch(
			'messaging.views.check_feature_availability', return_value={'available': True, 'reason': 'ok'}
		), patch('messaging.services.check_feature_availability', return_value={'available': True, 'reason': 'ok'}):
			response = self.client.post(
				reverse('api:messaging:send-media-message', kwargs={'conversation_id': self.match.id}),
				{
					'media_file': upload,
					'media_type': 'image',
					'client_message_id': 'media-persisted-1',
				},
			)

			self.assertEqual(response.status_code, status.HTTP_201_CREATED)
			message = Message.objects.get(id=response.data['message_id'])
			self.assertEqual(message.client_message_id, 'media-persisted-1')
			self.assertTrue(default_storage.exists(message.media_file_path))
			# REST exposes only an authenticated API route; the provider/local path
			# is never persisted or returned to the client.
			self.assertTrue(response.data['media_url'].startswith('http://testserver/'))
			self.assertTrue(response.data['media_url'].endswith(f'/conversations/{self.match.id}/messages/{message.id}/media/'))
			self.assertEqual(message.media_url, '')
			with default_storage.open(message.media_file_path, 'rb') as stored_file:
				self.assertEqual(stored_file.read(), valid_bytes)

	def test_multipart_media_upload_deletes_blob_when_message_creation_fails(self):
		self._activate_premium(self.user1)
		self._auth(self.user1)
		upload = SimpleUploadedFile('photo.jpg', b'\xff\xd8\xffcleanup-media-bytes', content_type='image/jpeg')

		with patch('messaging.views.check_feature_availability', return_value={'available': True, 'reason': 'ok'}), patch(
			'messaging.services.default_storage'
		) as mocked_storage, patch.object(MessageService, 'send_message', return_value=(None, 'Message creation failed')):
			mocked_storage.save.return_value = 'messages/cleanup/photo.jpg'
			mocked_storage.url.return_value = '/media/messages/cleanup/photo.jpg'
			response = self.client.post(
				reverse('api:messaging:send-media-message', kwargs={'conversation_id': self.match.id}),
				{'media_file': upload, 'media_type': 'image'},
			)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertFalse(Message.objects.filter(match=self.match).exists())
		mocked_storage.delete.assert_called_once_with('messages/cleanup/photo.jpg')

	def test_premium_user_can_initiate_call(self):
		self._activate_premium(self.user1)

		self._auth(self.user1)
		payload = {
			'target_user_id': str(self.user2.id),
			'call_type': 'audio',
			'offer_sdp': 'offer-data',
		}
		# LOG-07 : send_call_notification.delay est maintenant différée via
		# transaction.on_commit. Utiliser captureOnCommitCallbacks pour
		# exécuter les callbacks pendant le test.
		with patch('messaging.services.send_call_notification.delay') as mocked_delay:
			with self.captureOnCommitCallbacks(execute=True):
				response = self.client.post(
					reverse('api:messaging:initiate-premium-call'),
					payload,
					format='json',
				)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(Call.objects.filter(match=self.match).count(), 1)
		mocked_delay.assert_called_once()

	def test_call_answer_ice_and_terminate_flow(self):
		self._activate_premium(self.user1)

		self._auth(self.user1)
		with patch('messaging.services.send_call_notification.delay'):
			initiate = self.client.post(
				reverse('api:calls:initiate'),
				{'target_user_id': str(self.user2.id), 'call_type': 'audio', 'offer_sdp': 'offer-data'},
				format='json',
			)

		self.assertEqual(initiate.status_code, status.HTTP_201_CREATED)
		call_id = initiate.data['call_id']

		self._auth(self.user2)
		answer = self.client.post(
			reverse('api:calls:answer', kwargs={'call_id': call_id}),
			{'answer_sdp': 'answer-data'},
			format='json',
		)
		self.assertEqual(answer.status_code, status.HTTP_200_OK)

		ice = self.client.post(
			reverse('api:calls:ice-candidate', kwargs={'call_id': call_id}),
			{'candidate': {'candidate': 'abc', 'sdpMid': '0', 'sdpMLineIndex': 0}},
			format='json',
		)
		self.assertEqual(ice.status_code, status.HTTP_204_NO_CONTENT)

		end = self.client.post(
			reverse('api:calls:terminate', kwargs={'call_id': call_id}),
			{'reason': 'ended_by_callee'},
			format='json',
		)
		self.assertEqual(end.status_code, status.HTTP_200_OK)

		call = Call.objects.get(id=call_id)
		self.assertEqual(call.status, Call.ENDED)
		self.assertEqual(Message.objects.filter(match=self.match, message_type=Message.CALL_LOG).count(), 1)

	def test_non_premium_cannot_initiate_call(self):
		self._auth(self.user1)
		payload = {
			'target_user_id': str(self.user2.id),
			'call_type': 'video',
			'offer_sdp': 'offer-data',
		}
		response = self.client.post(reverse('api:calls:initiate'), payload, format='json')

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_send_message_rejects_unsafe_markup(self):
		self._auth(self.user1)
		payload = {
			'client_message_id': 'html-1',
			'content': '<b>Salut</b><script>alert(1)</script>',
			'type': 'text',
		}
		response = self.client.post(self._messages_url(), payload, format='json')

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_send_message_strips_safe_html_from_text_content(self):
		self._auth(self.user1)
		payload = {
			'client_message_id': 'html-2',
			'content': '<b>Salut</b>',
			'type': 'text',
		}
		response = self.client.post(self._messages_url(), payload, format='json')

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data['content'], 'Salut')

	def test_send_message_preserves_plain_unicode_and_line_breaks(self):
		self._auth(self.user1)
		content = 'Bonjour 👋\nà bientôt'
		response = self.client.post(
			self._messages_url(),
			{
				'client_message_id': 'plain-unicode-1',
				'content': content,
				'type': 'text',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data['content'], content)

	def test_send_message_notification_task_uses_tokens(self):
		self.user2.fcm_tokens = [{'token': 'tok-1'}]
		self.user2.notification_settings = {'new_message_notifications': True}
		self.user2.save(update_fields=['fcm_tokens', 'notification_settings'])

		# FCM est maintenant délégué à notifications.fcm.send_fcm_to_user
		with patch('messaging.tasks.send_fcm_to_user') as mock_fcm:
			mock_fcm.return_value = {'success': 1, 'failure': 0, 'purged': 0}
			send_message_notification(
				self.user2.id,
				self.user1.id,
				'Hello',
				str(self.match.id),
				message_id='message-id',
			)

			mock_fcm.assert_called_once()
			# Vérifier que le destinataire est user2
			call_args = mock_fcm.call_args
			self.assertEqual(call_args[0][0].id, self.user2.id)
			self.assertEqual(call_args.kwargs['data']['message_id'], 'message-id')

	def test_send_read_notification_task_uses_tokens(self):
		self.user1.is_premium = True
		self.user1.premium_until = timezone.now() + timedelta(days=30)
		self.user1.fcm_tokens = [{'token': 'tok-1'}]
		self.user1.notification_settings = {'message_read_notifications': True}
		self.user1.save(update_fields=['is_premium', 'premium_until', 'fcm_tokens', 'notification_settings'])
		from subscriptions.utils import invalidate_premium_status_cache
		invalidate_premium_status_cache(self.user1)

		with patch('messaging.tasks.send_fcm_to_user') as mock_fcm:
			mock_fcm.return_value = {'success': 1, 'failure': 0, 'purged': 0}
			send_read_notification(self.user1.id, self.user2.id, str(self.match.id), 'message-id')

		mock_fcm.assert_called_once()
		call_args = mock_fcm.call_args
		self.assertEqual(call_args[0][0].id, self.user1.id)

	def test_send_call_notification_task_uses_tokens(self):
		self.user2.fcm_tokens = [{'token': 'tok-1'}]
		self.user2.save(update_fields=['fcm_tokens'])

		with patch('messaging.tasks.send_fcm_to_user') as mock_fcm:
			mock_fcm.return_value = {'success': 1, 'failure': 0, 'purged': 0}
			send_call_notification(self.user2.id, self.user1.id, 'audio', str(self.match.id))

		mock_fcm.assert_called_once()
		call_args = mock_fcm.call_args
		self.assertEqual(call_args[0][0].id, self.user2.id)

	def test_handle_new_message_signal_dispatches_socket_and_notification(self):
		message = Message.objects.create(match=self.match, sender=self.user1, content='Signal test', message_type=Message.TEXT)

		mock_layer = MagicMock()
		with patch('messaging.signals.send_message_notification.delay') as mocked_delay, \
			 patch('messaging.signals.get_channel_layer', return_value=mock_layer), \
			 patch('messaging.signals.async_to_sync', side_effect=lambda fn: fn):
			handle_new_message(Message, message, True)

		mocked_delay.assert_called_once()
		notification = Notification.objects.get(user=self.user2, type='new_message')
		self.assertEqual(
			mocked_delay.call_args.kwargs['message_id'],
			str(message.id),
			'FCM notification_id must be derived from the message, not the sender',
		)
		self.assertEqual(mock_layer.group_send.call_count, 2)
		self.assertEqual(
			mock_layer.group_send.call_args_list[0].args,
			(
				f'conversation_{self.match.id}',
				{
					'type': 'message_created',
					'message_id': str(message.id),
					'conversation_id': str(self.match.id),
					'sender_id': str(self.user1.id),
					'content': 'Signal test',
					'message_type': Message.TEXT,
					'media_url': None,
					'media_type': None,
					'media_thumbnail_url': None,
					'media_download_url': None,
					'media_mime_type': None,
					'media_size_bytes': None,
					'media_file_name': None,
					'media_duration_ms': None,
					'sent_at': message.created_at.isoformat(),
					'client_message_id': None,
				},
			),
		)
		self.assertEqual(
			mock_layer.group_send.call_args_list[1].args,
			(
				f'user_{self.user2.id}',
				{
					'type': 'new_message',
					'conversation_id': str(self.match.id),
					'message_id': str(message.id),
					'from_user_id': str(self.user1.id),
					'sender_name': self.user1.display_name,
					'preview': 'Signal test',
					'notification_id': str(notification.id),
					'unread_count': 0,
				},
			),
		)
		self.assertEqual(notification.data['message_id'], str(message.id))

	def test_media_message_signal_includes_media_fields(self):
		message = Message.objects.create(
			match=self.match,
			sender=self.user1,
			content='Photo',
			message_type=Message.IMAGE,
			media_url='/media/messages/photo.jpg',
			media_thumbnail_url='/media/messages/photo-thumb.jpg',
			media_file_path='messages/photo.jpg',
			media_mime_type='image/jpeg',
			media_size_bytes=42,
			media_file_name='photo.jpg',
		)
		mock_layer = MagicMock()
		with patch('messaging.signals.send_message_notification.delay'), \
			 patch('messaging.signals.get_channel_layer', return_value=mock_layer), \
			 patch('messaging.signals.async_to_sync', side_effect=lambda fn: fn):
			handle_new_message(Message, message, True)

		group_name, event = mock_layer.group_send.call_args_list[0].args
		self.assertEqual(group_name, f'conversation_{self.match.id}')
		self.assertTrue(event['media_url'].endswith(f'/conversations/{self.match.id}/messages/{message.id}/media/'))
		self.assertEqual(event['media_type'], Message.IMAGE)
		self.assertIsNone(event['media_thumbnail_url'])
		self.assertEqual(event['media_mime_type'], 'image/jpeg')
		self.assertEqual(event['media_size_bytes'], 42)
		self.assertEqual(event['media_file_name'], 'photo.jpg')
		self.assertTrue(event['media_download_url'].endswith(f'/messages/{message.id}/media/'))

	def test_handle_call_update_signal_dispatches_socket_event(self):
		call = Call.objects.create(
			match=self.match,
			caller=self.user1,
			callee=self.user2,
			call_type=Call.AUDIO,
			offer_sdp='offer',
			status=Call.RINGING,
		)

		mock_layer = MagicMock()
		with patch('messaging.signals.get_channel_layer', return_value=mock_layer), \
			 patch('messaging.signals.async_to_sync', side_effect=lambda fn: fn):
			handle_call_update(Call, call, True)

		expected_payload = {
			'type': 'incoming_call',
			'call': {
				'id': str(call.id),
				'caller_id': str(self.user1.id),
				'caller_name': self.user1.display_name,
				'call_type': Call.AUDIO,
				'match_id': str(self.match.id),
			}
		}
		# Conversation group + callee's personal group (ring without the chat open).
		self.assertEqual(mock_layer.group_send.call_count, 2)
		self.assertEqual(
			mock_layer.group_send.call_args_list[0].args,
			(f'conversation_{self.match.id}', expected_payload),
		)
		self.assertEqual(
			mock_layer.group_send.call_args_list[1].args,
			(f'user_{self.user2.id}', expected_payload),
		)

	def test_handle_call_update_ignores_saves_that_cannot_change_status(self):
		"""An ICE-candidate save must not make the callee ring a second time."""
		call = Call.objects.create(
			match=self.match,
			caller=self.user1,
			callee=self.user2,
			call_type=Call.AUDIO,
			offer_sdp='offer',
			status=Call.RINGING,
		)

		mock_layer = MagicMock()
		with patch('messaging.signals.get_channel_layer', return_value=mock_layer), \
			 patch('messaging.signals.async_to_sync', side_effect=lambda fn: fn):
			handle_call_update(
				Call, call, False, update_fields=frozenset({'ice_candidates'})
			)

		mock_layer.group_send.assert_not_called()

	def test_handle_call_update_broadcasts_end_to_both_participants(self):
		call = Call.objects.create(
			match=self.match,
			caller=self.user1,
			callee=self.user2,
			call_type=Call.AUDIO,
			offer_sdp='offer',
			status=Call.ENDED,
			end_reason='ended_by_caller',
		)

		mock_layer = MagicMock()
		with patch('messaging.signals.get_channel_layer', return_value=mock_layer), \
			 patch('messaging.signals.async_to_sync', side_effect=lambda fn: fn):
			handle_call_update(Call, call, False, update_fields=None)

		self.assertEqual(mock_layer.group_send.call_count, 3)
		groups = [call_args.args[0] for call_args in mock_layer.group_send.call_args_list]
		self.assertEqual(
			groups,
			[
				f'conversation_{self.match.id}',
				f'user_{self.user1.id}',
				f'user_{self.user2.id}',
			],
		)
		payload = mock_layer.group_send.call_args_list[0].args[1]
		self.assertEqual(payload['type'], 'call_update')
		self.assertEqual(payload['call']['status'], Call.ENDED)
		self.assertEqual(payload['call']['end_reason'], 'ended_by_caller')

	# ------------------------------------------------------------------ #
	# Unread-count endpoint
	# ------------------------------------------------------------------ #

	def test_unread_count_endpoint_sums_every_conversation(self):
		"""The badge must not be capped by the conversation list page size."""
		second_match = Match.objects.create(
			user1=self.user3, user2=self.user1, status=Match.ACTIVE
		)
		self.match.user1_unread_count = 3
		self.match.save(update_fields=['user1_unread_count'])
		second_match.user2_unread_count = 4
		second_match.save(update_fields=['user2_unread_count'])

		self._auth(self.user1)
		response = self.client.get(reverse('api:messaging:conversations-unread-count'))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data, {'unread_count': 7})

	def test_unread_count_endpoint_returns_zero_without_conversations(self):
		self._auth(self.user3)
		response = self.client.get(reverse('api:messaging:conversations-unread-count'))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data, {'unread_count': 0})

	def test_unread_count_endpoint_excludes_hidden_conversations(self):
		"""Stays consistent with the list, which hides deleted conversations."""
		self.match.user1_unread_count = 5
		self.match.save(update_fields=['user1_unread_count'])
		ConversationHiddenState.objects.create(match=self.match, user=self.user1)

		self._auth(self.user1)
		response = self.client.get(reverse('api:messaging:conversations-unread-count'))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data, {'unread_count': 0})

	def test_unread_count_endpoint_ignores_other_users_counters(self):
		self.match.user1_unread_count = 2
		self.match.user2_unread_count = 9
		self.match.save(update_fields=['user1_unread_count', 'user2_unread_count'])

		self._auth(self.user1)
		response = self.client.get(reverse('api:messaging:conversations-unread-count'))

		self.assertEqual(response.data, {'unread_count': 2})

	def test_unread_count_endpoint_requires_authentication(self):
		response = self.client.get(reverse('api:messaging:conversations-unread-count'))
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	# ------------------------------------------------------------------ #
	# Delivery receipts
	# ------------------------------------------------------------------ #

	def test_mark_incoming_as_delivered_flips_only_incoming_sent_messages(self):
		incoming = Message.objects.create(
			match=self.match, sender=self.user1, content='In', status=Message.SENT
		)
		outgoing = Message.objects.create(
			match=self.match, sender=self.user2, content='Out', status=Message.SENT
		)
		already_read = Message.objects.create(
			match=self.match, sender=self.user1, content='Read', status=Message.READ
		)

		receipts = MessageService.mark_incoming_as_delivered(
			user=self.user2, match=self.match
		)

		incoming.refresh_from_db()
		outgoing.refresh_from_db()
		already_read.refresh_from_db()
		self.assertEqual(incoming.status, Message.DELIVERED)
		self.assertIsNotNone(incoming.delivered_at)
		self.assertEqual(outgoing.status, Message.SENT)
		self.assertEqual(already_read.status, Message.READ)

		self.assertEqual(len(receipts), 1)
		self.assertEqual(receipts[0].conversation_id, str(self.match.id))
		self.assertEqual(receipts[0].sender_id, str(self.user1.id))
		self.assertEqual(receipts[0].message_ids, (str(incoming.id),))

	def test_mark_incoming_as_delivered_preserves_unread_counters(self):
		"""``delivered`` still counts as unread — the badge must not drop."""
		Message.objects.create(
			match=self.match, sender=self.user1, content='In', status=Message.SENT
		)
		self.match.user2_unread_count = 1
		self.match.save(update_fields=['user2_unread_count'])

		MessageService.mark_incoming_as_delivered(user=self.user2, match=self.match)

		self.match.refresh_from_db()
		self.assertEqual(self.match.user2_unread_count, 1)

	def test_mark_incoming_as_delivered_without_match_sweeps_active_matches(self):
		other_match = Match.objects.create(
			user1=self.user2, user2=self.user3, status=Match.ACTIVE
		)
		first = Message.objects.create(
			match=self.match, sender=self.user1, content='A', status=Message.SENT
		)
		second = Message.objects.create(
			match=other_match, sender=self.user3, content='B', status=Message.SENT
		)

		receipts = MessageService.mark_incoming_as_delivered(user=self.user2)

		first.refresh_from_db()
		second.refresh_from_db()
		self.assertEqual(first.status, Message.DELIVERED)
		self.assertEqual(second.status, Message.DELIVERED)
		self.assertEqual(
			{receipt.conversation_id for receipt in receipts},
			{str(self.match.id), str(other_match.id)},
		)

	def test_mark_incoming_as_delivered_is_idempotent(self):
		Message.objects.create(
			match=self.match, sender=self.user1, content='In', status=Message.SENT
		)
		MessageService.mark_incoming_as_delivered(user=self.user2, match=self.match)

		self.assertEqual(
			MessageService.mark_incoming_as_delivered(user=self.user2, match=self.match),
			[],
		)

	def test_delivered_message_can_still_be_marked_as_read(self):
		message = Message.objects.create(
			match=self.match, sender=self.user1, content='In', status=Message.SENT
		)
		self.match.user2_unread_count = 1
		self.match.save(update_fields=['user2_unread_count'])
		MessageService.mark_incoming_as_delivered(user=self.user2, match=self.match)

		with patch('messaging.services.send_read_notification.delay'):
			with self.captureOnCommitCallbacks(execute=True):
				receipt = MessageService.mark_messages_as_read(
					user=self.user2, match=self.match
				)

		message.refresh_from_db()
		self.assertEqual(message.status, Message.READ)
		self.assertEqual(receipt.messages_marked, 1)
		self.assertEqual(receipt.unread_count_for_me, 0)

	def test_broadcast_delivery_receipts_targets_conversation_and_author(self):
		message = Message.objects.create(
			match=self.match, sender=self.user1, content='In', status=Message.SENT
		)
		receipts = MessageService.mark_incoming_as_delivered(
			user=self.user2, match=self.match
		)

		mock_layer = MagicMock()
		with patch('messaging.services.get_channel_layer', return_value=mock_layer), \
			 patch('messaging.services.async_to_sync', side_effect=lambda fn: fn):
			MessageService.broadcast_delivery_receipts(receipts)

		self.assertEqual(mock_layer.group_send.call_count, 2)
		groups = [call_args.args[0] for call_args in mock_layer.group_send.call_args_list]
		self.assertEqual(
			groups, [f'conversation_{self.match.id}', f'user_{self.user1.id}']
		)
		payload = mock_layer.group_send.call_args_list[0].args[1]
		self.assertEqual(payload['type'], 'message_delivered')
		self.assertEqual(payload['conversation_id'], str(self.match.id))
		self.assertEqual(payload['message_ids'], [str(message.id)])

	def test_broadcast_delivery_receipts_survives_channel_layer_failure(self):
		Message.objects.create(
			match=self.match, sender=self.user1, content='In', status=Message.SENT
		)
		receipts = MessageService.mark_incoming_as_delivered(
			user=self.user2, match=self.match
		)

		mock_layer = MagicMock()
		mock_layer.group_send.side_effect = RuntimeError('channel layer unavailable')
		with patch('messaging.services.get_channel_layer', return_value=mock_layer), \
			 patch('messaging.services.async_to_sync', side_effect=lambda fn: fn):
			MessageService.broadcast_delivery_receipts(receipts)

	# ------------------------------------------------------------------ #
	# Typing indicator parity
	# ------------------------------------------------------------------ #

	def test_typing_endpoint_broadcasts_to_conversation_group(self):
		self._auth(self.user1)
		url = reverse('api:messaging:typing-indicator', kwargs={'conversation_id': self.match.id})

		mock_layer = MagicMock()
		with patch('messaging.services.get_channel_layer', return_value=mock_layer), \
			 patch('messaging.services.async_to_sync', side_effect=lambda fn: fn):
			response = self.client.post(url, {'is_typing': True}, format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data, {'is_typing': True})
		mock_layer.group_send.assert_called_once_with(
			f'conversation_{self.match.id}',
			{
				'type': 'typing_indicator',
				'user_id': str(self.user1.id),
				'status': 'typing',
			},
		)

	def test_typing_endpoint_broadcasts_stop(self):
		self._auth(self.user1)
		url = reverse('api:messaging:typing-indicator', kwargs={'conversation_id': self.match.id})

		mock_layer = MagicMock()
		with patch('messaging.services.get_channel_layer', return_value=mock_layer), \
			 patch('messaging.services.async_to_sync', side_effect=lambda fn: fn):
			response = self.client.post(url, {'is_typing': False}, format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(
			mock_layer.group_send.call_args.args[1]['status'], 'stopped'
		)

	def test_typing_endpoint_succeeds_when_broadcast_fails(self):
		self._auth(self.user1)
		url = reverse('api:messaging:typing-indicator', kwargs={'conversation_id': self.match.id})

		mock_layer = MagicMock()
		mock_layer.group_send.side_effect = RuntimeError('channel layer unavailable')
		with patch('messaging.services.get_channel_layer', return_value=mock_layer), \
			 patch('messaging.services.async_to_sync', side_effect=lambda fn: fn):
			response = self.client.post(url, {'is_typing': True}, format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
