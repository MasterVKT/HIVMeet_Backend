"""
Admin configuration for subscriptions app.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import SubscriptionPlan, Subscription, Transaction, WebhookEvent


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['plan_id', 'name', 'price_display', 'billing_interval', 'is_active', 'order']
    list_filter = ['is_active', 'billing_interval', 'currency']
    search_fields = ['plan_id', 'name', 'name_en', 'name_fr']
    list_editable = ['is_active', 'order']
    
    fieldsets = (
        (_('Identification'), {
            'fields': ('plan_id',)
        }),
        (_('Names'), {
            'fields': ('name', 'name_en', 'name_fr')
        }),
        (_('Descriptions'), {
            'fields': ('description', 'description_en', 'description_fr')
        }),
        (_('Pricing'), {
            'fields': ('price', 'currency', 'billing_interval', 'trial_period_days')
        }),
        (_('Features'), {
            'fields': (
                'unlimited_likes', 'can_see_likers', 'can_rewind',
                'monthly_boosts_count', 'daily_super_likes_count',
                'media_messaging_enabled', 'audio_video_calls_enabled'
            )
        }),
        (_('Settings'), {
            'fields': ('is_active', 'order')
        }),
    )
    
    def price_display(self, obj):
        return f"{obj.price} {obj.currency}"
    price_display.short_description = _('Price')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'user_email', 'plan_name', 'status', 'period_display',
        'is_premium', 'auto_renew', 'created_at'
    ]
    list_filter = [
        'status', 'plan', 'auto_renew', 'cancel_at_period_end',
        'created_at', 'current_period_end'
    ]
    search_fields = ['user__email', 'user__display_name', 'subscription_id']
    readonly_fields = [
        'subscription_id', 'created_at', 'updated_at',
        'last_payment_attempt', 'canceled_at'
    ]
    
    fieldsets = (
        (_('User'), {
            'fields': ('user',)
        }),
        (_('Subscription'), {
            'fields': (
                'subscription_id', 'plan', 'status',
                'current_period_start', 'current_period_end', 'trial_end'
            )
        }),
        (_('Billing'), {
            'fields': (
                'auto_renew', 'cancel_at_period_end', 'canceled_at',
                'cancellation_reason', 'payment_method', 'last_payment_attempt'
            )
        }),
        (_('Features'), {
            'fields': (
                'boosts_remaining', 'super_likes_remaining',
                'last_boosts_reset', 'last_super_likes_reset'
            )
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = _('User')
    
    def plan_name(self, obj):
        return obj.plan.name
    plan_name.short_description = _('Plan')
    
    def period_display(self, obj):
        return format_html(
            '{} → {}',
            obj.current_period_start.strftime('%Y-%m-%d'),
            obj.current_period_end.strftime('%Y-%m-%d')
        )
    period_display.short_description = _('Period')
    
    def is_premium(self, obj):
        return obj.is_premium
    is_premium.boolean = True
    is_premium.short_description = _('Premium')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_id', 'user_email', 'type', 'status',
        'amount_display', 'created_at'
    ]
    list_filter = ['type', 'status', 'currency', 'created_at']
    search_fields = [
        'transaction_id', 'subscription__user__email',
        'subscription__subscription_id'
    ]
    readonly_fields = [
        'transaction_id', 'subscription', 'type', 'status',
        'amount', 'currency', 'payment_method', 'provider_response',
        'error_message', 'created_at', 'updated_at'
    ]
    
    def user_email(self, obj):
        return obj.subscription.user.email
    user_email.short_description = _('User')
    
    def amount_display(self, obj):
        return f"{obj.amount} {obj.currency}"
    amount_display.short_description = _('Amount')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = [
        'event_id', 'event_type', 'processed', 'processed_at', 'created_at'
    ]
    list_filter = ['event_type', 'processed', 'created_at']
    search_fields = ['event_id', 'event_type']
    readonly_fields = [
        'event_id', 'event_type', 'payload', 'processed',
        'processed_at', 'error_message', 'created_at'
    ]
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False