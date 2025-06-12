"""
Services for subscriptions app.
"""
import logging
import requests
import uuid
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.db import transaction as db_transaction
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

from .models import Subscription, Transaction, SubscriptionPlan
from authentication.models import User

logger = logging.getLogger('hivmeet.subscriptions')


class MyCoolPayService:
    """
    Service for interacting with MyCoolPay payment provider.
    """
    
    def __init__(self):
        self.api_key = getattr(settings, 'MYCOOLPAY_API_KEY', '')
        self.api_secret = getattr(settings, 'MYCOOLPAY_API_SECRET', '')
        self.base_url = getattr(settings, 'MYCOOLPAY_BASE_URL', 'https://api.mycoolpay.com/v1')
        self.webhook_url = getattr(settings, 'MYCOOLPAY_WEBHOOK_URL', '')
    
    def _make_request(self, method, endpoint, data=None):
        """Make authenticated request to MyCoolPay API."""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                json=data,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"MyCoolPay API error: {str(e)}")
            raise
    
    def create_payment_session(self, user, plan, payment_token, coupon_code=None):
        """
        Create a payment session with MyCoolPay.
        
        Returns:
            dict: Payment result with status and details
        """
        # Calculate amount (apply coupon if provided)
        amount = plan.price
        if coupon_code:
            # TODO: Implement coupon validation and discount calculation
            pass
        
        # Create payment intent
        payment_data = {
            'amount': int(amount * 100),  # Convert to cents
            'currency': plan.currency.lower(),
            'payment_method': payment_token,
            'description': f"HIVMeet {plan.get_name('en')} subscription",
            'metadata': {
                'user_id': str(user.id),
                'plan_id': plan.plan_id,
                'subscription_type': 'new'
            },
            'confirm': True,
            'return_url': f"{settings.FRONTEND_URL}/subscription/confirm"
        }
        
        try:
            result = self._make_request('POST', 'payment_intents', payment_data)
            
            # Create subscription in MyCoolPay
            if result['status'] == 'succeeded':
                subscription_data = {
                    'customer': user.email,
                    'plan_id': plan.plan_id,
                    'payment_method': payment_token,
                    'trial_period_days': plan.trial_period_days,
                    'metadata': {
                        'user_id': str(user.id)
                    }
                }
                
                sub_result = self._make_request('POST', 'subscriptions', subscription_data)
                
                return {
                    'status': 'succeeded',
                    'subscription_id': sub_result['id'],
                    'payment_intent_id': result['id'],
                    'amount': amount,
                    'currency': plan.currency
                }
            
            elif result['status'] == 'requires_action':
                return {
                    'status': 'requires_action',
                    'client_secret': result['client_secret'],
                    'payment_intent_id': result['id']
                }
            
            else:
                return {
                    'status': 'failed',
                    'error_message': result.get('error', {}).get('message', 'Payment failed')
                }
                
        except Exception as e:
            logger.error(f"Payment session creation failed: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e)
            }
    
    def cancel_subscription(self, subscription_id):
        """Cancel a subscription at period end."""
        try:
            self._make_request(
                'POST',
                f'subscriptions/{subscription_id}/cancel',
                {'cancel_at_period_end': True}
            )
            return True
        except Exception as e:
            logger.error(f"Subscription cancellation failed: {str(e)}")
            return False
    
    def reactivate_subscription(self, subscription_id):
        """Reactivate a canceled subscription."""
        try:
            self._make_request(
                'POST',
                f'subscriptions/{subscription_id}/reactivate',
                {}
            )
            return True
        except Exception as e:
            logger.error(f"Subscription reactivation failed: {str(e)}")
            return False


