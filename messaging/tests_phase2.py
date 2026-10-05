"""Focused regressions for phase-2 messaging contracts."""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from matching.models import Match
from messaging.models import ConversationHiddenState, Message
from messaging.presence import PresenceService
from messaging.serializers import MessageSerializer, SendMediaMessageSerializer
from messaging.signals import dispatch_new_message_after_commit
from messaging.services import MessageService
from messaging.tasks import send_read_notification
from subscriptions.utils import invalidate_premium_status_cache
from notifications.models import Notification
from profiles.models import KycAttempt


User = get_user_model()


@override_settings(
    SECURE_SSL_REDIRECT=False,
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
)
class PhaseTwoMessagingTests(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            email='phase2-sender@example.com', password='Secret123!',
            display_name='Sender', birth_date=date(1990, 1, 1),
        )
        self.recipient = User.objects.create_user(
            email='phase2-recipient@example.com', password='Secret123!',
            display_name='Recipient', birth_date=date(1991, 1, 1),
        )
        self.match = Match.objects.create(
            user1=self.sender, user2=self.recipient, status=Match.ACTIVE,
        )
        for user in (self.sender, self.recipient):
            KycAttempt.objects.create(
                user=user,
                status=KycAttempt.VERIFIED,
                is_open=False,
                expires_at=timezone.now() + timedelta(days=1),
            )
        self.client = APIClient()

    def _premium_sender(self):
        self.sender.is_premium = True
        self.sender.premium_until = timezone.now() + timedelta(days=30)
        self.sender.save(update_fields=['is_premium', 'premium_until'])
        invalidate_premium_status_cache(self.sender)

    def _edit_url(self, message):
        return reverse(
            'api:messaging:edit-message',
            kwargs={
                'conversation_id': self.match.id,
                'message_id': message.id,
            },
        )

    def _delete_url(self):
        return reverse(
            'api:messaging:delete-messages',
            kwargs={'conversation_id': self.match.id},
        )

    def test_local_deletion_accepts_received_and_sent_messages(self):
        outgoing = Message.objects.create(
            match=self.match, sender=self.sender, content='outgoing',
        )
        incoming = Message.objects.create(
            match=self.match, sender=self.recipient, content='incoming',
        )
        self.client.force_authenticate(self.sender)

        response = self.client.post(
            self._delete_url(),
            {'message_ids': [str(outgoing.id), str(incoming.id)], 'scope': 'for_me'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        outgoing.refresh_from_db()
        incoming.refresh_from_db()
        self.assertTrue(outgoing.is_deleted_by_sender)
        self.assertTrue(incoming.is_deleted_by_recipient)

    def test_hiding_is_per_user_and_an_incoming_message_restores_only_recipient(self):
        self.client.force_authenticate(self.sender)
        response = self.client.delete(
            reverse(
                'api:messaging:delete-conversation',
                kwargs={'conversation_id': self.match.id},
            )
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(
            ConversationHiddenState.objects.filter(
                match=self.match, user=self.sender,
            ).exists()
        )
        ConversationHiddenState.objects.create(match=self.match, user=self.recipient)

        message, error = MessageService.send_message(
            sender=self.sender,
            match=self.match,
            content='restore recipient only',
            client_message_id='restore-hidden-conversation',
        )

        self.assertIsNotNone(message)
        self.assertIsNone(error)
        self.assertTrue(
            ConversationHiddenState.objects.filter(
                match=self.match, user=self.sender,
            ).exists()
        )
        self.assertFalse(
            ConversationHiddenState.objects.filter(
                match=self.match, user=self.recipient,
            ).exists()
        )

    def test_global_deletion_is_premium_author_only_and_cleans_related_state(self):
        self._premium_sender()
        message = Message.objects.create(
            match=self.match,
            sender=self.sender,
            content='retract me',
            media_url='/media/messages/retract.jpg',
            media_file_path='messages/retract.jpg',
            status=Message.SENT,
        )
        Notification.objects.create(
            user=self.recipient,
            type='new_message',
            title='Sender',
            body='retract me',
            data={'message_id': str(message.id)},
        )
        self.match.user2_unread_count = 1
        self.match.last_message_at = message.created_at
        self.match.last_message_preview = message.content
        self.match.save(update_fields=['user2_unread_count', 'last_message_at', 'last_message_preview'])
        self.client.force_authenticate(self.sender)

        with patch('messaging.services._delete_stored_media') as remove_media:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    self._delete_url(),
                    {'message_ids': [str(message.id)], 'scope': 'for_everyone'},
                    format='json',
                )
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
            self.assertTrue(remove_media.called)

        message.refresh_from_db()
        self.match.refresh_from_db()
        self.assertTrue(message.is_deleted_for_everyone)
        self.assertEqual(message.content, '')
        self.assertEqual(message.media_file_path, '')
        self.assertEqual(self.match.user2_unread_count, 0)
        self.assertFalse(Notification.objects.filter(data__message_id=str(message.id)).exists())

    def test_global_deletion_rejects_free_user_without_mutating_message(self):
        message = Message.objects.create(
            match=self.match, sender=self.sender, content='keep me',
        )
        self.client.force_authenticate(self.sender)

        response = self.client.post(
            self._delete_url(),
            {'message_ids': [str(message.id)], 'scope': 'for_everyone'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error'], 'premium_required')
        message.refresh_from_db()
        self.assertFalse(message.is_deleted_for_everyone)

    def test_notification_is_persisted_before_push_and_uses_canonical_uuid(self):
        message = Message.objects.create(
            match=self.match, sender=self.sender, content='hello',
        )
        with patch('messaging.signals.send_message_notification.delay') as delay:
            dispatch_new_message_after_commit(message.id)

        notification = Notification.objects.get(
            user=self.recipient, type='new_message', data__message_id=str(message.id),
        )
        self.assertEqual(notification.data['notification_id'], str(notification.id))
        self.assertTrue(delay.called)
        self.assertEqual(delay.call_args.kwargs['notification_id'], str(notification.id))

    def test_serializer_normalizes_relative_media_and_hides_retracted_payload(self):
        message = Message.objects.create(
            match=self.match,
            sender=self.sender,
            content='removed',
            media_url='media/messages/a.jpg',
            is_deleted_for_everyone=True,
        )
        payload = MessageSerializer(message).data
        self.assertTrue(payload['is_deleted_for_everyone'])
        self.assertEqual(payload['content'], '')
        self.assertIsNone(payload['media_url'])

        visible = Message.objects.create(
            match=self.match,
            sender=self.sender,
            content='media',
            media_url='media/messages/visible.jpg',
        )
        self.assertIsNone(MessageSerializer(visible).data['media_url'])

    def test_conversation_preview_skips_a_globally_retracted_latest_message(self):
        visible = Message.objects.create(
            match=self.match,
            sender=self.recipient,
            content='keep this preview',
        )
        retracted = Message.objects.create(
            match=self.match,
            sender=self.recipient,
            content='',
            is_deleted_for_everyone=True,
        )
        self.match.last_message_at = retracted.created_at
        self.match.last_message_preview = ''
        self.match.save(update_fields=['last_message_at', 'last_message_preview'])
        self.client.force_authenticate(self.sender)

        response = self.client.get(reverse('api:messaging:conversation-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'][0]['last_message']['message_id'], str(visible.id))
        self.assertEqual(
            response.data['results'][0]['last_message']['content_preview'],
            'keep this preview',
        )

    def test_media_serializer_rejects_renamed_plaintext_upload(self):
        serializer = SendMediaMessageSerializer(data={
            'media_type': 'image',
            'media_file': SimpleUploadedFile(
                'not-an-image.jpg', b'plain text', content_type='image/jpeg',
            ),
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('media_file', serializer.errors)

    def test_media_serializer_accepts_supported_image_video_and_audio_signatures(self):
        fixtures = (
            ('image', 'image.jpg', 'image/jpeg', b'\xff\xd8\xff\xe0jpeg-data'),
            ('video', 'video.mp4', 'video/mp4', b'\x00\x00\x00\x18ftypisomdata'),
            ('audio', 'audio.mp3', 'audio/mpeg', b'ID3audio-data'),
        )
        for media_type, filename, content_type, content in fixtures:
            with self.subTest(media_type=media_type):
                serializer = SendMediaMessageSerializer(data={
                    'media_type': media_type,
                    'media_file': SimpleUploadedFile(
                        filename, content, content_type=content_type,
                    ),
                })
                self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_online_recipient_is_delivered_without_waiting_for_reconnect(self):
        PresenceService.heartbeat(self.recipient, 'phase2-online-device')
        message, error = MessageService.send_message(
            sender=self.sender,
            match=self.match,
            content='already online',
            client_message_id='online-receipt',
        )

        self.assertIsNone(error)
        self.assertEqual(message.status, Message.DELIVERED)
        self.assertIsNotNone(message.delivered_at)

    def test_premium_author_can_edit_text_and_refreshes_preview_atomically(self):
        self._premium_sender()
        message = Message.objects.create(
            match=self.match,
            sender=self.sender,
            content='before edit',
            status=Message.DELIVERED,
        )
        self.match.last_message_at = message.created_at
        self.match.last_message_preview = message.content
        self.match.user2_unread_count = 1
        self.match.save(update_fields=[
            'last_message_at', 'last_message_preview', 'user2_unread_count',
        ])
        self.client.force_authenticate(self.sender)

        with patch.object(MessageService, '_broadcast_message_updated') as broadcast:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.patch(
                    self._edit_url(message),
                    {'content': 'after edit'},
                    format='json',
                )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['content'], 'after edit')
        self.assertIsNotNone(response.data['edited_at'])
        message.refresh_from_db()
        self.match.refresh_from_db()
        self.assertEqual(message.content, 'after edit')
        self.assertIsNotNone(message.edited_at)
        self.assertEqual(self.match.last_message_preview, 'after edit')
        self.assertEqual(self.match.user2_unread_count, 1)
        broadcast.assert_called_once_with(
            self.match.id,
            str(message.id),
            'after edit',
            message.edited_at,
        )

    def test_edit_rejects_free_author_other_author_and_expired_message_without_mutation(self):
        message = Message.objects.create(
            match=self.match, sender=self.sender, content='keep text',
        )
        self.client.force_authenticate(self.sender)
        response = self.client.patch(
            self._edit_url(message), {'content': 'must fail'}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error'], 'premium_required')
        message.refresh_from_db()
        self.assertEqual(message.content, 'keep text')

        self._premium_sender()
        self.client.force_authenticate(self.recipient)
        response = self.client.patch(
            self._edit_url(message), {'content': 'still fail'}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error'], 'edit_not_author')
        message.refresh_from_db()
        self.assertEqual(message.content, 'keep text')

        Message.objects.filter(pk=message.pk).update(
            created_at=timezone.now() - timedelta(minutes=16),
        )
        self.client.force_authenticate(self.sender)
        response = self.client.patch(
            self._edit_url(message), {'content': 'too late'}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error'], 'edit_window_expired')
        message.refresh_from_db()
        self.assertEqual(message.content, 'keep text')

    def test_global_delete_is_atomic_when_any_selected_message_is_ineligible(self):
        self._premium_sender()
        fresh = Message.objects.create(
            match=self.match, sender=self.sender, content='fresh',
        )
        expired = Message.objects.create(
            match=self.match, sender=self.sender, content='expired',
        )
        Message.objects.filter(pk=expired.pk).update(
            created_at=timezone.now() - timedelta(minutes=16),
        )
        self.client.force_authenticate(self.sender)

        response = self.client.post(
            self._delete_url(),
            {
                'message_ids': [str(fresh.id), str(expired.id)],
                'scope': 'for_everyone',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error'], 'global_delete_not_allowed')
        fresh.refresh_from_db()
        expired.refresh_from_db()
        self.assertFalse(fresh.is_deleted_for_everyone)
        self.assertFalse(expired.is_deleted_for_everyone)

    def test_restore_hidden_conversation_is_idempotent(self):
        self.client.force_authenticate(self.sender)
        delete_url = reverse(
            'api:messaging:delete-conversation',
            kwargs={'conversation_id': self.match.id},
        )
        restore_url = reverse(
            'api:messaging:restore-conversation',
            kwargs={'conversation_id': self.match.id},
        )
        self.assertEqual(self.client.delete(delete_url).status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(ConversationHiddenState.objects.filter(
            match=self.match, user=self.sender,
        ).exists())

        self.assertEqual(self.client.put(restore_url).status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.client.put(restore_url).status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ConversationHiddenState.objects.filter(
            match=self.match, user=self.sender,
        ).exists())

    def test_read_alert_is_only_sent_to_opted_in_active_premium_author(self):
        self.sender.fcm_tokens = [{'token': 'phase2-token'}]
        self.sender.notification_settings = {'message_read_notifications': True}
        self.sender.save(update_fields=['fcm_tokens', 'notification_settings'])
        invalidate_premium_status_cache(self.sender)

        notification_count_before = Notification.objects.count()
        with patch('messaging.tasks.send_fcm_to_user') as send_fcm:
            send_read_notification(
                self.sender.id, self.recipient.id, str(self.match.id), 'message-id',
            )
        send_fcm.assert_not_called()
        self.assertEqual(Notification.objects.count(), notification_count_before)

        self._premium_sender()
        with patch('messaging.tasks.send_fcm_to_user') as send_fcm:
            send_read_notification(
                self.sender.id, self.recipient.id, str(self.match.id), 'message-id',
            )
        send_fcm.assert_called_once()
        self.assertEqual(Notification.objects.count(), notification_count_before)

    def test_notification_preferences_force_read_alerts_off_for_free_users(self):
        self.client.force_authenticate(self.sender)
        url = '/api/v1/user-settings/notification-preferences'
        response = self.client.put(
            url,
            {'message_read_notifications': True},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['message_read_notifications'])

        self._premium_sender()
        response = self.client.put(
            url,
            {'message_read_notifications': True},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['message_read_notifications'])

