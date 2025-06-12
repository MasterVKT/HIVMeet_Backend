"""
Periodic tasks for subscriptions app.
"""
import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
from celery import shared_task
from .models import Subscription, SubscriptionPlan
from .services import MyCoolPayService

logger = logging.getLogger('hivmeet.subscriptions.tasks')


@shared_task
def check_subscription_expirations():
    """
    Check for expired subscriptions and update their status.
    Runs every hour.
    """
    logger.info("Starting subscription expiration check")
    
    # Find subscriptions that have expired
    expired_subscriptions = Subscription.objects.filter(
        status__in=[Subscription.STATUS_ACTIVE, Subscription.STATUS_TRIALING],
        current_period_end__lt=timezone.now()
    )
    
    for subscription in expired_subscriptions:
        if subscription.cancel_at_period_end:
            # Subscription was canceled and should expire
            subscription.status = Subscription.STATUS_CANCELED
            logger.info(f"Subscription {subscription.subscription_id} canceled after period end")
        else:
            # Subscription should be renewed but payment might have failed
            subscription.status = Subscription.STATUS_EXPIRED
            logger.info(f"Subscription {subscription.subscription_id} expired")
        
        subscription.save()
        
        # Update user premium status
        user = subscription.user
        user.is_premium = False
        user.premium_until = None
        user.save(update_fields=['is_premium', 'premium_until'])
    
    logger.info(f"Processed {expired_subscriptions.count()} expired subscriptions")


@shared_task
def send_expiration_reminders():
    """
    Send reminders to users whose subscriptions are about to expire.
    Runs daily.
    """
    logger.info("Starting expiration reminder task")
    
    # Reminders 3 days before expiration
    three_days_from_now = timezone.now() + timedelta(days=3)
    subscriptions_3days = Subscription.objects.filter(
        status=Subscription.STATUS_ACTIVE,
        cancel_at_period_end=False,
        current_period_end__date=three_days_from_now.date()
    ).select_related('user')
    
    for subscription in subscriptions_3days:
        # TODO: Send notification/email to user
        logger.info(f"3-day reminder for user {subscription.user.email}")
    
    # Reminders 1 day before expiration
    tomorrow = timezone.now() + timedelta(days=1)
    subscriptions_1day = Subscription.objects.filter(
        status=Subscription.STATUS_ACTIVE,
        cancel_at_period_end=False,
        current_period_end__date=tomorrow.date()
    ).select_related('user')
    
    for subscription in subscriptions_1day:
        # TODO: Send notification/email to user
        logger.info(f"1-day reminder for user {subscription.user.email}")
    
    logger.info(f"Sent {subscriptions_3days.count() + subscriptions_1day.count()} reminders")


@shared_task
def reset_daily_counters():
    """
    Reset daily feature counters (super likes).
    Runs daily at midnight.
    """
    logger.info("Starting daily counter reset")
    
    # Get all active subscriptions
    active_subscriptions = Subscription.objects.filter(
        status__in=[Subscription.STATUS_ACTIVE, Subscription.STATUS_TRIALING]
    )
    
    reset_count = 0
    for subscription in active_subscriptions:
        # Check if reset is needed (more than 24 hours since last reset)
        if (timezone.now() - subscription.last_super_likes_reset).total_seconds() >= 86400:
            subscription.reset_daily_counters()
            reset_count += 1
    
    logger.info(f"Reset daily counters for {reset_count} subscriptions")


@shared_task
def reset_monthly_counters():
    """
    Reset monthly feature counters (boosts).
    Runs daily, checks each subscription individually.
    """
    logger.info("Starting monthly counter reset")
    
    # Get all active monthly subscriptions
    monthly_subscriptions = Subscription.objects.filter(
        status__in=[Subscription.STATUS_ACTIVE, Subscription.STATUS_TRIALING],
        plan__billing_interval=SubscriptionPlan.INTERVAL_MONTH
    )
    
    reset_count = 0
    for subscription in monthly_subscriptions:
        # Check if 30 days have passed since last reset
        if (timezone.now() - subscription.last_boosts_reset).days >= 30:
            subscription.reset_monthly_counters()
            reset_count += 1
    
    logger.info(f"Reset monthly counters for {reset_count} subscriptions")


@shared_task
def retry_failed_payments():
    """
    Retry failed subscription payments.
    Runs every 6 hours.
    """
    logger.info("Starting failed payment retry")
    
    # Get subscriptions in past_due status
    past_due_subscriptions = Subscription.objects.filter(
        status=Subscription.STATUS_PAST_DUE,
        auto_renew=True
    ).select_related('user', 'plan')
    
    payment_service = MyCoolPayService()
    retry_count = 0
    success_count = 0
    
    for subscription in past_due_subscriptions:
        # Don't retry if last attempt was within 24 hours
        if subscription.last_payment_attempt:
            hours_since_last = (timezone.now() - subscription.last_payment_attempt).total_seconds() / 3600
            if hours_since_last < 24:
                continue
        
        try:
            # Attempt to charge the subscription
            result = payment_service._make_request(
                'POST',
                f'subscriptions/{subscription.subscription_id}/retry',
                {}
            )
            
            if result.get('status') == 'succeeded':
                success_count += 1
                logger.info(f"Payment retry successful for subscription {subscription.subscription_id}")
            
            retry_count += 1
            
        except Exception as e:
            logger.error(f"Payment retry failed for subscription {subscription.subscription_id}: {str(e)}")
        
        # Update last payment attempt
        subscription.last_payment_attempt = timezone.now()
        subscription.save(update_fields=['last_payment_attempt'])
    
    logger.info(f"Retried {retry_count} payments, {success_count} successful")


@shared_task
def clean_old_webhook_events():
    """
    Clean up old processed webhook events.
    Runs weekly.
    """
    logger.info("Starting webhook event cleanup")
    
    # Delete processed events older than 30 days
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    from .models import WebhookEvent
    deleted_count = WebhookEvent.objects.filter(
        processed=True,
        created_at__lt=thirty_days_ago
    ).delete()[0]
    
    logger.info(f"Deleted {deleted_count} old webhook events")


# Celery beat schedule configuration
# Add this to your celery configuration:
"""
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'check-subscription-expirations': {
        'task': 'subscriptions.tasks.check_subscription_expirations',
        'schedule': crontab(minute=0),  # Every hour
    },
    'send-expiration-reminders': {
        'task': 'subscriptions.tasks.send_expiration_reminders',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM
    },
    'reset-daily-counters': {
        'task': 'subscriptions.tasks.reset_daily_counters',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
    'reset-monthly-counters': {
        'task': 'subscriptions.tasks.reset_monthly_counters',
        'schedule': crontab(hour=0, minute=30),  # Daily at 00:30
    },
    'retry-failed-payments': {
        'task': 'subscriptions.tasks.retry_failed_payments',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
    'clean-old-webhook-events': {
        'task': 'subscriptions.tasks.clean_old_webhook_events',
        'schedule': crontab(hour=2, minute=0, day_of_week=1),  # Weekly on Monday at 2 AM
    },
}
"""