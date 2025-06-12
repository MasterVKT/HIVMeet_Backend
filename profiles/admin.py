"""
Admin configuration for profiles app.
"""
from django.utils import timezone
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import Profile, ProfilePhoto, Verification


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'city', 'country', 'gender', 'is_hidden', 'created_at']
    list_filter = ['gender', 'is_hidden', 'allow_profile_in_discovery', 'created_at']
    search_fields = ['user__email', 'user__display_name', 'city', 'country']
    readonly_fields = ['created_at', 'updated_at', 'profile_views', 'likes_received']
    
    fieldsets = (
        (_('User'), {
            'fields': ('user',)
        }),
        (_('Personal Information'), {
            'fields': ('bio', 'gender', 'interests')
        }),
        (_('Location'), {
            'fields': ('latitude', 'longitude', 'city', 'country', 'hide_exact_location')
        }),
        (_('Preferences'), {
            'fields': ('relationship_types_sought', 'age_min_preference', 'age_max_preference',
                      'distance_max_km', 'genders_sought')
        }),
        (_('Visibility'), {
            'fields': ('is_hidden', 'show_online_status', 'allow_profile_in_discovery')
        }),
        (_('Statistics'), {
            'fields': ('profile_views', 'likes_received', 'created_at', 'updated_at')
        }),
    )


@admin.register(ProfilePhoto)
class ProfilePhotoAdmin(admin.ModelAdmin):
    list_display = ['profile', 'is_main', 'is_approved', 'thumbnail_preview', 'uploaded_at']
    list_filter = ['is_main', 'is_approved', 'uploaded_at']
    search_fields = ['profile__user__email', 'profile__user__display_name']
    readonly_fields = ['thumbnail_preview', 'photo_preview', 'uploaded_at']
    
    def thumbnail_preview(self, obj):
        if obj.thumbnail_url:
            return format_html('<img src="{}" style="max-height: 50px;"/>', obj.thumbnail_url)
        return '-'
    thumbnail_preview.short_description = _('Thumbnail')
    
    def photo_preview(self, obj):
        if obj.photo_url:
            return format_html('<img src="{}" style="max-height: 200px;"/>', obj.photo_url)
        return '-'
    photo_preview.short_description = _('Photo')


@admin.register(Verification)
class VerificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'status', 'submitted_at', 'reviewed_at', 'expires_at']
    list_filter = ['status', 'submitted_at', 'expires_at']
    search_fields = ['user__email', 'user__display_name']
    readonly_fields = ['verification_code', 'created_at', 'updated_at']
    
    fieldsets = (
        (_('User'), {
            'fields': ('user', 'verification_code')
        }),
        (_('Documents'), {
            'fields': ('id_document_path', 'medical_document_path', 'selfie_path')
        }),
        (_('Status'), {
            'fields': ('status', 'rejection_reason')
        }),
        (_('Review'), {
            'fields': ('reviewed_by', 'submitted_at', 'reviewed_at', 'expires_at')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = ['approve_verification', 'reject_verification']
    
    def approve_verification(self, request, queryset):
        for verification in queryset:
            verification.status = Verification.VERIFIED
            verification.reviewed_by = request.user
            verification.reviewed_at = timezone.now()
            verification.save()
        self.message_user(request, _('Selected verifications have been approved.'))
    approve_verification.short_description = _('Approve selected verifications')
    
    def reject_verification(self, request, queryset):
        for verification in queryset:
            verification.status = Verification.REJECTED
            verification.reviewed_by = request.user
            verification.reviewed_at = timezone.now()
            verification.save()
        self.message_user(request, _('Selected verifications have been rejected.'))
    reject_verification.short_description = _('Reject selected verifications')