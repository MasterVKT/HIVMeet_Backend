"""
URLs for authentication app.
"""
from django.urls import path
from . import views

app_name = 'authentication'

urlpatterns = [
    # Registration and verification
    path('register', views.register_view, name='register'),
    path('verify-email/<str:verification_token>', views.verify_email_view, name='verify-email'),
    
    # Login and logout
    path('login', views.login_view, name='login'),
    path('logout', views.logout_view, name='logout'),
    
    # Password management
    path('forgot-password', views.forgot_password_view, name='forgot-password'),
    path('reset-password', views.reset_password_view, name='reset-password'),
    
    # Token management
    path('refresh-token', views.refresh_token_view, name='refresh-token'),
    
    # FCM token
    path('fcm-token', views.RegisterFCMTokenView.as_view(), name='fcm-token'),
]