"""
Tests for subscriptions app.
File: subscriptions/tests.py
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import Mock, patch
from datetime import timedelta

from .models import SubscriptionPlan, Subscription, Transaction
from .services import SubscriptionService, PremiumFeatureService

User = get_user_model()


class SubscriptionPlanModelTest(TestCase):
    """Test SubscriptionPlan model."""
    
    def setUp(self):
        self.plan = SubscriptionPlan.objects.create(
            plan_id='test_monthly',
            name='Test Monthly',
            name_en='Test Monthly',
            name_fr='Test Mensuel',
            description='Test description',
            description_en='Test description',
            description_fr='Description test',
            price=9.99,
            currency='EUR',
            billing_interval=SubscriptionPlan.INTERVAL_MONTH,
            trial_period_days=7
        )
    
    def test_plan_creation(self):
        """Test plan is created correctly."""
        self.assertEqual(self.plan.plan_id, 'test_monthly')
        self.assertEqual(self.plan.price, Decimal('9.99'))
        self.assertEqual(self.plan.billing_interval, SubscriptionPlan.INTERVAL_MONTH)
    
    def test_localized_names(self):
        """Test localized name methods."""
        self.assertEqual(self.plan.get_name('en'), 'Test Monthly')
        self.assertEqual(self.plan.get_name('fr'), 'Test Mensuel')
        self.assertEqual(self.plan.get_name(), 'Test Mensuel')  # Default French
    
    def test_features_list(self):
        """Test features list generation."""
        features = self.plan.get_features_list()
        expected_features = [
            'unlimited_likes', 'can_see_likers', 'can_rewind',
            'monthly_boosts', 'daily_super_likes', 'media_messaging',
            'audio_video_calls'
        ]
        for feature in expected_features:
            self.assertIn(feature, features)


class SubscriptionModelTest(TestCase):
    """Test Subscription model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            display_name='Test User'
        )
        
        self.plan = SubscriptionPlan.objects.create(
            plan_id='test_monthly',
            name='Test Monthly',
            price=9.99,
            billing_interval=SubscriptionPlan.INTERVAL_MONTH,
            monthly_boosts_count=1,
            daily_super_likes_count=5
        )
        
        self.subscription = Subscription.objects.create(
            subscription_id='sub_test123',
            user=self.user,
            plan=self.plan,
            status=Subscription.STATUS_ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            boosts_remaining=1,
            super_likes_remaining=5
        )
    
    def test_subscription_creation(self):
        """Test subscription is created correctly."""
        self.assertEqual(self.subscription.user, self.user)
        self.assertEqual(self.subscription.plan, self.plan)
        self.assertTrue(self.subscription.is_active)
        self.assertTrue(self.subscription.is_premium)
    
    def test_use_boost(self):
        """Test using a boost."""
        self.assertTrue(self.subscription.use_boost())
        self.assertEqual(self.subscription.boosts_remaining, 0)
        self.assertFalse(self.subscription.use_boost())  # No more boosts
    
    def test_use_super_like(self):
        """Test using a super like."""
        initial_count = self.subscription.super_likes_remaining
        self.assertTrue(self.subscription.use_super_like())
        self.assertEqual(self.subscription.super_likes_remaining, initial_count - 1)
    
    def test_reset_counters(self):
        """Test resetting counters."""
        self.subscription.boosts_remaining = 0
        self.subscription.super_likes_remaining = 0
        self.subscription.save()
        
        self.subscription.reset_monthly_counters()
        self.assertEqual(self.subscription.boosts_remaining, self.plan.monthly_boosts_count)
        
        self.subscription.reset_daily_counters()
        self.assertEqual(self.subscription.super_likes_remaining, self.plan.daily_super_likes_count)


