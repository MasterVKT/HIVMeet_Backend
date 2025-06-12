"""
API URL configuration for HIVMeet backend.
"""
from django.urls import path, include

app_name = 'api'

urlpatterns = [
    # Authentication endpoints
    path('auth/', include('authentication.urls')),
    
    # User profiles endpoints
    path('user-profiles/', include('profiles.urls')),
    
    # Discovery and matching endpoints
    path('discovery/', include('matching.urls.discovery')),
    path('matches/', include('matching.urls.matches')),
    
    # Messaging endpoints
    path('conversations/', include('messaging.urls')),
    path('calls/', include('messaging.urls_calls')),
    # Content and resources endpoints
    path('content/', include('resources.urls')),
    path('feed/', include('resources.urls_feed')),
    # Subscription endpoints
    # path('subscriptions/', include('subscriptions.urls')),
      # User settings endpoints
    path('user-settings/', include('profiles.urls_settings')),
    
    # Reporting endpoints
    # path('reports/', include('moderation.urls')),
]