"""
Signals for subscriptions app.
File: subscriptions/signals.py
"""
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Subscription, Transaction
from .utils import invalidate_premium_status_cache
from authentication.models import User

logger = logging.getLogger('hivmeet.subscriptions.signals')


@receiver(post_save, sender=User)
def invalidate_premium_cache_on_user_change(sender, instance, **kwargs):
    """Drop the cached premium status whenever the premium fields are written.

    Covers every path that flips premium outside the subscription flow: admin
    edits, expiry sweeps, maintenance scripts. Cache-only side effect, so it
    cannot recurse into another save.
    """
    update_fields = kwargs.get('update_fields')
    if update_fields is not None and not (
        {'is_premium', 'premium_until'} & set(update_fields)
    ):
        return
    invalidate_premium_status_cache(instance)


@receiver(post_save, sender=Subscription)
def update_user_premium_status(sender, instance, created, **kwargs):
    """
    Update user's premium status when subscription changes.
    """
    if instance.is_premium:
        # Activate premium status
        instance.user.is_premium = True
        instance.user.premium_until = instance.current_period_end
        instance.user.save(update_fields=['is_premium', 'premium_until'])
        logger.info("Premium status activated")
    else:
        # Check if premium should be deactivated
        if instance.status in [Subscription.STATUS_CANCELED, Subscription.STATUS_EXPIRED]:
            if instance.current_period_end <= timezone.now():
                instance.user.is_premium = False
                instance.user.premium_until = None
                instance.user.save(update_fields=['is_premium', 'premium_until'])
                logger.info("Premium status deactivated")

    # Unconditional: any subscription write can change paid access, and a
    # cancellation reaching this signal previously left the 5-minute cache
    # untouched — the user kept premium features after losing them.
    invalidate_premium_status_cache(instance.user)


@receiver(pre_save, sender=Subscription)
def handle_subscription_status_change(sender, instance, **kwargs):
    """
    Handle subscription status changes.
    """
    if instance.pk:
        # Get the old instance
        try:
            old_instance = Subscription.objects.get(pk=instance.pk)
            
            # Check if status changed from active to canceled
            if (old_instance.status in [Subscription.STATUS_ACTIVE, Subscription.STATUS_TRIALING] and
                instance.status == Subscription.STATUS_CANCELED):
                
                # TODO: Send cancellation confirmation email
                logger.info("Subscription canceled")
            
            # Check if status changed to active
            elif (old_instance.status != Subscription.STATUS_ACTIVE and
                  instance.status == Subscription.STATUS_ACTIVE):
                
                # Reset counters on activation
                instance.boosts_remaining = instance.plan.monthly_boosts_count
                instance.super_likes_remaining = instance.plan.daily_super_likes_count
                instance.last_boosts_reset = timezone.now()
                instance.last_super_likes_reset = timezone.now()
                
                # TODO: Send activation confirmation email
                logger.info("Subscription activated")
                
        except Subscription.DoesNotExist:
            pass


@receiver(post_save, sender=Transaction)
def handle_transaction_created(sender, instance, created, **kwargs):
    """
    Handle new transaction creation.
    """
    if created:
        if instance.type == Transaction.TYPE_PURCHASE and instance.status == Transaction.STATUS_SUCCEEDED:
            # TODO: Send purchase confirmation email
            logger.info("Purchase transaction created")
        
        elif instance.type == Transaction.TYPE_REFUND and instance.status == Transaction.STATUS_SUCCEEDED:
            # TODO: Send refund confirmation email
            logger.info("Refund processed")


# Signal to sync premium features with profile
from django.db.models.signals import post_delete

@receiver(post_delete, sender=Subscription)
def remove_premium_on_subscription_delete(sender, instance, **kwargs):
    """
    Remove premium status when subscription is deleted.
    """
    try:
        user = instance.user
        user.is_premium = False
        user.premium_until = None
        user.save(update_fields=['is_premium', 'premium_until'])
        logger.info("Premium status removed after subscription deletion")
    except User.DoesNotExist:
        pass
