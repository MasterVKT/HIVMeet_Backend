"""
Services for subscriptions app.
"""
import logging
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import transaction as db_transaction

from .models import Subscription, Transaction, SubscriptionPlan
from .pricing import convert_amount, quantum_for_currency, resolve_effective_currency
from .utils import invalidate_premium_status_cache
logger = logging.getLogger('hivmeet.subscriptions')


class PlanChangeRequiresPaymentError(Exception):
    """Raised when an immediate (prorated) plan change needs a real charge.

    MyCoolPay has no subscription-modification API (Paylink-only, see
    `MyCoolPayService` below): an immediate upgrade whose prorated net
    amount is positive must go through a brand new Paylink for that amount,
    exactly like a purchase. This exception carries `proration_info` (which
    includes the net amount and currency) so the caller (the `modify`
    view) can create that Paylink. The subscription and user are left
    untouched — the plan change is only applied once the webhook confirms
    payment (`payment_gateway.apply_provider_status` →
    `SubscriptionService.create_subscription`, which already knows how to
    update an existing subscription to `payment.plan`).
    """

    def __init__(self, proration_info):
        self.proration_info = proration_info
        super().__init__(
            "A payment is required to apply this plan change immediately."
        )


class MyCoolPayService:
    """Compatibility facade for legacy callers.

    MyCoolPay's documented integration is Paylink-based and does not expose
    provider subscription, retry, cancellation, or modification endpoints.
    New purchases use ``payment_gateway.MyCoolPayPaylinkClient``. Keeping these
    methods explicit prevents old code from calling invented remote endpoints.
    """

    def create_payment_session(self, user, plan, payment_token, coupon_code=None):
        return {
            'status': 'failed',
            'error_message': 'Use the Paylink purchase endpoint',
        }

    def cancel_subscription(self, subscription_id):
        return False

    def reactivate_subscription(self, subscription_id):
        return False

    def modify_subscription(self, subscription_id, new_plan_id, proration=True):
        return {
            'status': 'failed',
            'error_message': 'A new Paylink is required for a paid plan change',
        }


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
        invalidate_premium_status_cache(user)

        logger.info("Subscription created or updated")
        
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

    def _calculate_period_end_from(self, start, plan):
        """Calculate subscription period end date from a given start."""
        if plan.billing_interval == SubscriptionPlan.INTERVAL_MONTH:
            return start + timedelta(days=30)
        elif plan.billing_interval == SubscriptionPlan.INTERVAL_YEAR:
            return start + timedelta(days=365)
        return start + timedelta(days=30)

    @staticmethod
    def _calculate_proration(subscription, new_plan):
        """Compute the proration credit and charge for a plan change.

        Returns a dict with ``credit_amount``, ``charge_amount``, ``currency``,
        ``prorated_period_start`` and ``prorated_period_end``.

        - ``credit_amount``: unused value of the *old* plan's current period.
        - ``charge_amount``: prorated cost of the *new* plan for the remaining
          time.
        - The net balance (charge - credit) determines whether the user must
          pay extra (positive) or receives a credit (negative).

        Both plans are priced in the user's effective billing currency (the
        same resolution ``pricing.quote_plan`` uses for a fresh purchase),
        not their raw ``.price``/``.currency`` fields — plans can be stored
        in a different currency than what the user is actually charged, and
        the net amount computed here is charged as-is via a new Paylink.
        """
        now = timezone.now()
        old_plan = subscription.plan
        currency = resolve_effective_currency(subscription.user)

        period_start = subscription.current_period_start
        period_end = subscription.current_period_end
        total_seconds = (period_end - period_start).total_seconds()
        remaining_seconds = max((period_end - now).total_seconds(), 0)

        if total_seconds <= 0:
            fraction_remaining = Decimal('0')
        else:
            fraction_remaining = Decimal(str(remaining_seconds)) / Decimal(str(total_seconds))

        old_price = convert_amount(old_plan.price, old_plan.currency, currency)
        new_price = convert_amount(new_plan.price, new_plan.currency, currency)
        quantum = quantum_for_currency(currency)

        # Credit: unused portion of the old plan
        credit_amount = (old_price * fraction_remaining).quantize(quantum)

        # Charge: prorated cost of the new plan for the remaining time
        charge_amount = (new_price * fraction_remaining).quantize(quantum)

        return {
            'credit_amount': credit_amount,
            'charge_amount': charge_amount,
            'currency': currency,
            'prorated_period_start': now,
            'prorated_period_end': period_end,
        }

    @db_transaction.atomic
    def modify_subscription(self, subscription, new_plan, proration=True):
        """Change an existing subscription to a new plan.

        Args:
            subscription: the user's active ``Subscription`` instance.
            new_plan: the target ``SubscriptionPlan`` instance.
            proration: if ``True``, the change takes effect immediately when
                the prorated net amount is covered by the outgoing plan's
                unused credit. If the net amount is positive, no local state
                changes: the caller must create a new Paylink for that amount
                (see ``PlanChangeRequiresPaymentError``) and the change is
                applied only once the webhook confirms payment. If ``False``,
                the change is scheduled for the next billing cycle instead
                (``cancel_at_period_end`` semantics, applied by the renewal
                webhook).

        Returns:
            dict with key ``proration_info`` (``None`` if ``proration=False``).

        Raises:
            PlanChangeRequiresPaymentError: the prorated net amount is
                positive — a new Paylink is required before this change can
                be applied.
        """
        user = subscription.user
        old_plan = subscription.plan
        now = timezone.now()

        if not proration:
            # Schedule the change for the next billing cycle.
            # We mark the current subscription to end at period end; the renewal
            # webhook (handle_subscription_renewal) will create the new plan.
            subscription.cancel_at_period_end = True
            subscription.cancellation_reason = f"plan_change:{new_plan.plan_id}"
            subscription.save()

            logger.info(
                "Subscription change scheduled: %s -> %s at next cycle",
                old_plan.plan_id,
                new_plan.plan_id,
            )

            user.is_premium = True
            user.premium_until = subscription.current_period_end
            user.save(update_fields=['is_premium', 'premium_until'])
            invalidate_premium_status_cache(user)

            return {'proration_info': None}

        # 1. Compute proration locally.
        proration_info = self._calculate_proration(subscription, new_plan)
        net_amount = proration_info['charge_amount'] - proration_info['credit_amount']

        if net_amount > 0:
            # MyCoolPay has no subscription-modification API — a real charge
            # requires a brand new Paylink. Leave the subscription untouched;
            # the caller creates the Paylink and the webhook applies the
            # change on payment success.
            raise PlanChangeRequiresPaymentError(proration_info)

        # 2. Net amount <= 0: the outgoing plan's unused credit covers the
        # new plan in full — apply immediately, no payment needed (the
        # surplus credit, if any, is not refunded in cash).
        subscription.plan = new_plan
        subscription.status = Subscription.STATUS_ACTIVE
        subscription.current_period_start = now
        subscription.current_period_end = self._calculate_period_end_from(now, new_plan)
        subscription.cancel_at_period_end = False
        subscription.canceled_at = None
        subscription.cancellation_reason = ''
        # Adjust feature counters to the new plan's limits
        subscription.boosts_remaining = new_plan.monthly_boosts_count
        subscription.super_likes_remaining = new_plan.daily_super_likes_count
        subscription.last_boosts_reset = now
        subscription.last_super_likes_reset = now
        subscription.save()

        Transaction.objects.create(
            transaction_id=f"mod_{subscription.id}_{now.strftime('%Y%m%d%H%M%S')}",
            subscription=subscription,
            type=Transaction.TYPE_MODIFICATION,
            status=Transaction.STATUS_SUCCEEDED,
            amount=Decimal('0.00'),
            currency=proration_info['currency'],
            payment_method=subscription.payment_method or 'card'
        )

        logger.info(
            "Subscription modified without additional payment (credit covered change): %s -> %s",
            old_plan.plan_id,
            new_plan.plan_id,
        )

        user.is_premium = True
        user.premium_until = subscription.current_period_end
        user.save(update_fields=['is_premium', 'premium_until'])
        invalidate_premium_status_cache(user)

        return {'proration_info': proration_info}

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
            
            logger.info("Payment success handled")
            
        except Subscription.DoesNotExist:
            logger.error("Subscription not found while handling payment success")
    
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
            
            logger.info("Payment failure handled")
            
        except Subscription.DoesNotExist:
            logger.error("Subscription not found while handling payment failure")
    
    def handle_subscription_renewal(self, event_data):
        """Handle subscription renewal webhook."""
        subscription_id = event_data.get('subscription_id')
        
        try:
            subscription = Subscription.objects.get(subscription_id=subscription_id)

            # Check for a pending plan change (proration=False from modify)
            pending_plan_change = None
            if subscription.cancellation_reason and subscription.cancellation_reason.startswith('plan_change:'):
                pending_plan_change = subscription.cancellation_reason.split(':', 1)[1]

            if pending_plan_change:
                try:
                    new_plan = SubscriptionPlan.objects.get(
                        plan_id=pending_plan_change, is_active=True
                    )
                    subscription.plan = new_plan
                    subscription.cancellation_reason = ''
                    subscription.cancel_at_period_end = False
                    logger.info(
                        "Applying pending subscription plan change: %s",
                        new_plan.plan_id,
                    )
                except SubscriptionPlan.DoesNotExist:
                    logger.warning(
                        f"Pending plan change target not found: "
                        f"{pending_plan_change}"
                    )
                    subscription.cancellation_reason = ''

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
            
            logger.info("Subscription renewed")
            
        except Subscription.DoesNotExist:
            logger.error("Subscription not found while handling renewal")
    
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
            
            logger.info("Subscription canceled")
            
        except Subscription.DoesNotExist:
            logger.error("Subscription not found while handling cancellation")
    
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
            
            logger.info("Refund processed")
            
        except Transaction.DoesNotExist:
            logger.error("Original transaction not found while handling refund")


class PremiumFeatureService:
    """
    Service for managing premium features and limits.
    """
    
    @staticmethod
    def check_premium_status(user):
        """Check if user has active premium subscription.

        Delegates to ``subscriptions.utils.is_premium_user`` so that premium
        access has exactly one definition. This method used to cache
        ``user.subscription.is_premium`` under the *same* cache key that
        ``is_premium_user`` uses for ``user.is_premium and premium_until >
        now`` — whichever ran first decided the answer for the other, and the
        two can disagree (for example right after an expiry).
        """
        from .utils import is_premium_user

        return is_premium_user(user)
    
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
