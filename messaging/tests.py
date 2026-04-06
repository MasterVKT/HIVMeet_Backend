from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from matching.models import Match
from messaging.models import Call, Message
from messaging.signals import handle_call_update, handle_new_message
from messaging.tasks import send_call_notification, send_message_notification, send_read_notification
from profiles.models import Profile


User = get_user_model()


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

	def _auth(self, user):
		self.client.force_authenticate(user=user)

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

	def test_get_messages_marks_received_messages_as_read(self):
		msg = Message.objects.create(match=self.match, sender=self.user1, content='Unread', status=Message.SENT)
		self.match.user2_unread_count = 1
		self.match.save(update_fields=['user2_unread_count'])

		self._auth(self.user2)
		with patch('messaging.services.send_read_notification.delay') as mocked_delay:
			response = self.client.get(self._messages_url())

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		msg.refresh_from_db()
		self.match.refresh_from_db()
		self.assertEqual(msg.status, Message.READ)
		self.assertEqual(self.match.user2_unread_count, 0)
		mocked_delay.assert_called_once()

	def test_mark_single_message_as_read_endpoint(self):
		msg = Message.objects.create(match=self.match, sender=self.user1, content='Ping', status=Message.SENT)
		self.match.user2_unread_count = 1
		self.match.save(update_fields=['user2_unread_count'])

		self._auth(self.user2)
		url = reverse('api:messaging:mark-single-read', kwargs={'conversation_id': self.match.id, 'message_id': msg.id})
		response = self.client.put(url, {}, format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		msg.refresh_from_db()
		self.assertEqual(msg.status, Message.READ)

	def test_mark_messages_as_read_batch_endpoint(self):
		msg1 = Message.objects.create(match=self.match, sender=self.user1, content='One', status=Message.SENT)
		msg2 = Message.objects.create(match=self.match, sender=self.user1, content='Two', status=Message.SENT)
		self.match.user2_unread_count = 2
		self.match.save(update_fields=['user2_unread_count'])

		self._auth(self.user2)
		url = reverse('api:messaging:mark-as-read', kwargs={'conversation_id': self.match.id})
		with patch('messaging.services.send_read_notification.delay') as mocked_delay:
			response = self.client.put(url, {'last_read_message_id': str(msg2.id)}, format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['messages_marked'], 2)
		mocked_delay.assert_called_once()
		msg1.refresh_from_db()
		msg2.refresh_from_db()
		self.assertEqual(msg1.status, Message.READ)
		self.assertEqual(msg2.status, Message.READ)

	def test_delete_message_soft_delete_sender(self):
		msg = Message.objects.create(match=self.match, sender=self.user1, content='Delete me')
		self._auth(self.user1)
		url = reverse('api:messaging:delete-message', kwargs={'conversation_id': self.match.id, 'message_id': msg.id})
		response = self.client.delete(url)

		self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
		msg.refresh_from_db()
		self.assertTrue(msg.is_deleted_by_sender)

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

	def test_non_premium_cannot_send_media_message(self):
		self._auth(self.user1)
		payload = {
			'client_message_id': 'media-1',
			'type': 'image',
			'media_file_path_on_storage': 'messages/file.jpg',
			'content': '',
		}
		response = self.client.post(self._messages_url(), payload, format='json')
		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_generate_media_upload_url_returns_storage_payload(self):
		self._auth(self.user1)
		response = self.client.post(
			reverse('api:messaging:generate-media-upload-url'),
			{'file_name': 'photo.jpg', 'content_type': 'image/jpeg'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('upload_url', response.data)
		self.assertIn('file_path_on_storage', response.data)

	def test_premium_user_can_send_media_message(self):
		self.user1.is_premium = True
		self.user1.save(update_fields=['is_premium'])
		self._auth(self.user1)
		upload = SimpleUploadedFile('photo.jpg', b'fake-image-bytes', content_type='image/jpeg')
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
		self.assertIn('/media/messages/', response.data['media_url'])

	def test_premium_user_can_initiate_call(self):
		self.user1.is_premium = True
		self.user1.save(update_fields=['is_premium'])

		self._auth(self.user1)
		payload = {
			'target_user_id': str(self.user2.id),
			'call_type': 'audio',
			'offer_sdp': 'offer-data',
		}
		with patch('messaging.services.send_call_notification.delay') as mocked_delay:
			response = self.client.post(reverse('api:calls:initiate'), payload, format='json')

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(Call.objects.filter(match=self.match).count(), 1)
		mocked_delay.assert_called_once()

	def test_call_answer_ice_and_terminate_flow(self):
		self.user1.is_premium = True
		self.user1.save(update_fields=['is_premium'])

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

	def test_send_message_notification_task_uses_tokens(self):
		self.user2.fcm_tokens = [{'token': 'tok-1'}]
		self.user2.notification_settings = {'new_message_notifications': True}
		self.user2.save(update_fields=['fcm_tokens', 'notification_settings'])

		with patch('messaging.tasks.messaging.Notification') as mock_notification, patch(
			'messaging.tasks.messaging.MulticastMessage'
		) as mock_multicast, patch('messaging.tasks.messaging.send_multicast') as mock_send:
			mock_send.return_value.success_count = 1
			mock_send.return_value.failure_count = 0
			send_message_notification(self.user2.id, self.user1.id, 'Hello', str(self.match.id))

		mock_notification.assert_called_once()
		mock_multicast.assert_called_once()
		mock_send.assert_called_once()

	def test_send_read_notification_task_uses_tokens(self):
		self.user1.fcm_tokens = [{'token': 'tok-1'}]
		self.user1.notification_settings = {'message_read_notifications': True}
		self.user1.save(update_fields=['fcm_tokens', 'notification_settings'])

		with patch('messaging.tasks.messaging.Notification') as mock_notification, patch(
			'messaging.tasks.messaging.MulticastMessage'
		) as mock_multicast, patch('messaging.tasks.messaging.send_multicast') as mock_send:
			mock_send.return_value.success_count = 1
			mock_send.return_value.failure_count = 0
			send_read_notification(self.user1.id, self.user2.id, str(self.match.id), 'message-id')

		mock_notification.assert_called_once()
		mock_multicast.assert_called_once()
		mock_send.assert_called_once()

	def test_send_call_notification_task_uses_tokens(self):
		self.user2.fcm_tokens = [{'token': 'tok-1'}]
		self.user2.save(update_fields=['fcm_tokens'])

		with patch('messaging.tasks.messaging.Notification') as mock_notification, patch(
			'messaging.tasks.messaging.MulticastMessage'
		) as mock_multicast, patch('messaging.tasks.messaging.send_multicast') as mock_send:
			mock_send.return_value.success_count = 1
			send_call_notification(self.user2.id, self.user1.id, 'audio', str(self.match.id))

		mock_notification.assert_called_once()
		mock_multicast.assert_called_once()
		mock_send.assert_called_once()

	def test_handle_new_message_signal_dispatches_socket_and_notification(self):
		message = Message.objects.create(match=self.match, sender=self.user1, content='Signal test', message_type=Message.TEXT)

		with patch('messaging.signals.send_message_notification.delay') as mocked_delay, patch(
			'messaging.signals.channel_layer'
		) as mocked_channel_layer, patch('messaging.signals.async_to_sync', side_effect=lambda fn: fn):
			handle_new_message(Message, message, True)

		mocked_delay.assert_called_once()
		mocked_channel_layer.group_send.assert_called_once()

	def test_handle_call_update_signal_dispatches_socket_event(self):
		call = Call.objects.create(
			match=self.match,
			caller=self.user1,
			callee=self.user2,
			call_type=Call.AUDIO,
			offer_sdp='offer',
			status=Call.RINGING,
		)

		with patch('messaging.signals.channel_layer') as mocked_channel_layer, patch(
			'messaging.signals.async_to_sync', side_effect=lambda fn: fn
		):
			handle_call_update(Call, call, True)

		mocked_channel_layer.group_send.assert_called_once()
