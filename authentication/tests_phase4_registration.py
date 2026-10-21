from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from rest_framework.test import APIClient

from authentication.middleware import FirebaseAuthenticationMiddleware
from authentication.models import User


class RegistrationContractTests(TestCase):
    def setUp(self):
        # Throttle counters live in the shared cache; each test starts clean.
        cache.clear()
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

    @patch('authentication.views._firebase_service')
    def test_registration_creates_linked_profile_with_required_gender(self, firebase_service):
        firebase_service.return_value.create_user.return_value = SimpleNamespace(uid='firebase-phase4')
        response = self.client.post('/api/v1/auth/register/', self.payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['verification_required'])
        self.assertNotIn('email', response.data)
        user = User.objects.get(email=self.payload['email'])
        self.assertEqual(user.firebase_uid, 'firebase-phase4')
        self.assertEqual(user.profile.gender, 'female')
        self.assertFalse(user.profile.gender_confirmation_required)

    @patch('authentication.views._firebase_service')
    def test_registration_does_not_emit_a_legacy_verification_email(self, firebase_service):
        firebase_service.return_value.create_user.return_value = SimpleNamespace(uid='firebase-no-legacy-email')
        response = self.client.post('/api/v1/auth/register/', self.payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(email=self.payload['email']).exists())
        firebase_service.return_value.delete_user.assert_not_called()

    @patch('firebase_admin.auth.verify_id_token')
    def test_unverified_firebase_identity_cannot_receive_django_tokens(self, verify_token):
        verify_token.return_value = {
            'uid': 'unverified-firebase-user',
            'email': 'not-verified@example.test',
            'email_verified': False,
        }
        response = self.client.post('/api/v1/auth/firebase-exchange/', {'firebase_token': 'test'}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['code'], 'email_not_verified')
        self.assertEqual(User.objects.count(), 0)

    def test_an_old_access_token_is_refused_when_email_is_not_verified(self):
        user = User.objects.create_user(
            email='old-token@example.test', password='password', display_name='Old token',
            birth_date=date(1990, 1, 1), email_verified=False,
        )
        from rest_framework_simplejwt.tokens import RefreshToken
        access = str(RefreshToken.for_user(user).access_token)
        response = self.client.post(
            '/api/v1/auth/logout/',
            HTTP_AUTHORIZATION=f'Bearer {access}',
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['error'], 'email_not_verified')

    @patch('authentication.views._firebase_service')
    def test_refresh_refuses_an_unverified_firebase_account(self, firebase_service):
        user = User.objects.create_user(
            email='refresh-unverified@example.test', password='password',
            display_name='Refresh token', birth_date=date(1990, 1, 1),
            firebase_uid='refresh-unverified', email_verified=False,
        )
        firebase_service.return_value.get_user.return_value = SimpleNamespace(
            email=user.email,
            email_verified=False,
        )
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = str(RefreshToken.for_user(user))
        response = self.client.post(
            '/api/v1/auth/refresh-token/', {'refresh_token': refresh}, format='json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['code'], 'email_not_verified')

    @patch('authentication.views._firebase_service')
    def test_password_login_refuses_when_firebase_record_is_unverified(self, firebase_service):
        user = User.objects.create_user(
            email='login-unverified@example.test', password='StrongPassword123!',
            display_name='Password login', birth_date=date(1990, 1, 1),
            firebase_uid='login-unverified', email_verified=True,
        )
        firebase_service.return_value.get_user.return_value = SimpleNamespace(
            email=user.email,
            email_verified=False,
        )
        response = self.client.post('/api/v1/auth/login/', {
            'email': user.email,
            'password': 'StrongPassword123!',
        }, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['code'], 'email_not_verified')
        user.refresh_from_db()
        self.assertFalse(user.email_verified)

    def test_registration_rejects_missing_gender_before_firebase_provisioning(self):
        payload = dict(self.payload)
        payload.pop('gender')
        response = self.client.post('/api/v1/auth/register/', payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('gender', response.data['details'])
        self.assertEqual(User.objects.count(), 0)

    @patch('authentication.views._firebase_service')
    def test_registration_accepts_apostrophes_in_display_name(self, firebase_service):
        firebase_service.return_value.create_user.return_value = SimpleNamespace(uid='firebase-apostrophe')
        payload = dict(self.payload)
        payload['display_name'] = "N'Guessan"
        response = self.client.post('/api/v1/auth/register/', payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(email=self.payload['email']).exists())

    def test_registration_reports_a_short_phone_with_a_stable_field_code(self):
        payload = dict(self.payload)
        payload['phone_number'] = '0102030'
        response = self.client.post('/api/v1/auth/register/', payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'registration_invalid')
        self.assertEqual(response.data['field_errors']['phone_number'], ['invalid'])
        self.assertIn('phone_number', response.data['details'])
        self.assertEqual(User.objects.count(), 0)

    def test_registration_reports_a_duplicate_email_with_a_stable_field_code(self):
        User.objects.create_user(
            email=self.payload['email'], password='StrongPassword123!',
            display_name='Existing account', birth_date=date(1990, 1, 1),
        )
        response = self.client.post('/api/v1/auth/register/', self.payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'registration_invalid')
        self.assertEqual(response.data['field_errors']['email'], ['unique'])

    def test_registration_reports_a_common_password_with_a_stable_field_code(self):
        payload = dict(self.payload)
        payload['password'] = 'Password1!'
        payload['password_confirm'] = 'Password1!'
        response = self.client.post('/api/v1/auth/register/', payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            'password_too_common',
            response.data['field_errors']['password'],
        )
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

    @patch('firebase_admin.auth.verify_id_token')
    def test_firebase_exchange_never_recreates_an_account_when_the_setting_is_false(self, verify_token):
        verify_token.return_value = {
            'uid': 'transition-firebase-user', 'email': 'transition@example.test',
            'name': 'Transition', 'email_verified': True,
        }
        response = self.client.post('/api/v1/auth/firebase-exchange/', {'firebase_token': 'test'}, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'registration_required')
        self.assertFalse(User.objects.filter(email='transition@example.test').exists())

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


class AuthenticationMiddlewareVerificationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _run_middleware(self, request):
        middleware = FirebaseAuthenticationMiddleware(
            lambda _request: HttpResponse(status=204)
        )
        middleware(request)
        return request.user

    def test_old_jwt_is_anonymous_when_email_is_not_verified(self):
        user = User.objects.create_user(
            email='middleware-jwt@example.test', password='password',
            display_name='Middleware JWT', birth_date=date(1990, 1, 1),
            email_verified=False,
        )
        from rest_framework_simplejwt.tokens import RefreshToken

        request = self.factory.get(
            '/', HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}',
        )
        authenticated_user = self._run_middleware(request)
        self.assertFalse(authenticated_user.is_authenticated)

    @patch('hivmeet_backend.firebase_service.firebase_service.verify_id_token')
    def test_firebase_header_is_anonymous_without_verified_claim(self, verify_id_token):
        user = User.objects.create_user(
            email='middleware-firebase@example.test', password='password',
            display_name='Middleware Firebase', birth_date=date(1990, 1, 1),
            firebase_uid='middleware-firebase-uid', email_verified=True,
        )
        verify_id_token.return_value = {
            'uid': user.firebase_uid,
            'email': user.email,
            'email_verified': False,
        }

        request = self.factory.get('/', HTTP_AUTHORIZATION='Firebase test-token')
        authenticated_user = self._run_middleware(request)
        self.assertFalse(authenticated_user.is_authenticated)
