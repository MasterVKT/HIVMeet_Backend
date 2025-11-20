"""
URLs for authentication app.
"""
from django.urls import path
from . import views
from .views import FirebaseLoginView

app_name = 'authentication'

urlpatterns = [
    # Registration and verification
    path('register', views.register_view, name='register'),
    path('register/', views.register_view),  # alias avec slash
    path('verify-email/<str:verification_token>', views.verify_email_view, name='verify-email'),
    path('verify-email/<str:verification_token>/', views.verify_email_view),  # alias avec slash
    
    # Login and logout
    path('login', views.login_view, name='login'),
    path('login/', views.login_view),  # alias avec slash
    path('logout', views.logout_view, name='logout'),
    path('logout/', views.logout_view),  # alias avec slash
    
    # Firebase token exchange
    path('firebase-login/', FirebaseLoginView.as_view(), name='firebase-login'),
    path('firebase-exchange/', FirebaseLoginView.as_view(), name='firebase-exchange'),
    
    # Password management
    path('forgot-password', views.forgot_password_view, name='forgot-password'),
    path('forgot-password/', views.forgot_password_view),  # alias avec slash
    path('reset-password', views.reset_password_view, name='reset-password'),
    path('reset-password/', views.reset_password_view),  # alias avec slash
    
    # Token management
    path('refresh-token/', views.refresh_token_view, name='refresh-token'),
    path('refresh-token', views.refresh_token_view),  # alias sans slash
    
    # FCM token
    path('fcm-token', views.RegisterFCMTokenView.as_view(), name='fcm-token'),
    path('fcm-token/', views.RegisterFCMTokenView.as_view()),  # alias avec slash
]