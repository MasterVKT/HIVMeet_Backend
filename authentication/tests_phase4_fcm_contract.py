"""Contract tests for the FCM token endpoint consumed by Flutter."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

User = get_user_model()


class FCMTokenEndpointContractTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='phase4-fcm-contract@example.test',
            password='testpass123',
            display_name='FCM Contract',
            birth_date=timezone.localdate() - timedelta(days=30 * 365),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_register_accepts_platform_and_delete_accepts_json_body(self):
        token = 'phase4-contract-token'
        response = self.client.post(
            '/api/v1/auth/fcm-token',
            {'fcm_token': token, 'platform': 'android'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(
            self.user.fcm_tokens,
            [{'token': token, 'added_at': self.user.fcm_tokens[0]['added_at'], 'platform': 'android'}],
        )

        response = self.client.delete(
            '/api/v1/auth/fcm-token',
            {'fcm_token': token},
            format='json',
        )
        self.assertEqual(response.status_code, 204)
        self.user.refresh_from_db()
        self.assertEqual(self.user.fcm_tokens, [])
