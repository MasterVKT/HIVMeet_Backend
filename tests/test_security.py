"""
Security tests for HIVMeet backend.
File: tests/test_security.py
"""
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from tests.base import (
    APIBaseTestCase,
    UserFactory,
    ProfileFactory,
    SubscriptionPlanFactory,
)
from profiles.models import Profile, Verification
from matching.models import Match
from messaging.models import Message
from subscriptions.models import PaymentTransaction, Transaction
from subscriptions.payment_gateway import callback_signature
import json
import base64
from decimal import Decimal


class AuthenticationSecurityTest(APIBaseTestCase):
    """Test authentication security measures."""

    @override_settings(AUTH_PASSWORD_VALIDATORS=[
        {
            'NAME': (
                'django.contrib.auth.password_validation.'
                'UserAttributeSimilarityValidator'
            ),
        },
        {
            'NAME': (
                'django.contrib.auth.password_validation.'
                'MinimumLengthValidator'
            ),
            'OPTIONS': {'min_length': 8},
        },
        {
            'NAME': (
                'django.contrib.auth.password_validation.'
                'CommonPasswordValidator'
            ),
        },
        {
            'NAME': (
                'django.contrib.auth.password_validation.'
                'NumericPasswordValidator'
            ),
        },
    ])
    def test_password_requirements(self):
        """Test password validation rules."""
        weak_passwords = [
            'password',      # Too common
            '12345678',      # Only numbers
            'aaaaaaaa',      # Repeating characters
            'Pass123',       # Too short
        ]
        
        for index, password in enumerate(weak_passwords):
            response = self.client.post(reverse('authentication:register'), {
                'email': f'weak-password-{index}@example.com',
                'password': password,
                'password_confirm': password,
                'display_name': 'Test User',
                'birth_date': '1990-01-01',
                'accept_terms': True
            })
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn('password', response.data['details'])
    
    @override_settings(RATELIMIT_ENABLE=True)
    def test_brute_force_protection(self):
        """Test protection against brute force attacks."""
        email = 'testuser@example.com'
        self.create_user(email=email)
        cache.clear()
        
        # Attempt multiple failed logins
        for _ in range(11):
            response = self.client.post(reverse('authentication:login'), {
                'email': email,
                'password': 'wrongpassword'
            }, REMOTE_ADDR='198.51.100.10', HTTP_USER_AGENT='security-test')
        
        # Should be rate limited after 5 attempts
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
    
    def test_jwt_token_security(self):
        """Test JWT token security features."""
        user = self.create_user()
        response = self.client.post(reverse('authentication:login'), {
            'email': user.email,
            'password': 'testpass123'
        })
        
        # Check token structure
        access_token = response.data['access_token']
        parts = access_token.split('.')
        self.assertEqual(len(parts), 3)  # Header, payload, signature
        
        # Verify token contains expected claims
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=='))
        self.assertIn('user_id', payload)
        self.assertIn('exp', payload)  # Expiration
        self.assertIn('iat', payload)  # Issued at
        
        # Test token manipulation detection
        tampered_token = access_token[:-10] + 'tampered'
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tampered_token}')
        response = self.client.get(reverse('api:profiles:my-profile'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DataAccessSecurityTest(APIBaseTestCase):
    """Test data access controls and permissions."""
    
    def setUp(self):
        super().setUp()
        self.user1 = self.create_authenticated_user()
        self.profile1 = ProfileFactory(user=self.user1, is_hidden=False)
        
        self.user2 = self.create_user()
        self.profile2 = ProfileFactory(user=self.user2, is_hidden=False)
        
        self.user3 = self.create_user()
        self.profile3 = ProfileFactory(user=self.user3, allow_profile_in_discovery=False)
    
    def test_profile_visibility_controls(self):
        """Test profile visibility restrictions."""
        # Can see public profile
        response = self.client.get(
            reverse('api:profiles:user-profile', kwargs={'user_id': self.user2.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Cannot see hidden profile
        self.profile2.is_hidden = True
        self.profile2.save()
        response = self.client.get(
            reverse('api:profiles:user-profile', kwargs={'user_id': self.user2.id})
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_conversation_access_control(self):
        """Test conversation access is limited to participants."""
        # Create conversation between user1 and user2
        conv = Match.objects.create(user1=self.user1, user2=self.user2)
        
        # User1 can access
        response = self.client.get(
            reverse(
                'api:messaging:conversation-messages',
                kwargs={'conversation_id': conv.id},
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # User3 cannot access
        self.authenticate(self.user3)
        response = self.client.get(
            reverse(
                'api:messaging:conversation-messages',
                kwargs={'conversation_id': conv.id},
            )
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_verification_data_protection(self):
        """Test verification data is properly protected."""
        verification = Verification.objects.get(user=self.user1)
        verification.status = 'pending_review'
        verification.save(update_fields=['status'])
        
        # Owner can see their verification
        response = self.client.get(reverse('api:profiles:verification-status'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Other users cannot access
        self.authenticate(self.user2)
        # Try to access user1's verification - should get their own or 404
        response = self.client.get(reverse('api:profiles:verification-status'))
        self.assertNotEqual(response.data.get('user_id'), str(self.user1.id))


class InputValidationSecurityTest(APIBaseTestCase):
    """Test input validation and sanitization."""
    
    def test_sql_injection_prevention(self):
        """Test protection against SQL injection."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
            "1; UPDATE users SET is_admin=true WHERE id=1;"
        ]
        
        user = self.create_authenticated_user()
        
        for payload in malicious_inputs:
            # Try in search
            response = self.client.get(
                reverse('api:discovery:discovery'),
                {'search': payload}
            )
            self.assertIn(response.status_code, [200, 400])
            
            # Try in profile update
            response = self.client.patch(
                reverse('api:profiles:my-profile'),
                {'bio': payload}
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # Verify data is properly escaped
            profile = Profile.objects.get(user=user)
            self.assertEqual(profile.bio, payload)  # Should be stored as-is, not executed
    
    def test_xss_prevention(self):
        """Test protection against XSS attacks."""
        xss_payloads = [
            '<script>alert("XSS")</script>',
            '<img src=x onerror=alert("XSS")>',
            'javascript:alert("XSS")',
            '<iframe src="javascript:alert(\'XSS\')"></iframe>'
        ]
        
        user = self.create_authenticated_user()
        ProfileFactory(user=user)
        
        for payload in xss_payloads:
            # Update profile with XSS payload
            response = self.client.patch(
                reverse('api:profiles:my-profile'),
                {'bio': payload}
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # Retrieve and check sanitization
            response = self.client.get(reverse('api:profiles:my-profile'))
            bio = response.data['bio']
            
            # Verify dangerous content is escaped/removed
            self.assertNotIn('<script>', bio)
            self.assertNotIn('onerror=', bio)
    
    def test_file_upload_validation(self):
        """Test file upload security."""
        user = self.create_authenticated_user()
        ProfileFactory(user=user)
        
        # Test malicious file extensions
        dangerous_files = [
            ('malicious.exe', b'MZ\x90\x00'),  # Executable
            ('script.js', b'alert("XSS")'),     # JavaScript
            ('shell.php', b'<?php system($_GET["cmd"]); ?>'),  # PHP
        ]
        
        for filename, content in dangerous_files:
            upload = SimpleUploadedFile(
                filename,
                content,
                content_type='application/octet-stream',
            )
            response = self.client.post(
                reverse('api:profiles:upload-photo'),
                {'file': upload},
                format='multipart'
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test file size limit
        large_file = SimpleUploadedFile(
            'large.jpg',
            b'x' * (5 * 1024 * 1024 + 1),
            content_type='image/jpeg',
        )
        response = self.client.post(
            reverse('api:profiles:upload-photo'),
            {'file': large_file},
            format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class WebhookSecurityTest(TestCase):
    """Test the documented MyCoolPay callback contract."""

    def setUp(self):
        self.client = self.client_class()
        self.public_key = 'test_public_key'
        self.private_key = 'test_private_key'
        self.webhook_url = reverse('api:mycoolpay-webhook')

    def _payload(self, payment=None):
        return {
            'application': self.public_key,
            'app_transaction_ref': (
                payment.app_transaction_ref if payment else 'hivmeet_unknown'
            ),
            'transaction_ref': (
                payment.provider_transaction_ref if payment else 'provider_unknown'
            ),
            'transaction_type': 'PAYIN',
            'transaction_amount': '999',
            'transaction_currency': 'XAF',
            'transaction_operator': 'CM_OM',
            'transaction_status': 'SUCCESS',
            'transaction_message': 'Successful transaction',
        }

    def test_webhook_signature_validation(self):
        payload = self._payload()
        with self.settings(
            MYCOOLPAY_PUBLIC_KEY=self.public_key,
            MYCOOLPAY_PRIVATE_KEY=self.private_key,
            MYCOOLPAY_CALLBACK_ALLOWED_IPS=('127.0.0.1',),
        ):
            unsigned_response = self.client.post(
                self.webhook_url,
                json.dumps(payload),
                content_type='application/json',
                REMOTE_ADDR='127.0.0.1',
            )
            self.assertEqual(unsigned_response.status_code, status.HTTP_400_BAD_REQUEST)

            payload['signature'] = 'invalid_signature'
            response = self.client.post(
                self.webhook_url,
                json.dumps(payload),
                content_type='application/json',
                REMOTE_ADDR='127.0.0.1',
            )
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_webhook_replay_protection(self):
        user = UserFactory()
        plan = SubscriptionPlanFactory(price=Decimal('999'), currency='XAF')
        payment = PaymentTransaction.objects.create(
            user=user,
            plan=plan,
            amount=Decimal('999'),
            currency='XAF',
            provider_transaction_ref='provider_replay_test',
            status=PaymentTransaction.STATUS_PENDING,
        )
        payload = self._payload(payment)
        payload['signature'] = callback_signature(payload, self.private_key)

        with self.settings(
            MYCOOLPAY_PUBLIC_KEY=self.public_key,
            MYCOOLPAY_PRIVATE_KEY=self.private_key,
            MYCOOLPAY_CALLBACK_ALLOWED_IPS=('127.0.0.1',),
        ):
            response = self.client.post(
                self.webhook_url,
                json.dumps(payload),
                content_type='application/json', REMOTE_ADDR='127.0.0.1'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            response = self.client.post(
                self.webhook_url,
                json.dumps(payload),
                content_type='application/json', REMOTE_ADDR='127.0.0.1'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        payment.refresh_from_db()
        self.assertTrue(payment.is_fulfilled)
        self.assertEqual(
            Transaction.objects.filter(
                transaction_id='provider_replay_test'
            ).count(),
            1,
        )


class PrivacyComplianceTest(APIBaseTestCase):
    """Test GDPR/privacy compliance features."""
    
    def setUp(self):
        super().setUp()
        self.user = self.create_authenticated_user()
        ProfileFactory(user=self.user)
        
        # Create some user data
        other_user = self.create_user()
        ProfileFactory(user=other_user)
        
        # Create conversation and messages
        conv = Match.objects.create(user1=self.user, user2=other_user)
        Message.objects.create(
            match=conv,
            sender=self.user,
            content='Test message'
        )
    
    def test_data_export(self):
        """Test user data export functionality."""
        response = self.client.post(reverse('api:user_settings:export-data'))
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        data = response.json()
        self.assertEqual(data['action_type'], 'data_export')
        self.assertEqual(data['status'], 'pending')
        self.assertNotIn('email', data)
    
    def test_data_deletion(self):
        """Test account deletion and data anonymization."""
        user_id = self.user.id
        
        response = self.client.post(
            reverse('api:user_settings:delete-account'),
            {'confirm': True, 'password': 'testpass123'}
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['action_type'], 'account_deletion')
        self.assertEqual(response.data['status'], 'pending')

        # Deletion is deliberately deferred until email confirmation and the
        # grace period have elapsed; the authenticated session remains valid.
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(id=user_id)
        self.assertTrue(user.is_active)
        self.assertIsNotNone(Message.objects.filter(sender=user).first())
