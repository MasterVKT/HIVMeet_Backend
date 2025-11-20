from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Custom admin for User model with premium features."""
    
    list_display = [
        'email', 'display_name', 'premium_badge', 'is_verified', 
        'is_active', 'date_joined'
    ]
    list_filter = [
        'is_premium', 'is_verified', 'is_active', 'is_staff', 
        'verification_status', 'date_joined'
    ]
    search_fields = ['email', 'display_name']
    ordering = ['-date_joined']
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {
            'fields': ('display_name', 'birth_date', 'phone_number', 'firebase_uid')
        }),
        (_('Premium status'), {
            'fields': ('is_premium', 'premium_until'),
            'classes': ('collapse',)
        }),
        (_('Verification'), {
            'fields': ('is_verified', 'verification_status', 'email_verified'),
            'classes': ('collapse',)
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        (_('Important dates'), {
            'fields': ('last_login', 'date_joined', 'last_active'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'display_name', 'birth_date', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ['date_joined', 'last_login', 'last_active', 'firebase_uid']
    
    def premium_badge(self, obj):
        """Display premium badge in admin list."""
        if obj.is_premium:
            return format_html(
                '<span style="background: gold; color: black; padding: 2px 6px; '
                'border-radius: 3px; font-weight: bold;">PREMIUM</span>'
            )
        return '-'
    premium_badge.short_description = _('Premium Status')
    premium_badge.admin_order_field = 'is_premium'
