"""
Serializers for subscriptions app.
"""
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal
from .models import SubscriptionPlan, Subscription, Transaction
from authentication.models import User


class PlanFeaturesSummarySerializer(serializers.Serializer):
    """Serializer for plan features summary."""
    unlimited_likes = serializers.BooleanField()
    can_see_likers = serializers.BooleanField()
    can_rewind = serializers.BooleanField()
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
    features = serializers.SerializerMethodField()
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            'plan_id',
            'name',
            'description',
            'price',
            'currency',
            'billing_interval',
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
    
    def get_features(self, obj):
        """Get list of feature keys."""
        return obj.get_features_list()


class CurrentSubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for current user subscription.
    """
    subscription_id = serializers.CharField(read_only=True)
    plan_id = serializers.CharField(source='plan.plan_id', read_only=True)
    plan_name = serializers.SerializerMethodField()
    features_summary = serializers.SerializerMethodField()
    
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
            'monthly_boosts_count': obj.plan.monthly_boosts_count,
            'daily_super_likes_count': obj.plan.daily_super_likes_count,
            'media_messaging_enabled': obj.plan.media_messaging_enabled,
            'audio_video_calls_enabled': obj.plan.audio_video_calls_enabled
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
            'monthly_boosts_count': 0,
            'daily_super_likes_count': 0,
            'media_messaging_enabled': False,
            'audio_video_calls_enabled': False
        }


class PurchaseSubscriptionSerializer(serializers.Serializer):
    """
    Serializer for purchasing a subscription.
    """
    plan_id = serializers.CharField(required=True)
    payment_method_token = serializers.CharField(required=True)
    coupon_code = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    
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


class WebhookSerializer(serializers.Serializer):
    """
    Serializer for MyCoolPay webhook payload.
    """
    event_id = serializers.CharField(required=True)
    event_type = serializers.CharField(required=True)
    data = serializers.JSONField(required=True)
    signature = serializers.CharField(required=True)
    timestamp = serializers.DateTimeField(required=True)
    
    def validate(self, data):
        """Validate webhook signature."""
        # TODO: Implement signature validation with MyCoolPay secret
        # This should verify the webhook signature to ensure it's from MyCoolPay
        return data