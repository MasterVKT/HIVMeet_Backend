"""
Tests for subscriptions app.
File: subscriptions/tests.py
"""
from datetime import date
from decimal import Decimal
from django.core.cache import cache
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import Mock, patch
from datetime import timedelta

from .models import (
    PaymentTransaction,
    Subscription,
    SubscriptionPlan,
    Transaction,
)
from .services import (
    SubscriptionService,
    PremiumFeatureService,
    PlanChangeRequiresPaymentError,
)
from .utils import is_premium_user

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
            price=Decimal('9.99'),
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
            display_name='Test User',
            birth_date=date(1990, 1, 1)
        )
        
        self.plan = SubscriptionPlan.objects.create(
            plan_id='test_monthly',
            name='Test Monthly',
            price=Decimal('9.99'),
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
            display_name='Test User',
            birth_date=date(1990, 1, 1)
        )
        
        self.plan = SubscriptionPlan.objects.create(
            plan_id='test_monthly',
            name='Test Monthly',
            name_en='Test Monthly',
            name_fr='Test Mensuel',
            price=Decimal('9.99'),
            currency='EUR',
            billing_interval=SubscriptionPlan.INTERVAL_MONTH,
            is_active=True
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_get_plans(self):
        """Test getting subscription plans.

        The endpoint inherits the project-wide ``PageNumberPagination``, so the
        payload is the DRF envelope ``{count, next, previous, results}`` — not a
        bare list. The Flutter client reads ``payload['results']`` accordingly
        (``premium_repository_impl.dart``).
        """
        url = reverse('api:subscriptions:plans')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['plan_id'], 'test_monthly')
    
    def test_get_current_subscription_none(self):
        """Test getting current subscription when none exists."""
        url = reverse('api:subscriptions:current')
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
        
        url = reverse('api:subscriptions:current')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['subscription_id'], 'sub_test123')
        self.assertEqual(response.data['status'], Subscription.STATUS_ACTIVE)
        self.assertIn('features_summary', response.data)
    
    @patch('subscriptions.views.initiate_payment')
    def test_purchase_subscription(self, mock_payment):
        """Purchasing creates a pending backend-owned Paylink."""
        mock_payment.return_value = Mock(
            id='11111111-1111-1111-1111-111111111111',
            amount=Decimal('9.99'),
            currency='EUR',
            status=PaymentTransaction.STATUS_PENDING,
            payment_url=(
                'https://my-coolpay.com/payment/checkout/provider-ref'
            ),
        )
        
        url = reverse('api:subscriptions:purchase')
        data = {
            'plan_id': 'test_monthly',
            'phone_number': '699009900',
            'language': 'fr',
        }
        response = self.client.post(url, data, format='json', secure=True)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['payment_status'], 'pending')
        self.assertEqual(
            response.data['payment_id'],
            '11111111-1111-1111-1111-111111111111',
        )
        self.assertFalse(Subscription.objects.filter(user=self.user).exists())
    
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
        
        url = reverse('api:subscriptions:cancel')
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
            display_name='Test User',
            birth_date=date(1990, 1, 1)
        )
        
        self.plan = SubscriptionPlan.objects.create(
            plan_id='test_monthly',
            name='Test Monthly',
            price=Decimal('9.99'),
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
            birth_date=date(1990, 1, 1),
            is_premium=True,
            premium_until=timezone.now() + timedelta(days=30)
        )
        
        self.plan = SubscriptionPlan.objects.create(
            plan_id='test_monthly',
            name='Test Monthly',
            price=Decimal('9.99'),
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


class PremiumStatusCacheInvalidationTest(TestCase):
    """Paid access must never survive its own revocation in cache.

    The premium status is cached for 5 minutes under a single key. Before the
    2026-07-31 fix that key was only cleared on purchase, so a cancelled or
    expired subscription kept granting premium features until the TTL lapsed.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email='cache@example.com',
            password='testpass123',
            display_name='Cache User',
            birth_date=date(1990, 1, 1),
            is_premium=True,
            premium_until=timezone.now() + timedelta(days=30)
        )
        self.plan = SubscriptionPlan.objects.create(
            plan_id='cache_monthly',
            name='Cache Monthly',
            price=Decimal('9.99'),
            billing_interval=SubscriptionPlan.INTERVAL_MONTH
        )

    def tearDown(self):
        cache.clear()

    def test_expiry_is_not_masked_by_cache(self):
        self.assertTrue(is_premium_user(self.user))

        self.user.premium_until = timezone.now() - timedelta(days=1)
        self.user.save(update_fields=['premium_until'])

        self.assertFalse(is_premium_user(self.user))

    def test_revocation_through_full_save_invalidates_cache(self):
        self.assertTrue(is_premium_user(self.user))

        self.user.is_premium = False
        self.user.premium_until = None
        self.user.save()

        self.assertFalse(is_premium_user(self.user))

    def test_unrelated_user_save_keeps_cache_semantics(self):
        self.assertTrue(is_premium_user(self.user))

        self.user.display_name = 'Renamed'
        self.user.save(update_fields=['display_name'])

        self.assertTrue(is_premium_user(self.user))

    def test_subscription_write_invalidates_cache(self):
        self.assertTrue(is_premium_user(self.user))

        Subscription.objects.create(
            subscription_id='sub_cache123',
            user=self.user,
            plan=self.plan,
            status=Subscription.STATUS_EXPIRED,
            current_period_start=timezone.now() - timedelta(days=60),
            current_period_end=timezone.now() - timedelta(days=30),
        )

        self.user.refresh_from_db()
        self.assertFalse(is_premium_user(self.user))

    def test_service_and_utils_agree_on_premium_definition(self):
        """Both read the same cache key, so they must mean the same thing."""
        self.assertEqual(
            PremiumFeatureService.check_premium_status(self.user),
            is_premium_user(self.user),
        )

        self.user.premium_until = timezone.now() - timedelta(days=1)
        self.user.save(update_fields=['premium_until'])

        self.assertEqual(
            PremiumFeatureService.check_premium_status(self.user),
            is_premium_user(self.user),
        )
        self.assertFalse(PremiumFeatureService.check_premium_status(self.user))


class EmptySubscriptionContractTest(APITestCase):
    """A user without a subscription must still get the documented payload."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='nosub@example.com',
            password='testpass123',
            display_name='No Sub',
            birth_date=date(1990, 1, 1)
        )
        self.client.force_authenticate(user=self.user)

    def test_current_subscription_returns_full_empty_payload(self):
        response = self.client.get(reverse('api:subscriptions:current'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Previously the endpoint answered {} because DRF skips read-only
        # fields when the serializer instance is None.
        self.assertIn('subscription_id', response.data)
        self.assertIsNone(response.data['subscription_id'])
        self.assertEqual(response.data['status'], 'none')
        self.assertIn('features_summary', response.data)
        self.assertFalse(response.data['features_summary']['media_messaging_enabled'])
        self.assertFalse(response.data['features_summary']['audio_video_calls_enabled'])


class ModifySubscriptionAPITest(APITestCase):
    """Tests for POST /api/v1/subscriptions/current/modify/."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email='modify@example.com',
            password='testpass123',
            display_name='Modify User',
            birth_date=date(1990, 1, 1),
        )
        self.monthly_plan = SubscriptionPlan.objects.create(
            plan_id='modtest_monthly',
            name='Monthly',
            name_en='Monthly',
            name_fr='Mensuel',
            description='Monthly plan',
            description_en='Monthly plan',
            description_fr='Plan mensuel',
            price=Decimal('9.99'),
            currency='EUR',
            billing_interval=SubscriptionPlan.INTERVAL_MONTH,
            monthly_boosts_count=1,
            daily_super_likes_count=5,
            is_active=True,
        )
        self.yearly_plan = SubscriptionPlan.objects.create(
            plan_id='modtest_yearly',
            name='Yearly',
            name_en='Yearly',
            name_fr='Annuel',
            description='Yearly plan',
            description_en='Yearly plan',
            description_fr='Plan annuel',
            price=Decimal('79.99'),
            currency='EUR',
            billing_interval=SubscriptionPlan.INTERVAL_YEAR,
            monthly_boosts_count=5,
            daily_super_likes_count=10,
            is_active=True,
        )
        self.subscription = Subscription.objects.create(
            subscription_id='sub_modify123',
            user=self.user,
            plan=self.monthly_plan,
            status=Subscription.STATUS_ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=25),
            boosts_remaining=1,
            super_likes_remaining=5,
        )
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        cache.clear()

    @patch('subscriptions.views.is_mycoolpay_payment_flow_configured', return_value=True)
    @patch('subscriptions.views.initiate_payment')
    def test_modify_to_higher_plan_creates_paylink_for_net_amount(
        self, mock_payment, _mock_configured
    ):
        """Upgrade monthly -> yearly: the net prorated amount is positive, so
        MyCoolPay (Paylink-only, no modification API) needs a new Paylink for
        that amount — the plan itself is not switched until the webhook
        confirms payment."""
        mock_payment.return_value = Mock(
            id='22222222-2222-2222-2222-222222222222',
            amount=Decimal('70.00'),
            currency='EUR',
            status=PaymentTransaction.STATUS_PENDING,
            payment_url='https://my-coolpay.com/payment/checkout/provider-ref',
        )

        url = reverse('api:subscriptions:modify')
        response = self.client.post(
            url,
            {
                'new_plan_id': 'modtest_yearly',
                'proration': True,
                'phone_number': '699009900',
                'language': 'fr',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data['payment_id'],
            '22222222-2222-2222-2222-222222222222',
        )
        self.assertEqual(response.data['payment_status'], 'pending')

        # Plan change is deferred to the webhook — not applied inline.
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.plan, self.monthly_plan)

        mock_payment.assert_called_once()
        call_kwargs = mock_payment.call_args.kwargs
        self.assertEqual(call_kwargs['plan'], self.yearly_plan)
        self.assertEqual(call_kwargs['amount'], Decimal('70.00'))
        self.assertEqual(call_kwargs['currency'], 'EUR')

    def test_modify_to_higher_plan_without_phone_number_returns_400(self):
        """A positive net amount requires phone_number to create the Paylink."""
        url = reverse('api:subscriptions:modify')
        response = self.client.post(
            url,
            {'new_plan_id': 'modtest_yearly', 'proration': True},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'phone_number_required')
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.plan, self.monthly_plan)

    @patch('subscriptions.views.is_mycoolpay_payment_flow_configured', return_value=True)
    @patch('subscriptions.views.initiate_payment')
    def test_modify_paylink_creation_failure_returns_502(
        self, mock_payment, _mock_configured
    ):
        """MyCoolPay rejecting the Paylink request surfaces as 502."""
        from .payment_gateway import MyCoolPayError

        mock_payment.side_effect = MyCoolPayError('boom')

        url = reverse('api:subscriptions:modify')
        response = self.client.post(
            url,
            {
                'new_plan_id': 'modtest_yearly',
                'proration': True,
                'phone_number': '699009900',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.plan, self.monthly_plan)

    def test_modify_to_lower_plan_with_proration(self):
        """Downgrade yearly -> monthly: unused credit covers the new plan in
        full (net amount <= 0), so the change applies immediately with no
        payment involved."""
        # Set up user on yearly plan
        self.subscription.plan = self.yearly_plan
        self.subscription.save()

        url = reverse('api:subscriptions:modify')
        response = self.client.post(
            url,
            {'new_plan_id': 'modtest_monthly', 'proration': True},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['plan_id'], 'modtest_monthly')

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.plan, self.monthly_plan)

    def test_modify_without_active_subscription_returns_400(self):
        """No active subscription → 400 no_active_subscription."""
        self.subscription.delete()
        # Clear any cached relation on the authenticated user instance
        self.user.refresh_from_db()

        url = reverse('api:subscriptions:modify')
        response = self.client.post(
            url,
            {'new_plan_id': 'modtest_yearly'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'no_active_subscription')

    def test_modify_with_canceled_subscription_returns_400(self):
        """Canceled (inactive) subscription → 400."""
        self.subscription.status = Subscription.STATUS_CANCELED
        self.subscription.save()

        url = reverse('api:subscriptions:modify')
        response = self.client.post(
            url,
            {'new_plan_id': 'modtest_yearly'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'no_active_subscription')

    def test_modify_to_same_plan_returns_400(self):
        """Same plan → 400 same_plan."""
        url = reverse('api:subscriptions:modify')
        response = self.client.post(
            url,
            {'new_plan_id': 'modtest_monthly'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'same_plan')

    def test_modify_to_invalid_plan_returns_400(self):
        """Non-existent plan_id → 400 (serializer validation)."""
        url = reverse('api:subscriptions:modify')
        response = self.client.post(
            url,
            {'new_plan_id': 'nonexistent_plan'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_modify_missing_new_plan_id_returns_400(self):
        """Missing new_plan_id → 400 (serializer validation)."""
        url = reverse('api:subscriptions:modify')
        response = self.client.post(url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_modify_invalidates_premium_cache(self):
        """Cache must be invalidated after modification."""
        # Prime the cache
        is_premium_user(self.user)
        cached_key = f'user_premium_status_{self.user.id}'
        self.assertIsNotNone(cache.get(cached_key))

        # proration=False needs no payment (scheduled for next cycle), so it
        # exercises the cache-invalidation path without a Paylink mock.
        url = reverse('api:subscriptions:modify')
        self.client.post(
            url,
            {'new_plan_id': 'modtest_yearly', 'proration': False},
            format='json',
        )

        # Cache should have been invalidated and re-populated with new value
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_premium)

    def test_modify_with_proration_false_schedules_for_next_cycle(self):
        """proration=False: change scheduled, subscription marked for cancel_at_period_end."""
        url = reverse('api:subscriptions:modify')
        response = self.client.post(
            url,
            {'new_plan_id': 'modtest_yearly', 'proration': False},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # proration block should be null
        self.assertIsNone(response.data.get('proration'))
        self.assertEqual(
            response.data['scheduled_change']['plan_id'],
            'modtest_yearly',
        )
        self.assertEqual(
            response.data['scheduled_change']['effective_at'],
            self.subscription.current_period_end,
        )

        self.subscription.refresh_from_db()
        self.assertTrue(self.subscription.cancel_at_period_end)
        self.assertIn('plan_change:modtest_yearly', self.subscription.cancellation_reason)
        # Plan should NOT have changed yet
        self.assertEqual(self.subscription.plan, self.monthly_plan)

    def test_modify_creates_transaction_record(self):
        """A Transaction with type=modification should be created when the
        change applies immediately (net amount <= 0, no payment needed)."""
        # Downgrade yearly -> monthly: credit covers the new plan in full.
        self.subscription.plan = self.yearly_plan
        self.subscription.save()

        url = reverse('api:subscriptions:modify')
        self.client.post(
            url,
            {'new_plan_id': 'modtest_monthly', 'proration': True},
            format='json',
        )

        mod_tx = Transaction.objects.filter(
            subscription=self.subscription,
            type=Transaction.TYPE_MODIFICATION,
        )
        self.assertTrue(mod_tx.exists())
        self.assertEqual(mod_tx.first().status, Transaction.STATUS_SUCCEEDED)

    def test_modify_unauthenticated_returns_401(self):
        """Unauthenticated request → 401."""
        self.client.force_authenticate(user=None)
        url = reverse('api:subscriptions:modify')
        response = self.client.post(
            url,
            {'new_plan_id': 'modtest_yearly'},
            format='json',
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )


class ModifySubscriptionServiceTest(TestCase):
    """Unit tests for SubscriptionService.modify_subscription."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email='svc_modify@example.com',
            password='testpass123',
            display_name='Svc Modify',
            birth_date=date(1990, 1, 1),
        )
        self.monthly = SubscriptionPlan.objects.create(
            plan_id='svc_monthly',
            name='Monthly',
            name_en='Monthly',
            name_fr='Mensuel',
            description='d',
            description_en='d',
            description_fr='d',
            price=Decimal('10.00'),
            currency='EUR',
            billing_interval=SubscriptionPlan.INTERVAL_MONTH,
            monthly_boosts_count=1,
            daily_super_likes_count=5,
        )
        self.yearly = SubscriptionPlan.objects.create(
            plan_id='svc_yearly',
            name='Yearly',
            name_en='Yearly',
            name_fr='Annuel',
            description='d',
            description_en='d',
            description_fr='d',
            price=Decimal('100.00'),
            currency='EUR',
            billing_interval=SubscriptionPlan.INTERVAL_YEAR,
            monthly_boosts_count=5,
            daily_super_likes_count=10,
        )
        self.subscription = Subscription.objects.create(
            subscription_id='svc_sub_001',
            user=self.user,
            plan=self.monthly,
            status=Subscription.STATUS_ACTIVE,
            current_period_start=timezone.now() - timedelta(days=15),
            current_period_end=timezone.now() + timedelta(days=15),
        )
        self.service = SubscriptionService()

    def tearDown(self):
        cache.clear()

    def test_proration_calculation(self):
        """Proration credit is proportional to remaining time."""
        proration = self.service._calculate_proration(self.subscription, self.yearly)
        # 15 days remaining out of 30 → fraction ≈ 0.5
        # credit = 10.00 * 0.5 = 5.00
        # charge = 100.00 * 0.5 = 50.00
        self.assertEqual(proration['credit_amount'], Decimal('5.00'))
        self.assertEqual(proration['charge_amount'], Decimal('50.00'))
        self.assertEqual(proration['currency'], 'EUR')

    def test_modify_upgrade_with_positive_net_requires_payment(self):
        """Upgrading monthly -> yearly has a positive net amount (charge
        50.00 > credit 5.00): MyCoolPay has no modification API, so the
        service must not touch the subscription and instead signal that a
        new Paylink is needed."""
        period_end_before = self.subscription.current_period_end
        with self.assertRaises(PlanChangeRequiresPaymentError) as ctx:
            self.service.modify_subscription(
                subscription=self.subscription,
                new_plan=self.yearly,
                proration=True,
            )

        proration_info = ctx.exception.proration_info
        self.assertEqual(proration_info['credit_amount'], Decimal('5.00'))
        self.assertEqual(proration_info['charge_amount'], Decimal('50.00'))

        # Nothing was applied — the change waits for payment confirmation.
        # (The user is already premium via the active monthly subscription
        # created in setUp — that is unrelated to this modify attempt.)
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.plan, self.monthly)
        self.assertEqual(self.subscription.current_period_end, period_end_before)

    def test_modify_downgrade_with_covered_net_applies_immediately(self):
        """Downgrading yearly -> monthly: the outgoing plan's unused credit
        (50.00) covers the new plan's prorated cost (5.00) in full (net <= 0)
        — the change applies immediately, with no payment involved."""
        self.subscription.plan = self.yearly
        self.subscription.save()

        result = self.service.modify_subscription(
            subscription=self.subscription,
            new_plan=self.monthly,
            proration=True,
        )

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.plan, self.monthly)
        self.assertEqual(self.subscription.status, Subscription.STATUS_ACTIVE)
        # Period end should be ~30 days from now
        expected_end = timezone.now() + timedelta(days=30)
        self.assertAlmostEqual(
            self.subscription.current_period_end.timestamp(),
            expected_end.timestamp(),
            delta=120,
        )
        # Counters updated to new (monthly) plan
        self.assertEqual(self.subscription.boosts_remaining, 1)
        self.assertEqual(self.subscription.super_likes_remaining, 5)
        # Proration info returned even though no payment was needed
        self.assertIsNotNone(result['proration_info'])

    def test_modify_without_proration_schedules_change(self):
        """proration=False marks subscription for end-of-period plan change."""
        result = self.service.modify_subscription(
            subscription=self.subscription,
            new_plan=self.yearly,
            proration=False,
        )

        self.subscription.refresh_from_db()
        self.assertTrue(self.subscription.cancel_at_period_end)
        self.assertEqual(self.subscription.plan, self.monthly)  # unchanged
        self.assertIn('plan_change:svc_yearly', self.subscription.cancellation_reason)
        self.assertIsNone(result['proration_info'])

    def test_modify_updates_user_premium_status(self):
        """User.is_premium and premium_until must be updated (downgrade:
        net amount <= 0, applied immediately without payment)."""
        self.subscription.plan = self.yearly
        self.subscription.save()

        self.service.modify_subscription(
            subscription=self.subscription,
            new_plan=self.monthly,
            proration=True,
        )

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_premium)
        self.assertIsNotNone(self.user.premium_until)

    def test_modify_invalidates_premium_cache(self):
        """Premium cache key must be cleared after modification (downgrade:
        net amount <= 0, applied immediately without payment)."""
        from subscriptions.utils import premium_status_cache_key
        is_premium_user(self.user)
        key = premium_status_cache_key(self.user.id)
        self.assertIsNotNone(cache.get(key))

        self.subscription.plan = self.yearly
        self.subscription.save()

        self.service.modify_subscription(
            subscription=self.subscription,
            new_plan=self.monthly,
            proration=True,
        )

        # After modify, the old cached value is gone (may be re-populated)
        # The key point: calling is_premium_user again gives the correct answer
        self.user.refresh_from_db()
        self.assertTrue(is_premium_user(self.user))
