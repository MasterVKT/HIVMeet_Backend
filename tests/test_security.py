"""
Security tests for HIVMeet backend.
File: tests/test_security.py
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from tests.base import APIBaseTestCase, UserFactory, ProfileFactory
from profiles.models import Profile, Verification
from messaging.models import Conversation, Message
import json
import base64
import hashlib
import hmac


class AuthenticationSecurityTest(APIBaseTestCase):
    """Test authentication security measures."""
    
    def test_password_requirements(self):
        """Test password validation rules."""
        weak_passwords = [
            'password',      # Too common
            '12345678',      # Only numbers
            'aaaaaaaa',      # Repeating characters
            'Pass123',       # Too short
        ]
        
        for password in weak_passwords:
            response = self.client.post(reverse('authentication:register'), {
                'email': f'test{password}@example.com',
                'password': password,
                'password_confirm': password,
                'display_name': 'Test User',
                'birth_date': '1990-01-01',
                'accept_terms': True
            })
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn('password', response.data)
    
    def test_brute_force_protection(self):
        """Test protection against brute force attacks."""
        email = 'testuser@example.com'
        user = self.create_user(email=email)
        
        # Attempt multiple failed logins
        for i in range(6):
            response = self.client.post(reverse('authentication:login'), {
                'email': email,
                'password': 'wrongpassword'
            })
        
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
        access_token = response.data['access']
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
        response = self.client.get(reverse('profiles:my-profile'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DataAccessSecurityTest(APIBaseTestCase):
    """Test data access controls and permissions."""
    
    def setUp(self):
        super().setUp()
        self.user1 = self.create_authenticated_user()
        self.profile1 = ProfileFactory(user=self.user1, is_hidden=False)
        
        self.user2 = self.create_user()
        self.profile2 = ProfileFactory(user=self.user2, is_hidden=True)
        
        self.user3 = self.create_user()
        self.profile3 = ProfileFactory(user=self.user3, allow_profile_in_discovery=False)
    
    def test_profile_visibility_controls(self):
        """Test profile visibility restrictions."""
        # Can see public profile
        response = self.client.get(
            reverse('profiles:user-profile', kwargs={'user_id': self.user2.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Cannot see hidden profile
        self.profile2.is_hidden = True
        self.profile2.save()
        response = self.client.get(
            reverse('profiles:user-profile', kwargs={'user_id': self.user2.id})
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_conversation_access_control(self):
        """Test conversation access is limited to participants."""
        # Create conversation between user1 and user2
        conv = Conversation.objects.create()
        conv.participants.add(self.user1, self.user2)
        
        # User1 can access
        response = self.client.get(
            reverse('messaging:messages', kwargs={'conversation_id': conv.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # User3 cannot access
        self.authenticate(self.user3)
        response = self.client.get(
            reverse('messaging:messages', kwargs={'conversation_id': conv.id})
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_verification_data_protection(self):
        """Test verification data is properly protected."""
        verification = Verification.objects.create(
            user=self.user1,
            status='pending_review'
        )
        
        # Owner can see their verification
        response = self.client.get(reverse('profiles:verification-status'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Other users cannot access
        self.authenticate(self.user2)
        # Try to access user1's verification - should get their own or 404
        response = self.client.get(reverse('profiles:verification-status'))
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
                reverse('discovery:recommended-profiles'),
                {'search': payload}
            )
            self.assertIn(response.status_code, [200, 400])
            
            # Try in profile update
            response = self.client.patch(
                reverse('profiles:my-profile'),
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
                reverse('profiles:my-profile'),
                {'bio': payload}
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # Retrieve and check sanitization
            response = self.client.get(reverse('profiles:my-profile'))
            bio = response.data['bio']
            
            # Verify dangerous content is escaped/removed
            self.assertNotIn('<script>', bio)
            self.assertNotIn('javascript:', bio)
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
            response = self.client.post(
                reverse('profiles:upload-photo'),
                {'photo': (filename, content)},
                format='multipart'
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test file size limit
        large_file = b'x' * (10 * 1024 * 1024 + 1)  # 10MB + 1 byte
        response = self.client.post(
            reverse('profiles:upload-photo'),
            {'photo': ('large.jpg', large_file, 'image/jpeg')},
            format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class WebhookSecurityTest(TestCase):
    """Test webhook security."""
    
    def setUp(self):
        self.client = self.client_class()
        self.webhook_secret = 'test_webhook_secret'
        self.webhook_url = reverse('mycoolpay-webhook')
    
    def generate_signature(self, payload, secret):
        """Generate webhook signature."""
        return hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def test_webhook_signature_validation(self):
        """Test webhook signature is validated."""
        payload = json.dumps({
            'event_id': 'evt_123',
            'event_type': 'payment.succeeded',
            'data': {'amount': 999},
            'timestamp': '2024-01-01T00:00:00Z'
        })
        
        # Request without signature
        response = self.client.post(
            self.webhook_url,
            payload,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Request with invalid signature
        response = self.client.post(
            self.webhook_url,
            payload,
            content_type='application/json',
            HTTP_X_MYCOOLPAY_SIGNATURE='invalid_signature'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Request with valid signature
        with self.settings(MYCOOLPAY_WEBHOOK_SECRET=self.webhook_secret):
            valid_signature = self.generate_signature(payload, self.webhook_secret)
            response = self.client.post(
                self.webhook_url,
                payload,
                content_type='application/json',
                HTTP_X_MYCOOLPAY_SIGNATURE=valid_signature
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_webhook_replay_protection(self):
        """Test protection against webhook replay attacks."""
        payload = json.dumps({
            'event_id': 'evt_replay_test',
            'event_type': 'payment.succeeded',
            'data': {'amount': 999},
            'timestamp': '2024-01-01T00:00:00Z'
        })
        
        with self.settings(MYCOOLPAY_WEBHOOK_SECRET=self.webhook_secret):
            signature = self.generate_signature(payload, self.webhook_secret)
            headers = {'HTTP_X_MYCOOLPAY_SIGNATURE': signature}
            
            # First request should succeed
            response = self.client.post(
                self.webhook_url,
                payload,
                content_type='application/json',
                **headers
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # Replay should be detected
            response = self.client.post(
                self.webhook_url,
                payload,
                content_type='application/json',
                **headers
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.json()['status'], 'already_processed')


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
        conv = Conversation.objects.create()
        conv.participants.add(self.user, other_user)
        Message.objects.create(
            conversation=conv,
            sender=self.user,
            content='Test message'
        )
    
    def test_data_export(self):
        """Test user data export functionality."""
        response = self.client.get(reverse('authentication:export-data'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertIn('user', data)
        self.assertIn('profile', data)
        self.assertIn('messages_sent', data)
        
        # Verify sensitive data is included for owner
        self.assertEqual(data['user']['email'], self.user.email)
    
    def test_data_deletion(self):
        """Test account deletion and data anonymization."""
        user_id = self.user.id
        
        response = self.client.post(
            reverse('authentication:delete-account'),
            {'confirm': True, 'password': 'testpass123'}
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify user is deactivated
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(id=user_id)
        self.assertFalse(user.is_active)
        
        # Verify personal data is anonymized
        self.assertTrue(user.email.startswith('deleted_'))
        self.assertEqual(user.display_name, 'Deleted User')
        
        # Verify messages are preserved but anonymized
        message = Message.objects.filter(sender=user).first()
        self.assertIsNotNone(message)  # Message still exists
        self.assertEqual(message.sender.display_name, 'Deleted User')