class SubscriptionAPITest(APITestCase):
    """Test subscription API endpoints."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            display_name='Test User'
        )
        
        self.plan = SubscriptionPlan.objects.create(
            plan_id='test_monthly',
            name='Test Monthly',
            name_en='Test Monthly',
            name_fr='Test Mensuel',
            price=9.99,
            currency='EUR',
            billing_interval=SubscriptionPlan.INTERVAL_MONTH,
            is_active=True
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_get_plans(self):
        """Test getting subscription plans."""
        url = reverse('subscriptions:plans')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['plan_id'], 'test_monthly')
    
    def test_get_current_subscription_none(self):
        """Test getting current subscription when none exists."""
        url = reverse('subscriptions:current')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['subscription_id'])
        self.assertEqual(response.data['status'], 'none')
    
    def test_get_current_subscription_active(self):
        """Test getting current active subscription."""
        subscription = Subscription.objects.create(
            subscription_id='sub_test123',
            user=self.user,
            plan=self.plan,
            status=Subscription.STATUS_ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30)
        )
        
        url = reverse('subscriptions:current')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['subscription_id'], 'sub_test123')
        self.assertEqual(response.data['status'], Subscription.STATUS_ACTIVE)
        self.assertIn('features_summary', response.data)
    
    @patch('subscriptions.services.MyCoolPayService.create_payment_session')
    def test_purchase_subscription(self, mock_payment):
        """Test purchasing a subscription."""
        mock_payment.return_value = {
            'status': 'succeeded',
            'subscription_id': 'sub_new123',
            'payment_intent_id': 'pi_test123',
            'amount': Decimal('9.99'),
            'currency': 'EUR'
        }
        
        url = reverse('subscriptions:purchase')
        data = {
            'plan_id': 'test_monthly',
            'payment_method_token': 'pm_test123'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['subscription_id'], 'sub_new123')
        self.assertEqual(response.data['status'], Subscription.STATUS_ACTIVE)
        
        # Check subscription was created
        subscription = Subscription.objects.get(user=self.user)
        self.assertEqual(subscription.subscription_id, 'sub_new123')
        self.assertTrue(subscription.is_active)
    
    def test_cancel_subscription(self):
        """Test canceling a subscription."""
        subscription = Subscription.objects.create(
            subscription_id='sub_test123',
            user=self.user,
            plan=self.plan,
            status=Subscription.STATUS_ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30)
        )
        
        url = reverse('subscriptions:cancel')
        with patch('subscriptions.services.MyCoolPayService.cancel_subscription'):
            response = self.client.post(url, {'reason': 'Too expensive'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['cancel_at_period_end'])
        
        subscription.refresh_from_db()
        self.assertTrue(subscription.cancel_at_period_end)
        self.assertEqual(subscription.cancellation_reason, 'Too expensive')


class SubscriptionServiceTest(TestCase):
    """Test subscription service methods."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            display_name='Test User'
        )
        
        self.plan = SubscriptionPlan.objects.create(
            plan_id='test_monthly',
            name='Test Monthly',
            price=9.99,
            billing_interval=SubscriptionPlan.INTERVAL_MONTH
        )
        
        self.service = SubscriptionService()
    
    def test_create_subscription(self):
        """Test creating a subscription."""
        payment_data = {
            'subscription_id': 'sub_test123',
            'payment_intent_id': 'pi_test123',
            'amount': Decimal('9.99'),
            'currency': 'EUR'
        }
        
        subscription = self.service.create_subscription(
            self.user, self.plan, payment_data
        )
        
        self.assertEqual(subscription.subscription_id, 'sub_test123')
        self.assertEqual(subscription.status, Subscription.STATUS_ACTIVE)
        self.assertTrue(subscription.user.is_premium)
        
        # Check transaction was created
        transaction = Transaction.objects.get(subscription=subscription)
        self.assertEqual(transaction.type, Transaction.TYPE_PURCHASE)
        self.assertEqual(transaction.status, Transaction.STATUS_SUCCEEDED)
    
    def test_calculate_period_end(self):
        """Test period end calculation."""
        # Monthly
        monthly_end = self.service._calculate_period_end(self.plan)
        expected_monthly = timezone.now() + timedelta(days=30)
        self.assertAlmostEqual(
            monthly_end.timestamp(),
            expected_monthly.timestamp(),
            delta=60  # Within 1 minute
        )
        
        # Yearly
        self.plan.billing_interval = SubscriptionPlan.INTERVAL_YEAR
        yearly_end = self.service._calculate_period_end(self.plan)
        expected_yearly = timezone.now() + timedelta(days=365)
        self.assertAlmostEqual(
            yearly_end.timestamp(),
            expected_yearly.timestamp(),
            delta=60
        )


class PremiumFeatureServiceTest(TestCase):
    """Test premium feature service."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            display_name='Test User',
            is_premium=True,
            premium_until=timezone.now() + timedelta(days=30)
        )
        
        self.plan = SubscriptionPlan.objects.create(
            plan_id='test_monthly',
            name='Test Monthly',
            price=9.99,
            billing_interval=SubscriptionPlan.INTERVAL_MONTH
        )
        
        self.subscription = Subscription.objects.create(
            subscription_id='sub_test123',
            user=self.user,
            plan=self.plan,
            status=Subscription.STATUS_ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30)
        )
    
    def test_check_premium_status(self):
        """Test checking premium status."""
        self.assertTrue(PremiumFeatureService.check_premium_status(self.user))
        
        # Test with expired premium
        self.user.premium_until = timezone.now() - timedelta(days=1)
        self.user.save()
        self.assertFalse(PremiumFeatureService.check_premium_status(self.user))
    
    def test_can_use_feature(self):
        """Test checking feature availability."""
        self.assertTrue(
            PremiumFeatureService.can_use_feature(self.user, 'unlimited_likes')
        )
        self.assertTrue(
            PremiumFeatureService.can_use_feature(self.user, 'media_messaging')
        )
        
        # Test with non-premium user
        self.user.is_premium = False
        self.user.save()
        self.assertFalse(
            PremiumFeatureService.can_use_feature(self.user, 'unlimited_likes')
        )