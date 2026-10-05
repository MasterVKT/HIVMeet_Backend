"""
URLs for user settings.
"""
from django.urls import path
from . import views_settings
from .kyc import protect_view_with_active_kyc

app_name = 'user_settings'

urlpatterns = [
    # Notification preferences
    path('notification-preferences', views_settings.NotificationPreferencesView.as_view(), name='notification-preferences'),
    
    # Privacy preferences
    path('privacy-preferences', views_settings.PrivacyPreferencesView.as_view(), name='privacy-preferences'),
    
    # Blocked users
    path(
        'blocks',
        protect_view_with_active_kyc(views_settings.BlockedUsersListView.as_view()),
        name='blocked-users-list',
    ),
    path(
        'blocks/<uuid:user_id>',
        protect_view_with_active_kyc(views_settings.block_unblock_user_view),
        name='block-unblock-user',
    ),
    
    # Account management
    path('delete-account', views_settings.delete_account_view, name='delete-account'),
    path('export-data', views_settings.export_data_view, name='export-data'),
]
