"""
Models for subscriptions app.
"""
import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.validators import MinValueValidator
from datetime import timedelta

User = get_user_model()


class SubscriptionPlan(models.Model):
    """
    Model representing subscription plans.
    """
    
    INTERVAL_MONTH = 'month'
    INTERVAL_YEAR = 'year'
    
    INTERVAL_CHOICES = [
        (INTERVAL_MONTH, _('Monthly')),
        (INTERVAL_YEAR, _('Yearly')),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    plan_id = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_('Plan ID'),
        help_text=_('Unique identifier for the plan (e.g., hivmeet_monthly)')
    )
    
    name = models.CharField(
        max_length=100,
        verbose_name=_('Name')
    )
    
    name_en = models.CharField(
        max_length=100,
        verbose_name=_('Name (English)')
    )
    
    name_fr = models.CharField(
        max_length=100,
        verbose_name=_('Name (French)')
    )
    
    description = models.TextField(
        verbose_name=_('Description')
    )
    
    description_en = models.TextField(
        verbose_name=_('Description (English)')
    )
    
    description_fr = models.TextField(
        verbose_name=_('Description (French)')
    )
    
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Price')
    )
    
    currency = models.CharField(
        max_length=3,
        default='EUR',
        verbose_name=_('Currency')
    )
    
    billing_interval = models.CharField(
        max_length=10,
        choices=INTERVAL_CHOICES,
        verbose_name=_('Billing interval')
    )
    
    trial_period_days = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Trial period (days)')
    )
    
    # Features
    unlimited_likes = models.BooleanField(
        default=True,
        verbose_name=_('Unlimited likes')
    )
    
    can_see_likers = models.BooleanField(
        default=True,
        verbose_name=_('Can see who liked them')
    )
    
    can_rewind = models.BooleanField(
        default=True,
        verbose_name=_('Can rewind last swipe')
    )
    
    monthly_boosts_count = models.PositiveIntegerField(
        default=1,
        verbose_name=_('Monthly boosts count')
    )
    
    daily_super_likes_count = models.PositiveIntegerField(
        default=5,
        verbose_name=_('Daily super likes count')
    )
    
    media_messaging_enabled = models.BooleanField(
        default=True,
        verbose_name=_('Media messaging enabled')
    )
    
    audio_video_calls_enabled = models.BooleanField(
        default=True,
        verbose_name=_('Audio/video calls enabled')
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is active')
    )
    
    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Display order')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at')
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated at')
    )
    
    class Meta:
        verbose_name = _('Subscription plan')
        verbose_name_plural = _('Subscription plans')
        ordering = ['order', 'price']
        db_table = 'subscription_plans'
    
    def __str__(self):
        return f"{self.name} - {self.price} {self.currency}"
    
    def get_name(self, language='fr'):
        """Get localized name."""
        if language == 'en':
            return self.name_en or self.name
        return self.name_fr or self.name
    
    def get_description(self, language='fr'):
        """Get localized description."""
        if language == 'en':
            return self.description_en or self.description
        return self.description_fr or self.description
    
    def get_features_list(self):
        """Get list of included features."""
        features = []
        if self.unlimited_likes:
            features.append('unlimited_likes')
        if self.can_see_likers:
            features.append('can_see_likers')
        if self.can_rewind:
            features.append('can_rewind')
        if self.monthly_boosts_count > 0:
            features.append('monthly_boosts')
        if self.daily_super_likes_count > 0:
            features.append('daily_super_likes')
        if self.media_messaging_enabled:
            features.append('media_messaging')
        if self.audio_video_calls_enabled:
            features.append('audio_video_calls')
        return features


