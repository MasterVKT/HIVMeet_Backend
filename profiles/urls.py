"""
URLs for profiles app.
"""
from django.urls import path
from . import views
from .views_premium import LikesReceivedView, SuperLikesReceivedView, PremiumFeaturesStatusView

app_name = 'profiles'

urlpatterns = [
    # Profile management
    path('me/', views.MyProfileView.as_view(), name='my-profile'),
    path('<uuid:user_id>/', views.UserProfileView.as_view(), name='user-profile'),
    
    # Photo management
    path('me/photos/', views.upload_photo_view, name='upload-photo'),
    path('me/photos/<uuid:photo_id>/set-main/', views.set_main_photo_view, name='set-main-photo'),
    path('me/photos/<uuid:photo_id>/', views.delete_photo_view, name='delete-photo'),
    
    # Premium features
    path('likes-received/', LikesReceivedView.as_view(), name='likes-received'),
    path('super-likes-received/', SuperLikesReceivedView.as_view(), name='super-likes-received'),
    path('premium-status/', PremiumFeaturesStatusView.as_view(), name='premium-status'),
    
    # Verification
    path('me/verification/', views.VerificationStatusView.as_view(), name='verification-status'),
    path('me/verification/generate-upload-url/', views.generate_upload_url_view, name='generate-upload-url'),
    path('me/verification/submit-documents/', views.submit_verification_documents_view, name='submit-documents'),
]