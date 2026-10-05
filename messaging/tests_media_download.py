"""Contract tests for explicit, authenticated message-media downloads."""

from datetime import date, timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from matching.models import Match
from messaging.models import Message
from messaging.services import MessageService
from profiles.models import KycAttempt, Profile


User = get_user_model()


@override_settings(
    SECURE_SSL_REDIRECT=False,
    CHANNEL_LAYERS={
        'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'},
    },
)
class MessageMediaDownloadTests(APITestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            email='sender-media@example.test',
            password='TestPass123!',
            display_name='Sender',
            birth_date=date(1990, 1, 1),
        )
        self.recipient = User.objects.create_user(
            email='recipient-media@example.test',
            password='TestPass123!',
            display_name='Recipient',
            birth_date=date(1991, 1, 1),
        )
        self.outsider = User.objects.create_user(
            email='outsider-media@example.test',
            password='TestPass123!',
            display_name='Outsider',
            birth_date=date(1992, 1, 1),
        )
        self.unverified = User.objects.create_user(
            email='unverified-media@example.test',
            password='TestPass123!',
            display_name='Unverified',
            birth_date=date(1993, 1, 1),
        )
        Profile.objects.filter(user=self.sender).update(city='Paris', country='France')
        Profile.objects.filter(user=self.recipient).update(city='Paris', country='France')
        Profile.objects.filter(user=self.outsider).update(city='Lyon', country='France')
        self.match = Match.objects.create(
            user1=self.sender,
            user2=self.recipient,
            status=Match.ACTIVE,
        )
        for user in (self.sender, self.recipient, self.outsider):
            KycAttempt.objects.create(
                user=user,
                status=KycAttempt.VERIFIED,
                is_open=False,
                expires_at=timezone.now() + timedelta(days=1),
            )

    def _url(self, message):
        return reverse(
            'api:messaging:download-message-media',
            kwargs={'conversation_id': self.match.id, 'message_id': message.id},
        )

    def _message_with_file(self, payload=b'phase-one-media'):
        path = default_storage.save(
            f'messages/{self.match.id}/attachment.mp4',
            ContentFile(payload),
        )
        return Message.objects.create(
            match=self.match,
            sender=self.sender,
            message_type=Message.VIDEO,
            media_file_path=path,
            media_url=default_storage.url(path),
            media_mime_type='video/mp4',
            media_size_bytes=len(payload),
            media_file_name='attachment.mp4',
            media_duration_ms=900,
        )

    def test_participant_gets_metadata_full_and_resumable_media_stream(self):
        payload = b'0123456789'
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            message = self._message_with_file(payload)
            self.client.force_authenticate(self.recipient)

            response = self.client.get(self._url(message))
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response['Content-Type'], 'video/mp4')
            self.assertEqual(response['Accept-Ranges'], 'bytes')
            self.assertEqual(response['Cache-Control'], 'private, no-store, max-age=0')
            self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
            self.assertEqual(b''.join(response.streaming_content), payload)

            resumed = self.client.get(self._url(message), HTTP_RANGE='bytes=4-')
            self.assertEqual(resumed.status_code, status.HTTP_206_PARTIAL_CONTENT)
            self.assertEqual(resumed['Content-Range'], 'bytes 4-9/10')
            self.assertEqual(b''.join(resumed.streaming_content), payload[4:])

            self.client.force_authenticate(self.sender)
            history = self.client.get(
                reverse(
                    'api:messaging:conversation-messages',
                    kwargs={'conversation_id': self.match.id},
                )
            )
            self.assertEqual(history.status_code, status.HTTP_200_OK)
            serialized = history.data['results'][0]
            self.assertEqual(serialized['media_mime_type'], 'video/mp4')
            self.assertEqual(serialized['media_size_bytes'], len(payload))
            self.assertEqual(serialized['media_file_name'], 'attachment.mp4')
            self.assertEqual(serialized['media_duration_ms'], 900)
            self.assertTrue(serialized['media_url'].endswith(self._url(message)))
            self.assertIsNone(serialized['media_thumbnail_url'])
            self.assertTrue(serialized['media_download_url'].endswith(self._url(message)))

    def test_direct_local_media_path_is_not_served(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            message = self._message_with_file()
            response = self.client.get(default_storage.url(message.media_file_path))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_participant_cannot_download_attachment(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            message = self._message_with_file()
            self.client.force_authenticate(self.outsider)
            response = self.client.get(self._url(message))
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_request_cannot_download_attachment(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            message = self._message_with_file()
            response = self.client.get(self._url(message))
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_without_active_kyc_cannot_download_attachment(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            message = self._message_with_file()
            self.client.force_authenticate(self.unverified)
            response = self.client.get(self._url(message))
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_globally_deleted_attachment_cannot_be_downloaded(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            message = self._message_with_file()
            path = message.media_file_path
            with patch('messaging.services.is_premium_user', return_value=True):
                with self.captureOnCommitCallbacks(execute=True):
                    MessageService.delete_messages(
                        user=self.sender,
                        match=self.match,
                        message_ids=[message.id],
                        scope='for_everyone',
                    )

            message.refresh_from_db()
            self.assertTrue(message.is_deleted_for_everyone)
            self.assertFalse(default_storage.exists(path))
            self.client.force_authenticate(self.recipient)
            response = self.client.get(self._url(message))
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
