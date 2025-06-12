"""
Admin configuration for messaging app.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import Message, MessageReaction, Call, TypingIndicator


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'get_recipient', 'message_type', 'content_preview', 'status', 'created_at']
    list_filter = ['message_type', 'status', 'created_at']
    search_fields = ['sender__email', 'content']
    date_hierarchy = 'created_at'
    readonly_fields = ['id', 'client_message_id', 'created_at', 'delivered_at', 'read_at']
    
    def get_recipient(self, obj):
        return obj.get_recipient()
    get_recipient.short_description = _('Recipient')
    
    def content_preview(self, obj):
        if obj.content:
            return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
        return f"[{obj.message_type}]"
    content_preview.short_description = _('Content')
    
    fieldsets = (
        (_('Message Info'), {
            'fields': ('id', 'client_message_id', 'match', 'sender', 'message_type')
        }),
        (_('Content'), {
            'fields': ('content', 'media_url', 'media_thumbnail_url', 'media_file_path')
        }),
        (_('Status'), {
            'fields': ('status', 'created_at', 'delivered_at', 'read_at')
        }),
        (_('Deletion'), {
            'fields': ('is_deleted_by_sender', 'is_deleted_by_recipient')
        }),
    )


@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    list_display = ['caller', 'callee', 'call_type', 'status', 'duration_display', 'initiated_at']
    list_filter = ['call_type', 'status', 'initiated_at']
    search_fields = ['caller__email', 'callee__email']
    date_hierarchy = 'initiated_at'
    readonly_fields = ['id', 'initiated_at', 'answered_at', 'ended_at', 'duration_seconds']
    
    def duration_display(self, obj):
        if obj.duration_seconds:
            minutes = obj.duration_seconds // 60
            seconds = obj.duration_seconds % 60
            return f"{minutes}:{seconds:02d}"
        return '-'
    duration_display.short_description = _('Duration')
    
    fieldsets = (
        (_('Call Info'), {
            'fields': ('id', 'match', 'caller', 'callee', 'call_type')
        }),
        (_('Status'), {
            'fields': ('status', 'end_reason')
        }),
        (_('Timing'), {
            'fields': ('initiated_at', 'answered_at', 'ended_at', 'duration_seconds')
        }),
        (_('WebRTC Data'), {
            'classes': ('collapse',),
            'fields': ('offer_sdp', 'answer_sdp', 'ice_candidates')
        }),
    )