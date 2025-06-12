"""
Integration tests for HIVMeet backend.
File: tests/test_integration.py
"""
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from tests.base import APIBaseTestCase
from profiles.models import Profile
from matching.models import Like, Match
from messaging.models import Conversation, Message
from subscriptions.models import SubscriptionPlan, Subscription
import json


class UserRegistrationFlowTest(APIBaseTestCase):
    """Test complete user registration and profile creation flow."""
    
    def test_complete_registration_flow(self):
        """Test full registration process from signup to profile completion."""
        # 1. Register new user
        registration_data = {
            'email': 'newuser@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'display_name': 'New User',
            'birth_date': '1990-01-01',
            'accept_terms': True
        }
        
        response = self.client.post(reverse('authentication:register'), registration_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('user', response.data)
        self.assertIn('access', response.data)
        
        # 2. Authenticate
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
        
        # 3. Create profile
        profile_data = {
            'bio': 'Test bio',
            'gender': 'male',
            'interests': ['sports', 'music'],
            'city': 'Paris',
            'country': 'France',
            'latitude': 48.8566,
            'longitude': 2.3522,
            'relationship_types_sought': ['friendship', 'long_term_relationship'],
            'age_min_preference': 25,
            'age_max_preference': 40,
            'distance_max_km': 50,
            'genders_sought': ['female', 'non_binary']
        }
        
        response = self.client.put(
            reverse('profiles:my-profile'),
            profile_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 4. Upload profile photo
        photo_file = self.create_image_file()
        response = self.client.post(
            reverse('profiles:upload-photo'),
            {'photo': photo_file, 'is_main': True},
            format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # 5. Verify complete profile
        response = self.client.get(reverse('profiles:my-profile'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['profile_completion'] >= 80)


class MatchingFlowTest(APIBaseTestCase):
    """Test complete matching flow from discovery to match creation."""
    
    def setUp(self):
        super().setUp()
        # Create test users with profiles
        self.user1 = self.create_authenticated_user()
        self.profile1 = Profile.objects.create(
            user=self.user1,
            bio='User 1 bio',
            gender='male',
            city='Paris',
            country='France',
            latitude=48.8566,
            longitude=2.3522
        )
        
        self.user2 = self.create_user()
        self.profile2 = Profile.objects.create(
            user=self.user2,
            bio='User 2 bio',
            gender='female',
            city='Paris',
            country='France',
            latitude=48.8600,
            longitude=2.3500
        )
    
    def test_discovery_to_match_flow(self):
        """Test discovering profiles and creating a match."""
        # 1. Get recommended profiles
        response = self.client.get(reverse('discovery:recommended-profiles'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data['results']), 0)
        
        # 2. User 1 likes User 2
        response = self.client.post(
            reverse('matches:send-like', kwargs={'user_id': str(self.user2.id)}),
            {'is_super_like': False}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data['is_match'])
        
        # 3. User 2 likes User 1 back
        self.authenticate(self.user2)
        response = self.client.post(
            reverse('matches:send-like', kwargs={'user_id': str(self.user1.id)}),
            {'is_super_like': False}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['is_match'])
        
        # 4. Verify match exists for both users
        response = self.client.get(reverse('matches:list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
        self.authenticate(self.user1)
        response = self.client.get(reverse('matches:list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class MessagingFlowTest(APIBaseTestCase):
    """Test complete messaging flow."""
    
    def setUp(self):
        super().setUp()
        # Create matched users
        self.user1 = self.create_authenticated_user()
        self.user2 = self.create_user()
        
        Profile.objects.create(user=self.user1)
        Profile.objects.create(user=self.user2)
        
        # Create match
        self.match = Match.objects.create()
        self.match.users.add(self.user1, self.user2)
    
    def test_messaging_flow(self):
        """Test sending and receiving messages."""
        # 1. Get conversations
        response = self.client.get(reverse('messaging:conversations'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
        conversation_id = response.data['results'][0]['id']
        
        # 2. Send message
        message_data = {'content': 'Hello from user 1!'}
        response = self.client.post(
            reverse('messaging:send-message', kwargs={'conversation_id': conversation_id}),
            message_data
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # 3. User 2 receives message
        self.authenticate(self.user2)
        response = self.client.get(
            reverse('messaging:messages', kwargs={'conversation_id': conversation_id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['content'], 'Hello from user 1!')
        
        # 4. User 2 replies
        reply_data = {'content': 'Hello back from user 2!'}
        response = self.client.post(
            reverse('messaging:send-message', kwargs={'conversation_id': conversation_id}),
            reply_data
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # 5. Check unread count
        response = self.client.get(reverse('messaging:conversations'))
        self.assertEqual(response.data['results'][0]['unread_count'], 0)


class PremiumSubscriptionFlowTest(APIBaseTestCase):
    """Test premium subscription flow."""
    
    def setUp(self):
        super().setUp()
        self.user = self.create_authenticated_user()
        Profile.objects.create(user=self.user)
        
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
    
    def test_premium_purchase_and_features(self):
        """Test purchasing premium and using premium features."""
        # 1. Check initial status (non-premium)
        response = self.client.get(reverse('subscriptions:current'))
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
        response = self.client.get(reverse('subscriptions:current'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'active')
        self.assertTrue(response.data['features_summary']['can_see_likers'])
        
        # 4. Test premium feature - see who liked you
        other_user = self.create_user()
        Profile.objects.create(user=other_user)
        Like.objects.create(user=other_user, target_user=self.user)
        
        response = self.client.get(reverse('profiles:likes-received'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class VerificationFlowTest(APIBaseTestCase):
    """Test identity verification flow."""
    
    def setUp(self):
        super().setUp()
        self.user = self.create_authenticated_user()
        Profile.objects.create(user=self.user)
    
    def test_verification_flow(self):
        """Test complete verification process."""
        # 1. Get verification status
        response = self.client.get(reverse('profiles:verification-status'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['verification_status'], 'not_started')
        
        # 2. Generate upload URLs
        doc_types = ['identity_document', 'medical_document', 'selfie_with_code']
        upload_urls = {}
        
        for doc_type in doc_types:
            response = self.client.post(
                reverse('profiles:verification-upload-url'),
                {
                    'document_type': doc_type,
                    'file_type': 'image/jpeg',
                    'file_size': 1024000
                }
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            upload_urls[doc_type] = response.data['file_path_on_storage']
        
        # 3. Submit verification documents
        response = self.client.post(
            reverse('profiles:verification-submit'),
            {
                'documents': [
                    {
                        'document_type': 'identity_document',
                        'file_path': upload_urls['identity_document']
                    },
                    {
                        'document_type': 'medical_document',
                        'file_path': upload_urls['medical_document']
                    }
                ],
                'selfie_code_used': response.data.get('verification_selfie_code', 'TEST123')
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 4. Check updated status
        response = self.client.get(reverse('profiles:verification-status'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(response.data['verification_status'], ['pending_selfie', 'pending_review'])