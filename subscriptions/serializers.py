"""
Serializers for subscriptions app.
"""
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal
from .models import SubscriptionPlan, Subscription, Transaction
from .pricing import (
    PREMIUM_DAILY_REWINDS,
    monthly_equivalent,
    quote_plan,
    savings_percentage,
)
from authentication.models import User


class PlanFeaturesSummarySerializer(serializers.Serializer):
    """Serializer for plan features summary."""
    unlimited_likes = serializers.BooleanField()
    can_see_likers = serializers.BooleanField()
    can_rewind = serializers.BooleanField()
    daily_rewinds_count = serializers.IntegerField()
    monthly_boosts_count = serializers.IntegerField()
    daily_super_likes_count = serializers.IntegerField()
    media_messaging_enabled = serializers.BooleanField()
    audio_video_calls_enabled = serializers.BooleanField()


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """
    Serializer for subscription plans.
    """
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    base_price = serializers.SerializerMethodField()
    base_currency = serializers.CharField(source='currency', read_only=True)
    monthly_equivalent = serializers.SerializerMethodField()
    savings_percentage = serializers.SerializerMethodField()
    most_popular = serializers.SerializerMethodField()
    recommended = serializers.SerializerMethodField()
    features = serializers.SerializerMethodField()
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            'plan_id',
            'name',
            'description',
            'price',
            'currency',
            'base_price',
            'base_currency',
            'billing_interval',
            'monthly_equivalent',
            'savings_percentage',
            'most_popular',
            'recommended',
            'features',
            'trial_period_days'
        ]
    
    def get_name(self, obj):
        """Get localized name."""
        language = self.context.get('language', 'fr')
        return obj.get_name(language)
    
    def get_description(self, obj):
        """Get localized description."""
        language = self.context.get('language', 'fr')
        return obj.get_description(language)

    def _quote(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return quote_plan(obj, request.user)
        return {'amount': obj.price, 'currency': obj.currency}

    @staticmethod
    def _format_amount(value):
        return format(Decimal(value), 'f')

    def get_price(self, obj):
        return self._format_amount(self._quote(obj)['amount'])

    def get_currency(self, obj):
        return self._quote(obj)['currency']

    def get_base_price(self, obj):
        return self._format_amount(obj.price)

    def get_monthly_equivalent(self, obj):
        quote = self._quote(obj)
        value = monthly_equivalent(obj, quote['currency'])
        return self._format_amount(value)

    def get_savings_percentage(self, obj):
        return savings_percentage(
            obj,
            self.context.get('monthly_reference_price'),
        )

    def get_most_popular(self, obj):
        return obj.billing_interval == SubscriptionPlan.INTERVAL_YEAR

    def get_recommended(self, obj):
        return self.get_most_popular(obj)
    
    def get_features(self, obj):
        """Return explicit entitlements and limits for this plan."""
        return {
            'unlimited_likes': obj.unlimited_likes,
            'can_see_likers': obj.can_see_likers,
            'can_rewind': obj.can_rewind,
            'daily_rewinds_count': (
                PREMIUM_DAILY_REWINDS if obj.can_rewind else 0
            ),
            'monthly_boosts_count': obj.monthly_boosts_count,
            'daily_super_likes_count': obj.daily_super_likes_count,
            'media_messaging_enabled': obj.media_messaging_enabled,
            'audio_video_calls_enabled': obj.audio_video_calls_enabled,
        }


class CurrentSubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for current user subscription.
    """
    subscription_id = serializers.CharField(read_only=True)
    plan_id = serializers.CharField(source='plan.plan_id', read_only=True)
    plan_name = serializers.SerializerMethodField()
    features_summary = serializers.SerializerMethodField()
    scheduled_change = serializers.SerializerMethodField()
    
    class Meta:
        model = Subscription
        fields = [
            'subscription_id',
            'plan_id',
            'plan_name',
            'status',
            'current_period_start',
            'current_period_end',
            'auto_renew',
            'cancel_at_period_end',
            'scheduled_change',
            'features_summary'
        ]
    
    def get_plan_name(self, obj):
        """Get localized plan name."""
        language = self.context.get('language', 'fr')
        return obj.plan.get_name(language)
    
    def get_features_summary(self, obj):
        """Get features summary."""
        return {
            'unlimited_likes': obj.plan.unlimited_likes,
            'can_see_likers': obj.plan.can_see_likers,
            'can_rewind': obj.plan.can_rewind,
            'daily_rewinds_count': (
                PREMIUM_DAILY_REWINDS if obj.plan.can_rewind else 0
            ),
            'monthly_boosts_count': obj.plan.monthly_boosts_count,
            'daily_super_likes_count': obj.plan.daily_super_likes_count,
            'media_messaging_enabled': obj.plan.media_messaging_enabled,
            'audio_video_calls_enabled': obj.plan.audio_video_calls_enabled
        }

    def get_scheduled_change(self, obj):
        marker = obj.cancellation_reason or ''
        if not obj.cancel_at_period_end or not marker.startswith('plan_change:'):
            return None
        plan_id = marker.split(':', 1)[1]
        target = SubscriptionPlan.objects.filter(
            plan_id=plan_id,
            is_active=True,
        ).first()
        if target is None:
            return None
        language = self.context.get('language', 'fr')
        return {
            'plan_id': target.plan_id,
            'plan_name': target.get_name(language),
            'effective_at': obj.current_period_end,
        }


class EmptySubscriptionSerializer(serializers.Serializer):
    """
    Serializer for users without subscription.
    """
    subscription_id = serializers.SerializerMethodField()
    plan_id = serializers.SerializerMethodField()
    plan_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    current_period_start = serializers.SerializerMethodField()
    current_period_end = serializers.SerializerMethodField()
    auto_renew = serializers.SerializerMethodField()
    cancel_at_period_end = serializers.SerializerMethodField()
    features_summary = serializers.SerializerMethodField()
    
    def get_subscription_id(self, obj):
        return None
    
    def get_plan_id(self, obj):
        return None
    
    def get_plan_name(self, obj):
        return None
    
    def get_status(self, obj):
        return 'none'
    
    def get_current_period_start(self, obj):
        return None
    
    def get_current_period_end(self, obj):
        return None
    
    def get_auto_renew(self, obj):
        return None
    
    def get_cancel_at_period_end(self, obj):
        return False
    
    def get_features_summary(self, obj):
        return {
            'unlimited_likes': False,
            'can_see_likers': False,
            'can_rewind': False,
            'daily_rewinds_count': 0,
            'monthly_boosts_count': 0,
            'daily_super_likes_count': 0,
            'media_messaging_enabled': False,
            'audio_video_calls_enabled': False
        }


class PurchaseSubscriptionSerializer(serializers.Serializer):
    """Validate a server-created MyCoolPay Paylink request."""
    plan_id = serializers.CharField(required=True)
    phone_number = serializers.RegexField(
        regex=r'^\+?[0-9]{8,15}$',
        max_length=16,
        required=True,
    )
    language = serializers.ChoiceField(
        choices=('fr', 'en'),
        required=False,
        default='fr',
    )
    
    def validate_plan_id(self, value):
        """Validate plan exists and is active."""
        try:
            plan = SubscriptionPlan.objects.get(plan_id=value, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError(_("Invalid plan ID"))
        return value


class SubscriptionResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for subscription purchase response.
    """
    subscription_id = serializers.CharField(read_only=True)
    plan_id = serializers.CharField(source='plan.plan_id', read_only=True)
    message = serializers.SerializerMethodField()
    
    class Meta:
        model = Subscription
        fields = [
            'subscription_id',
            'plan_id',
            'status',
            'current_period_start',
            'current_period_end',
            'auto_renew',
            'message'
        ]
    
    def get_message(self, obj):
        """Get success message."""
        return _("Subscription activated successfully.")


class CancelSubscriptionSerializer(serializers.Serializer):
    """
    Serializer for canceling a subscription.
    """
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class CancelSubscriptionResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for subscription cancellation response.
    """
    message = serializers.SerializerMethodField()
    
    class Meta:
        model = Subscription
        fields = [
            'status',
            'cancel_at_period_end',
            'current_period_end',
            'message'
        ]
    
    def get_message(self, obj):
        """Get cancellation message."""
        return _("Your subscription will be canceled at the end of the current period.")


class ModifySubscriptionSerializer(serializers.Serializer):
    """
    Serializer for modifying (upgrading/downgrading) a subscription.

    POST /api/v1/subscriptions/current/modify/

    ``phone_number``/``language`` are only required when the immediate
    (prorated) change turns out to need a real charge — the view validates
    their presence itself once the net amount is known, since a serializer
    field can't be conditionally required on a value computed server-side.
    """
    new_plan_id = serializers.CharField(required=True)
    proration = serializers.BooleanField(required=False, default=True)
    phone_number = serializers.RegexField(
        regex=r'^\+?[0-9]{8,15}$',
        max_length=16,
        required=False,
        allow_blank=True,
    )
    language = serializers.ChoiceField(
        choices=('fr', 'en'),
        required=False,
        default='fr',
    )

    def validate_new_plan_id(self, value):
        """Validate that the target plan exists and is active."""
        try:
            SubscriptionPlan.objects.get(plan_id=value, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError(_("Invalid plan ID"))
        return value


class ProrationInfoSerializer(serializers.Serializer):
    """
    Serializer for the proration block returned by the modify endpoint.
    """
    credit_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    charge_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    currency = serializers.CharField(required=False, allow_null=True)
    prorated_period_start = serializers.DateTimeField(required=False, allow_null=True)
    prorated_period_end = serializers.DateTimeField(required=False, allow_null=True)


class TransactionSerializer(serializers.ModelSerializer):
    """
    Serializer for payment transactions.
    """
    class Meta:
        model = Transaction
        fields = [
            'transaction_id',
            'type',
            'status',
            'amount',
            'currency',
            'payment_method',
            'created_at'
        ]
        read_only_fields = fields

# MyCoolPay callback payloads are authenticated and validated in the webhook view.