class SubscriptionService:
    """
    Service for managing subscriptions.
    """
    
    @db_transaction.atomic
    def create_subscription(self, user, plan, payment_data):
        """Create or update user subscription."""
        # Check if user has existing subscription
        try:
            subscription = user.subscription
            # Update existing subscription
            subscription.plan = plan
            subscription.subscription_id = payment_data['subscription_id']
            subscription.status = Subscription.STATUS_ACTIVE
            subscription.current_period_start = timezone.now()
            subscription.current_period_end = self._calculate_period_end(plan)
            subscription.cancel_at_period_end = False
            subscription.canceled_at = None
            subscription.cancellation_reason = ''
        except Subscription.DoesNotExist:
            # Create new subscription
            subscription = Subscription(
                user=user,
                plan=plan,
                subscription_id=payment_data['subscription_id'],
                status=Subscription.STATUS_ACTIVE,
                current_period_start=timezone.now(),
                current_period_end=self._calculate_period_end(plan)
            )
        
        # Set initial counters
        subscription.boosts_remaining = plan.monthly_boosts_count
        subscription.super_likes_remaining = plan.daily_super_likes_count
        subscription.last_boosts_reset = timezone.now()
        subscription.last_super_likes_reset = timezone.now()
        subscription.save()
        
        # Create transaction record
        Transaction.objects.create(
            transaction_id=payment_data['payment_intent_id'],
            subscription=subscription,
            type=Transaction.TYPE_PURCHASE,
            status=Transaction.STATUS_SUCCEEDED,
            amount=payment_data['amount'],
            currency=payment_data['currency'],
            payment_method=payment_data.get('payment_method', 'card')
        )
        
        # Update user premium status
        user.is_premium = True
        user.premium_until = subscription.current_period_end
        user.save(update_fields=['is_premium', 'premium_until'])
        
        # Clear cache
        cache_key = f"user_premium_status_{user.id}"
        cache.delete(cache_key)
        
        logger.info(f"Subscription created/updated for user {user.email}")
        
        return subscription
    
    def _calculate_period_end(self, plan):
        """Calculate subscription period end date."""
        start = timezone.now()
        if plan.billing_interval == SubscriptionPlan.INTERVAL_MONTH:
            # Add 30 days for monthly
            return start + timedelta(days=30)
        elif plan.billing_interval == SubscriptionPlan.INTERVAL_YEAR:
            # Add 365 days for yearly
            return start + timedelta(days=365)
        else:
            return start + timedelta(days=30)  # Default to monthly
    
    def handle_payment_success(self, event_data):
        """Handle successful payment webhook."""
        subscription_id = event_data.get('subscription_id')
        payment_intent_id = event_data.get('payment_intent_id')
        
        try:
            subscription = Subscription.objects.get(subscription_id=subscription_id)
            
            # Create transaction record
            Transaction.objects.create(
                transaction_id=payment_intent_id,
                subscription=subscription,
                type=Transaction.TYPE_RENEWAL,
                status=Transaction.STATUS_SUCCEEDED,
                amount=Decimal(str(event_data.get('amount', 0) / 100)),
                currency=event_data.get('currency', 'EUR').upper()
            )
            
            # Update subscription status
            subscription.status = Subscription.STATUS_ACTIVE
            subscription.last_payment_attempt = timezone.now()
            subscription.save()
            
            logger.info(f"Payment success handled for subscription {subscription_id}")
            
        except Subscription.DoesNotExist:
            logger.error(f"Subscription not found: {subscription_id}")
    
    def handle_payment_failure(self, event_data):
        """Handle failed payment webhook."""
        subscription_id = event_data.get('subscription_id')
        
        try:
            subscription = Subscription.objects.get(subscription_id=subscription_id)
            
            # Update subscription status
            subscription.status = Subscription.STATUS_PAST_DUE
            subscription.last_payment_attempt = timezone.now()
            subscription.save()
            
            # TODO: Send notification to user about payment failure
            
            logger.info(f"Payment failure handled for subscription {subscription_id}")
            
        except Subscription.DoesNotExist:
            logger.error(f"Subscription not found: {subscription_id}")
    
    def handle_subscription_renewal(self, event_data):
        """Handle subscription renewal webhook."""
        subscription_id = event_data.get('subscription_id')
        
        try:
            subscription = Subscription.objects.get(subscription_id=subscription_id)
            
            # Update subscription periods
            subscription.current_period_start = timezone.now()
            subscription.current_period_end = self._calculate_period_end(subscription.plan)
            subscription.status = Subscription.STATUS_ACTIVE
            subscription.save()
            
            # Update user premium status
            user = subscription.user
            user.premium_until = subscription.current_period_end
            user.save(update_fields=['premium_until'])
            
            # Reset monthly counters if needed
            if subscription.plan.billing_interval == SubscriptionPlan.INTERVAL_MONTH:
                subscription.reset_monthly_counters()
            
            logger.info(f"Subscription renewed for user {user.email}")
            
        except Subscription.DoesNotExist:
            logger.error(f"Subscription not found: {subscription_id}")
    
    def handle_subscription_cancellation(self, event_data):
        """Handle subscription cancellation webhook."""
        subscription_id = event_data.get('subscription_id')
        
        try:
            subscription = Subscription.objects.get(subscription_id=subscription_id)
            
            # Update subscription status
            subscription.status = Subscription.STATUS_CANCELED
            subscription.save()
            
            # Update user premium status if expired
            if subscription.current_period_end <= timezone.now():
                user = subscription.user
                user.is_premium = False
                user.premium_until = None
                user.save(update_fields=['is_premium', 'premium_until'])
            
            logger.info(f"Subscription canceled for subscription {subscription_id}")
            
        except Subscription.DoesNotExist:
            logger.error(f"Subscription not found: {subscription_id}")
    
    def handle_refund(self, event_data):
        """Handle refund webhook."""
        payment_intent_id = event_data.get('payment_intent_id')
        refund_amount = Decimal(str(event_data.get('amount', 0) / 100))
        
        try:
            # Find original transaction
            original_transaction = Transaction.objects.get(
                transaction_id=payment_intent_id,
                status=Transaction.STATUS_SUCCEEDED
            )
            
            # Create refund transaction
            Transaction.objects.create(
                transaction_id=event_data.get('refund_id'),
                subscription=original_transaction.subscription,
                type=Transaction.TYPE_REFUND,
                status=Transaction.STATUS_SUCCEEDED,
                amount=refund_amount,
                currency=original_transaction.currency
            )
            
            # Cancel subscription if full refund
            if refund_amount >= original_transaction.amount:
                subscription = original_transaction.subscription
                subscription.status = Subscription.STATUS_CANCELED
                subscription.save()
                
                # Remove premium status
                user = subscription.user
                user.is_premium = False
                user.premium_until = None
                user.save(update_fields=['is_premium', 'premium_until'])
            
            logger.info(f"Refund processed for transaction {payment_intent_id}")
            
        except Transaction.DoesNotExist:
            logger.error(f"Original transaction not found: {payment_intent_id}")


