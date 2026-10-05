from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class FCMTokenCrossAccountTest(TestCase):
    """A device's FCM registration token must never be listed on more than
    one account at a time, otherwise both accounts receive each other's
    push notifications (observed symptom: a like's push reaching the liker
    as well as the liked user, after both had used the same device/emulator
    across different test accounts)."""

    def setUp(self):
        self.user_a = User.objects.create_user(
            email='fcm_a@example.com',
            password='testpass123',
            display_name='User A',
            birth_date=date(1990, 1, 1),
        )
        self.user_b = User.objects.create_user(
            email='fcm_b@example.com',
            password='testpass123',
            display_name='User B',
            birth_date=date(1990, 1, 1),
        )

    def test_add_fcm_token_attaches_it_to_the_user(self):
        self.user_a.add_fcm_token('token-1', device_id='dev-1', platform='android')

        self.assertEqual(len(self.user_a.fcm_tokens), 1)
        self.assertEqual(self.user_a.fcm_tokens[0]['token'], 'token-1')

    def test_add_fcm_token_detaches_it_from_every_other_account(self):
        # User A logs in on a device first.
        self.user_a.add_fcm_token('shared-token', platform='android')
        self.assertEqual(len(self.user_a.fcm_tokens), 1)

        # The same device later logs in as User B (e.g. a shared test
        # emulator, or a re-install without a clean logout) and registers
        # the *same* FCM token.
        self.user_b.add_fcm_token('shared-token', platform='android')

        self.user_a.refresh_from_db()
        self.user_b.refresh_from_db()

        # The token must now belong to B only — A must no longer receive
        # pushes intended for B.
        self.assertEqual(self.user_a.fcm_tokens, [])
        self.assertEqual(len(self.user_b.fcm_tokens), 1)
        self.assertEqual(self.user_b.fcm_tokens[0]['token'], 'shared-token')

    def test_add_fcm_token_does_not_disturb_other_tokens_on_other_accounts(self):
        self.user_a.add_fcm_token('token-a-only', platform='android')
        self.user_b.add_fcm_token('token-b-only', platform='ios')

        # Registering an unrelated token for A must not touch B's own token.
        self.user_a.add_fcm_token('token-a-second', platform='android')

        self.user_b.refresh_from_db()
        self.assertEqual(
            {t['token'] for t in self.user_b.fcm_tokens}, {'token-b-only'}
        )

    def test_remove_fcm_token_only_removes_the_given_token(self):
        self.user_a.add_fcm_token('token-1')
        self.user_a.add_fcm_token('token-2')

        self.user_a.remove_fcm_token('token-1')

        self.assertEqual(
            {t['token'] for t in self.user_a.fcm_tokens}, {'token-2'}
        )


class LogoutViewFCMTokenTest(APITestCase):
    """POST /api/v1/auth/logout should also detach the caller's FCM token
    when provided, so a device that successfully calls this endpoint stops
    receiving push notifications for the account it just left."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='logout_fcm@example.com',
            password='testpass123',
            display_name='Logout User',
            birth_date=date(1990, 1, 1),
        )
        self.user.add_fcm_token('device-token')
        self.client.force_authenticate(user=self.user)

    def test_logout_removes_the_provided_fcm_token(self):
        response = self.client.post(
            '/api/v1/auth/logout',
            {'fcm_token': 'device-token'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.user.refresh_from_db()
        self.assertEqual(self.user.fcm_tokens, [])

    def test_logout_without_fcm_token_still_succeeds(self):
        response = self.client.post('/api/v1/auth/logout', {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.user.refresh_from_db()
        # Token untouched — the client didn't ask to remove it.
        self.assertEqual(len(self.user.fcm_tokens), 1)