class Subscription(models.Model):
    """
    Model representing user subscriptions.
    """
    
    STATUS_PENDING = 'pending'
    STATUS_ACTIVE = 'active'
    STATUS_TRIALING = 'trialing'
    STATUS_PAST_DUE = 'past_due'
    STATUS_CANCELED = 'canceled'
    STATUS_EXPIRED = 'expired'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, _('Pending')),
        (STATUS_ACTIVE, _('Active')),
        (STATUS_TRIALING, _('Trialing')),
        (STATUS_PAST_DUE, _('Past due')),
        (STATUS_CANCELED, _('Canceled')),
        (STATUS_EXPIRED, _('Expired')),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    subscription_id = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('Subscription ID'),
        help_text=_('External subscription ID from payment provider')
    )
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='subscription',
        verbose_name=_('User')
    )
    
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions',
        verbose_name=_('Plan')
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name=_('Status')
    )
    
    current_period_start = models.DateTimeField(
        verbose_name=_('Current period start')
    )
    
    current_period_end = models.DateTimeField(
        verbose_name=_('Current period end')
    )
    
    trial_end = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Trial end')
    )
    
    auto_renew = models.BooleanField(
        default=True,
        verbose_name=_('Auto-renew')
    )
    
    cancel_at_period_end = models.BooleanField(
        default=False,
        verbose_name=_('Cancel at period end')
    )
    
    canceled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Canceled at')
    )
    
    cancellation_reason = models.TextField(
        blank=True,
        verbose_name=_('Cancellation reason')
    )
    
    # Feature counters
    boosts_remaining = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Boosts remaining')
    )
    
    super_likes_remaining = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Super likes remaining')
    )
    
    last_boosts_reset = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Last boosts reset')
    )
    
    last_super_likes_reset = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Last super likes reset')
    )
    
    # Payment info
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Payment method')
    )
    
    last_payment_attempt = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Last payment attempt')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at')
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated at')
    )
    
    class Meta:
        verbose_name = _('Subscription')
        verbose_name_plural = _('Subscriptions')
        db_table = 'subscriptions'
        indexes = [
            models.Index(fields=['status', 'current_period_end']),
            models.Index(fields=['user', 'status']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.plan.name} ({self.status})"
    
    @property
    def is_active(self):
        """Check if subscription is currently active."""
        return self.status in [self.STATUS_ACTIVE, self.STATUS_TRIALING]
    
    @property
    def is_premium(self):
        """Check if user has premium features."""
        return self.is_active and timezone.now() < self.current_period_end
    
    def reset_monthly_counters(self):
        """Reset monthly feature counters."""
        self.boosts_remaining = self.plan.monthly_boosts_count
        self.last_boosts_reset = timezone.now()
        self.save(update_fields=['boosts_remaining', 'last_boosts_reset'])
    
    def reset_daily_counters(self):
        """Reset daily feature counters."""
        self.super_likes_remaining = self.plan.daily_super_likes_count
        self.last_super_likes_reset = timezone.now()
        self.save(update_fields=['super_likes_remaining', 'last_super_likes_reset'])
    
    def use_boost(self):
        """Use a boost if available."""
        if self.boosts_remaining > 0:
            self.boosts_remaining -= 1
            self.save(update_fields=['boosts_remaining'])
            return True
        return False
    
    def use_super_like(self):
        """Use a super like if available."""
        if self.super_likes_remaining > 0:
            self.super_likes_remaining -= 1
            self.save(update_fields=['super_likes_remaining'])
            return True
        return False


class Transaction(models.Model):
    """
    Model for tracking payment transactions.
    """
    
    TYPE_PURCHASE = 'purchase'
    TYPE_RENEWAL = 'renewal'
    TYPE_REFUND = 'refund'
    
    TYPE_CHOICES = [
        (TYPE_PURCHASE, _('Purchase')),
        (TYPE_RENEWAL, _('Renewal')),
        (TYPE_REFUND, _('Refund')),
    ]
    
    STATUS_PENDING = 'pending'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, _('Pending')),
        (STATUS_SUCCEEDED, _('Succeeded')),
        (STATUS_FAILED, _('Failed')),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    transaction_id = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('Transaction ID'),
        help_text=_('External transaction ID from payment provider')
    )
    
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name=_('Subscription')
    )
    
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        verbose_name=_('Type')
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name=_('Status')
    )
    
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Amount')
    )
    
    currency = models.CharField(
        max_length=3,
        default='EUR',
        verbose_name=_('Currency')
    )
    
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Payment method')
    )
    
    provider_response = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Provider response'),
        help_text=_('Raw response from payment provider')
    )
    
    error_message = models.TextField(
        blank=True,
        verbose_name=_('Error message')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at')
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated at')
    )
    
    class Meta:
        verbose_name = _('Transaction')
        verbose_name_plural = _('Transactions')
        db_table = 'subscription_transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['subscription', '-created_at']),
            models.Index(fields=['status', 'type']),
        ]
    
    def __str__(self):
        return f"{self.transaction_id} - {self.amount} {self.currency} ({self.status})"


class WebhookEvent(models.Model):
    """
    Model for tracking webhook events from payment provider.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    event_id = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('Event ID'),
        help_text=_('External event ID from payment provider')
    )
    
    event_type = models.CharField(
        max_length=50,
        verbose_name=_('Event type')
    )
    
    payload = models.JSONField(
        verbose_name=_('Payload'),
        help_text=_('Raw webhook payload')
    )
    
    processed = models.BooleanField(
        default=False,
        verbose_name=_('Processed')
    )
    
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Processed at')
    )
    
    error_message = models.TextField(
        blank=True,
        verbose_name=_('Error message')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at')
    )
    
    class Meta:
        verbose_name = _('Webhook event')
        verbose_name_plural = _('Webhook events')
        db_table = 'webhook_events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['processed', 'created_at']),
            models.Index(fields=['event_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.event_id}"