class PremiumFeatureService:
    """
    Service for managing premium features and limits.
    """
    
    @staticmethod
    def check_premium_status(user):
        """Check if user has active premium subscription."""
        # Check cache first
        cache_key = f"user_premium_status_{user.id}"
        cached_status = cache.get(cache_key)
        if cached_status is not None:
            return cached_status
        
        # Check database
        try:
            subscription = user.subscription
            is_premium = subscription.is_premium
        except Subscription.DoesNotExist:
            is_premium = False
        
        # Cache result for 5 minutes
        cache.set(cache_key, is_premium, 300)
        
        return is_premium
    
    @staticmethod
    def check_and_reset_counters(subscription):
        """Check and reset daily/monthly counters if needed."""
        now = timezone.now()
        
        # Reset daily super likes
        if (now - subscription.last_super_likes_reset).days >= 1:
            subscription.reset_daily_counters()
        
        # Reset monthly boosts
        if subscription.plan.billing_interval == SubscriptionPlan.INTERVAL_MONTH:
            if (now - subscription.last_boosts_reset).days >= 30:
                subscription.reset_monthly_counters()
    
    @staticmethod
    def can_use_feature(user, feature):
        """Check if user can use a specific premium feature."""
        if not PremiumFeatureService.check_premium_status(user):
            return False
        
        try:
            subscription = user.subscription
            plan = subscription.plan
            
            # Check feature availability
            feature_map = {
                'unlimited_likes': plan.unlimited_likes,
                'see_likers': plan.can_see_likers,
                'rewind': plan.can_rewind,
                'media_messaging': plan.media_messaging_enabled,
                'calls': plan.audio_video_calls_enabled
            }
            
            return feature_map.get(feature, False)
            
        except Subscription.DoesNotExist:
            return False