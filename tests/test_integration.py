"""
Integration tests for HIVMeet backend.
File: tests/test_integration.py
"""
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from rest_framework import status
from tests.base import APIBaseTestCase, ProfileFactory
from profiles.models import KycAttempt, Profile
from matching.models import Like, Match
from messaging.models import Message
from subscriptions.models import SubscriptionPlan, Subscription
from unittest.mock import Mock, patch
import uuid


User = get_user_model()


def grant_active_kyc(user):
    """Make a fixture eligible for a protected social/Premium journey."""
    return KycAttempt.objects.create(
        user=user,
        status=KycAttempt.VERIFIED,
        is_open=False,
        expires_at=timezone.now() + timedelta(days=1),
    )


class UserRegistrationFlowTest(APIBaseTestCase):
    """Test complete user registration and profile creation flow."""
    
    @patch('profiles.views.storage_manager.upload_image')
    @patch('authentication.views.send_verification_email')
    @patch('authentication.views._firebase_service')
    def test_complete_registration_flow(
        self,
        firebase_service_factory,
        send_verification_email,
        upload_image,
    ):
        """Test full registration process from signup to profile completion."""
        firebase_service = firebase_service_factory.return_value
        firebase_service.create_user.return_value = Mock(uid='firebase-test-user')
        upload_image.return_value = {
            'main': 'https://storage.test/profile.jpg',
            'thumbnail': 'https://storage.test/profile-thumb.jpg',
        }
        # 1. Register new user
        registration_data = {
            'email': 'newuser@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'display_name': 'New User',
            'birth_date': '1990-01-01',
            'gender': 'male',
            'accept_terms': True
        }
        
        response = self.client.post(reverse('authentication:register'), registration_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('user_id', response.data)
        firebase_service.create_user.assert_called_once()
        send_verification_email.assert_called_once()
        
        # 2. Authenticate
        user = User.objects.get(id=response.data['user_id'])
        self.client.force_authenticate(user=user)
        
        # 3. Create profile
        profile_data = {
            'bio': 'Test bio',
            'gender': 'male',
            'interests': ['sports', 'music'],
            'city': 'Paris',
            'country': 'France',
            'latitude': 48.8566,
            'longitude': 2.3522,
            'relationship_types_sought': ['friendship', 'long_term'],
            'age_min_preference': 25,
            'age_max_preference': 40,
            'distance_max_km': 50,
            'genders_sought': ['female']
        }
        
        response = self.client.put(
            reverse('api:profiles:my-profile'),
            profile_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 4. Upload profile photo
        photo_file = self.create_image_file()
        response = self.client.post(
            reverse('api:profiles:upload-photo'),
            {'file': photo_file, 'is_main': True},
            format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # 5. Verify complete profile
        response = self.client.get(reverse('api:profiles:my-profile'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['bio'], 'Test bio')
        self.assertEqual(len(response.data['photos']), 1)


class MatchingFlowTest(APIBaseTestCase):
    """Test complete matching flow from discovery to match creation."""
    
    def setUp(self):
        super().setUp()
        # Create test users with profiles
        self.user1 = self.create_authenticated_user()
        self.profile1 = ProfileFactory(
            user=self.user1,
            bio='User 1 bio',
            gender='male',
            city='Paris',
            country='France',
            latitude=48.8566,
            longitude=2.3522
        )
        
        self.user2 = self.create_user()
        self.profile2 = ProfileFactory(
            user=self.user2,
            bio='User 2 bio',
            gender='female',
            city='Paris',
            country='France',
            latitude=48.8600,
            longitude=2.3500
        )
        grant_active_kyc(self.user1)
        grant_active_kyc(self.user2)
    
    def test_discovery_to_match_flow(self):
        """Test discovering profiles and creating a match."""
        # 1. Get recommended profiles
        response = self.client.get(reverse('api:discovery:discovery'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data['results']), 0)
        
        # 2. User 1 likes User 2
        response = self.client.post(
            reverse('api:discovery:like'),
            {'target_user_id': str(self.user2.id)}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'liked')
        
        # 3. User 2 likes User 1 back
        self.authenticate(self.user2)
        response = self.client.post(
            reverse('api:discovery:like'),
            {'target_user_id': str(self.user1.id)}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'matched')
        
        # 4. Verify match exists for both users
        response = self.client.get(reverse('api:matches:list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
        self.authenticate(self.user1)
        response = self.client.get(reverse('api:matches:list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class MessagingFlowTest(APIBaseTestCase):
    """Test complete messaging flow."""
    
    def setUp(self):
        super().setUp()
        # Create matched users
        self.user1 = self.create_authenticated_user()
        self.user2 = self.create_user()
        
        ProfileFactory(user=self.user1)
        ProfileFactory(user=self.user2)
        
        # Create match
        self.match = Match.objects.create(user1=self.user1, user2=self.user2)
        grant_active_kyc(self.user1)
        grant_active_kyc(self.user2)
    
    def test_messaging_flow(self):
        """Test sending and receiving messages."""
        # 1. Send the first message; empty matches are deliberately absent
        # from the conversation list until they contain activity.
        conversation_id = self.match.id
        message_data = {
            'client_message_id': str(uuid.uuid4()),
            'content': 'Hello from user 1!',
            'type': 'text',
        }
        response = self.client.post(
            reverse(
                'api:messaging:conversation-messages',
                kwargs={'conversation_id': conversation_id},
            ),
            message_data,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(reverse('api:messaging:conversation-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
        # 3. User 2 receives message
        self.authenticate(self.user2)
        response = self.client.get(
            reverse(
                'api:messaging:conversation-messages',
                kwargs={'conversation_id': conversation_id},
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['content'], 'Hello from user 1!')
        
        # 4. User 2 replies
        reply_data = {
            'client_message_id': str(uuid.uuid4()),
            'content': 'Hello back from user 2!',
            'type': 'text',
        }
        response = self.client.post(
            reverse(
                'api:messaging:conversation-messages',
                kwargs={'conversation_id': conversation_id},
            ),
            reply_data,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class PremiumSubscriptionFlowTest(APIBaseTestCase):
    """Test premium subscription flow."""
    
    def setUp(self):
        super().setUp()
        self.user = self.create_authenticated_user()
        ProfileFactory(user=self.user)
        
        # Create test plan
        self.plan = SubscriptionPlan.objects.create(
            plan_id='test_monthly',
            name='Test Monthly',
            name_en='Test Monthly',
            name_fr='Test Mensuel',
            price=9.99,
            currency='EUR',
            billing_interval='month',
            monthly_boosts_count=1,
            daily_super_likes_count=5
        )
        grant_active_kyc(self.user)
    
    def test_premium_purchase_and_features(self):
        """Test purchasing premium and using premium features."""
        # 1. Check initial status (non-premium)
        response = self.client.get(reverse('api:subscriptions:current'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'none')
        
        # 2. Purchase subscription
        with self.settings(MYCOOLPAY_BASE_URL='http://mock-mycoolpay.test'):
            # Mock payment success
            purchase_data = {
                'plan_id': 'test_monthly',
                'payment_method_token': 'pm_test_token'
            }
            
            # This would normally interact with MyCoolPay
            # For testing, we'll create the subscription directly
            subscription = Subscription.objects.create(
                subscription_id='sub_test123',
                user=self.user,
                plan=self.plan,
                status='active',
                current_period_start=timezone.now(),
                current_period_end=timezone.now() + timezone.timedelta(days=30),
                boosts_remaining=1,
                super_likes_remaining=5
            )
        
        # 3. Verify premium status
        response = self.client.get(reverse('api:subscriptions:current'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'active')
        self.assertTrue(response.data['features_summary']['can_see_likers'])
        
        # 4. Test premium feature - see who liked you
        other_user = self.create_user()
        ProfileFactory(user=other_user)
        Like.objects.create(from_user=other_user, to_user=self.user)
        
        response = self.client.get(reverse('api:profiles:likes-received'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class VerificationFlowTest(APIBaseTestCase):
    """Test the safe KYC v1 entry point and retired legacy contract."""
    
    def setUp(self):
        super().setUp()
        self.user = self.create_authenticated_user()
        ProfileFactory(user=self.user)
    
    def test_verification_flow(self):
        """Legacy paths stay closed; the challenge only comes from KYC start."""
        # Status never leaks a legacy document path or selfie code.
        response = self.client.get(reverse('api:profiles:verification-status'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'not_started')
        self.assertNotIn('verification_code', response.data)
        self.assertNotIn('documents_path', response.data)

        legacy_upload = self.client.post(
            reverse('api:profiles:generate-upload-url'),
            {'document_type': 'identity_document'},
            format='json',
        )
        self.assertEqual(legacy_upload.status_code, status.HTTP_410_GONE)
        legacy_submit = self.client.post(
            reverse('api:profiles:submit-documents'),
            {'documents': [], 'selfie_code_used': 'legacy-code'},
            format='json',
        )
        self.assertEqual(legacy_submit.status_code, status.HTTP_410_GONE)

        # The single-use challenge is emitted only by the authenticated start
        # operation; upload intents and technical validation are covered by
        # the dedicated phase-2 suite.
        started = self.client.post(
            reverse('api:profiles:kyc-start'),
            {
                'consent_version': 'kyc-v1-test',
                'confirmations': {
                    'official_identity_document': True,
                    'medical_document_under_90_days': True,
                    'single_use_selfie_challenge': True,
                    'human_review_acknowledged': True,
                },
                'idempotency_key': 'integration-kyc-start-0001',
            },
            format='json',
        )
        self.assertEqual(started.status_code, status.HTTP_201_CREATED)
        self.assertIn('code', started.data['selfie_challenge'])

        response = self.client.get(reverse('api:profiles:verification-status'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], KycAttempt.PENDING_ID)
        self.assertNotIn('verification_code', response.data)
