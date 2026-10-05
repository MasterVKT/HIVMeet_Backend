from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from authentication.models import User


class RegistrationContractTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.payload = {
            'email': 'phase4-register@example.test',
            'password': 'StrongPassword123!',
            'password_confirm': 'StrongPassword123!',
            'display_name': 'Phase Four',
            'birth_date': '1990-01-01',
            'phone_number': '+33612345678',
            'gender': 'female',
        }

    @patch('authentication.views.send_verification_email')
    @patch('authentication.views._firebase_service')
    def test_registration_creates_linked_profile_with_required_gender(self, firebase_service, _mail):
        firebase_service.return_value.create_user.return_value = SimpleNamespace(uid='firebase-phase4')
        response = self.client.post('/api/v1/auth/register/', self.payload, format='json')
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email=self.payload['email'])
        self.assertEqual(user.firebase_uid, 'firebase-phase4')
        self.assertEqual(user.profile.gender, 'female')
        self.assertFalse(user.profile.gender_confirmation_required)

    @patch('authentication.views.send_verification_email', side_effect=RuntimeError('mail unavailable'))
    @patch('authentication.views._firebase_service')
    def test_email_delivery_failure_does_not_split_a_committed_account(self, firebase_service, _mail):
        firebase_service.return_value.create_user.return_value = SimpleNamespace(uid='firebase-mail-failure')
        response = self.client.post('/api/v1/auth/register/', self.payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(email=self.payload['email']).exists())
        firebase_service.return_value.delete_user.assert_not_called()

    def test_registration_rejects_missing_gender_before_firebase_provisioning(self):
        payload = dict(self.payload)
        payload.pop('gender')
        response = self.client.post('/api/v1/auth/register/', payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('gender', response.data['details'])
        self.assertEqual(User.objects.count(), 0)

    @patch('firebase_admin.auth.verify_id_token')
    def test_firebase_exchange_never_creates_an_unregistered_account(self, verify_token):
        verify_token.return_value = {
            'uid': 'unknown-firebase-user',
            'email': 'not-registered@example.test',
            'email_verified': True,
        }
        response = self.client.post('/api/v1/auth/firebase-exchange/', {'firebase_token': 'test'}, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'registration_required')
        self.assertEqual(User.objects.count(), 0)

    @override_settings(HIVMEET_REQUIRE_EXPLICIT_REGISTRATION=False)
    @patch('firebase_admin.auth.verify_id_token')
    def test_transition_bridge_creates_no_discoverable_gendered_profile(self, verify_token):
        verify_token.return_value = {
            'uid': 'transition-firebase-user', 'email': 'transition@example.test',
            'name': 'Transition', 'email_verified': True,
        }
        response = self.client.post('/api/v1/auth/firebase-exchange/', {'firebase_token': 'test'}, format='json')
        self.assertEqual(response.status_code, 200)
        profile = User.objects.get(email='transition@example.test').profile
        self.assertEqual(profile.gender, '')
        self.assertTrue(profile.gender_confirmation_required)
        self.assertNotIn(profile.gender, {'male', 'female'})

    @patch('firebase_admin.auth.verify_id_token')
    def test_old_local_account_can_only_be_linked_to_its_matching_email(self, verify_token):
        user = User.objects.create_user(
            email='legacy@example.test', password='password', display_name='Legacy',
            birth_date=date(1990, 1, 1),
        )
        verify_token.return_value = {
            'uid': 'legacy-firebase-user', 'email': user.email, 'email_verified': True,
        }
        response = self.client.post('/api/v1/auth/firebase-exchange/', {'firebase_token': 'test'}, format='json')
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.firebase_uid, 'legacy-firebase-user')
