"""
Periodic tasks for subscriptions app.
"""
import logging
from datetime import timedelta
from django.conf import settings
from django.utils.translation import gettext as _
from django.utils import timezone
from django.db.models import Q
from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from asgiref.sync import sync_to_async
from firebase_admin import messaging

from .models import Subscription, SubscriptionPlan, PaymentTransaction
from .payment_gateway import (
    MyCoolPayError,
    MyCoolPayTransientError,
    reconcile_payment_if_due,
)
from notifications.models import Notification
from notifications.fcm import send_fcm_to_user
from notifications.payloads import subscription_expiry_payload

logger = logging.getLogger('hivmeet.subscriptions.tasks')


@shared_task(
    bind=True,
    max_retries=4,
    soft_time_limit=25,
    time_limit=30,
    acks_late=True,
    reject_on_worker_lost=True,
)
def reconcile_mycoolpay_payment(self, payment_id, force=False):
    """Reconcile one payment with bounded retries for transient failures."""
    try:
        payment, attempted = reconcile_payment_if_due(
            payment_id,
            min_interval_seconds=getattr(
                settings,
                'MYCOOLPAY_RECONCILIATION_MIN_AGE_SECONDS',
                60,
            ),
            force=force,
        )
    except PaymentTransaction.DoesNotExist:
        return 'missing'
    except MyCoolPayTransientError as exc:
        logger.warning(
            "Transient MyCoolPay reconciliation failure; payment=%s retry=%s",
            payment_id,
            self.request.retries,
        )
        countdown = min(30 * (2 ** self.request.retries), 300)
        raise self.retry(
            exc=exc,
            countdown=countdown,
            kwargs={'force': True},
        )
    except MyCoolPayError:
        logger.warning(
            "Rejected MyCoolPay reconciliation payload; payment=%s",
            payment_id,
        )
        return 'rejected'
    return 'reconciled' if attempted else payment.status.lower()


@shared_task
def reconcile_pending_mycoolpay_payments():
    """Schedule bounded recovery for callbacks MyCoolPay did not retry."""
    now = timezone.now()
    min_age = max(
        1,
        getattr(settings, 'MYCOOLPAY_RECONCILIATION_MIN_AGE_SECONDS', 60),
    )
    max_age_hours = max(
        1,
        getattr(settings, 'MYCOOLPAY_RECONCILIATION_MAX_AGE_HOURS', 168),
    )
    batch_size = min(
        500,
        max(1, getattr(settings, 'MYCOOLPAY_RECONCILIATION_BATCH_SIZE', 100)),
    )
    cutoff = now - timedelta(seconds=min_age)
    oldest = now - timedelta(hours=max_age_hours)
    pending = PaymentTransaction.objects.filter(
        status=PaymentTransaction.STATUS_PENDING,
        provider_transaction_ref__isnull=False,
        created_at__gte=oldest,
        created_at__lte=cutoff,
    ).filter(
        Q(last_checked_at__isnull=True) | Q(last_checked_at__lte=cutoff)
    ).order_by('created_at').values_list('id', flat=True)[:batch_size]

    payment_ids = list(pending)
    for payment_id in payment_ids:
        reconcile_mycoolpay_payment.delay(str(payment_id))
    return len(payment_ids)


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
            logger.info("Subscription canceled after period end")
        else:
            # Subscription should be renewed but payment might have failed
            subscription.status = Subscription.STATUS_EXPIRED
            logger.info("Subscription expired")
        
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
    Runs daily at 9 AM.

    Intervals: 7 days, 5 days, 3 days, and 1 day before expiration.
    Each reminder creates a Notification DB record, sends an FCM push,
    and broadcasts a WebSocket event — with anti-duplicate protection.
    """
    logger.info("Starting expiration reminder task")
    now = timezone.now()
    reminder_intervals = [7, 5, 3, 1]
    total_sent = 0

    for days in reminder_intervals:
        target_date = now + timedelta(days=days)
        subscriptions = Subscription.objects.filter(
            status=Subscription.STATUS_ACTIVE,
            cancel_at_period_end=False,
            current_period_end__date=target_date.date(),
        ).select_related('user')

        for subscription in subscriptions:
            user = subscription.user
            expiry_date = subscription.current_period_end.date().isoformat()

            # Anti-duplicate: check if a notification for this interval
            # already exists (the task runs daily, so we only create one
            # notification per interval per subscription period)
            notif_id = f'sub_expiry_{user.id}_{days}d'
            existing = Notification.objects.filter(
                user=user,
                type='subscription_expiring',
                data__notification_id=notif_id,
            ).exists()

            if existing:
                logger.debug(
                    "Reminder already sent: user=%s days=%d", user.id, days
                )
                continue

            # 1. Create Notification DB record
            try:
                title = "Votre abonnement expire bientôt"
                if days == 1:
                    body = "Votre abonnement Premium expire demain. Renouvelez-le dès maintenant !"
                else:
                    body = f"Plus que {days} jours pour renouveler votre abonnement Premium."

                Notification.objects.create(
                    user=user,
                    type='subscription_expiring',
                    title=title,
                    body=body,
                    data={
                        'type': 'subscription_expiring',
                        'notification_id': notif_id,
                        'days_remaining': str(days),
                        'expiry_date': expiry_date,
                    },
                )
            except Exception:
                logger.warning(
                    "Failed to create subscription expiry notification: "
                    "user=%s days=%d", user.id, days
                )
                continue

            # 2. Send FCM push
            try:
                data = subscription_expiry_payload(
                    user_id=str(user.id),
                    days_remaining=days,
                    expiry_date=expiry_date,
                )
                notif = messaging.Notification(
                    title=data['title'],
                    body=data['body'],
                )
                send_fcm_to_user(user, notification=notif, data=data)
            except Exception:
                logger.warning(
                    "FCM push failed for subscription expiry: user=%s days=%d",
                    user.id, days,
                )

            # 3. Broadcast WebSocket event
            try:
                channel_layer = get_channel_layer()
                if channel_layer:
                    async_to_sync(channel_layer.group_send)(
                        f"user_{user.id}",
                        {
                            "type": "subscription_expiring",
                            "notification_id": notif_id,
                            "days_remaining": str(days),
                            "expiry_date": expiry_date,
                        }
                    )
            except Exception:
                logger.warning(
                    "WebSocket dispatch failed for subscription expiry; days=%d",
                    days,
                )

            total_sent += 1
            logger.info("Subscription expiry reminder sent; days=%d", days)

    logger.info("Sent %d subscription expiry reminders", total_sent)


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
    """Deprecated compatibility task.

    MyCoolPay Paylinks are customer-initiated and expose no recurring-charge
    endpoint. Pending Paylinks are recovered by
    ``reconcile_pending_mycoolpay_payments`` instead.
    """
    logger.info("Skipped unsupported automatic MyCoolPay payment retries")
    return 0


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
