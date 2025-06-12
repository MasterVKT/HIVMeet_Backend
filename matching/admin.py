"""
Admin configuration for matching app.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import Like, Dislike, Match, ProfileView, Boost, DailyLikeLimit


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ['from_user', 'to_user', 'like_type', 'created_at']
    list_filter = ['like_type', 'created_at']
    search_fields = ['from_user__email', 'to_user__email']
    date_hierarchy = 'created_at'


@admin.register(Dislike)
class DislikeAdmin(admin.ModelAdmin):
    list_display = ['from_user', 'to_user', 'created_at', 'expires_at']
    list_filter = ['created_at', 'expires_at']
    search_fields = ['from_user__email', 'to_user__email']
    date_hierarchy = 'created_at'


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ['user1', 'user2', 'status', 'created_at', 'last_message_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user1__email', 'user2__email']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (_('Users'), {
            'fields': ('user1', 'user2', 'status')
        }),
        (_('Messaging'), {
            'fields': ('last_message_at', 'last_message_preview',
                      'user1_unread_count', 'user2_unread_count')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at')
        }),
    )
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ProfileView)
class ProfileViewAdmin(admin.ModelAdmin):
    list_display = ['viewer', 'viewed', 'viewed_at']
    list_filter = ['viewed_at']
    search_fields = ['viewer__email', 'viewed__email']
    date_hierarchy = 'viewed_at'


@admin.register(Boost)
class BoostAdmin(admin.ModelAdmin):
    list_display = ['user', 'started_at', 'expires_at', 'is_active_display', 'views_gained', 'likes_gained']
    list_filter = ['started_at', 'expires_at']
    search_fields = ['user__email']
    date_hierarchy = 'started_at'
    
    def is_active_display(self, obj):
        if obj.is_active():
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    is_active_display.short_description = _('Active')


@admin.register(DailyLikeLimit)
class DailyLikeLimitAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'likes_count', 'super_likes_count', 'rewinds_count']
    list_filter = ['date']
    search_fields = ['user__email']
    date_hierarchy = 'date'