"""
Celery configuration for HIVMeet.
File: hivmeet_backend/celery.py
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')

# Create Celery app
app = Celery('hivmeet_backend')

# Configure Celery using settings from Django settings.py
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load tasks from all registered Django apps
app.autodiscover_tasks()

# Celery beat schedule
app.conf.beat_schedule = {
    # Subscription tasks
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

# Debug task
@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')