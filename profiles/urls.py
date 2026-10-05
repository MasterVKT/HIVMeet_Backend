"""
URLs for profiles app.
"""
from django.urls import path
from . import views
from .kyc import protect_view_with_active_kyc
from .views_premium import LikesReceivedView, SuperLikesReceivedView, PremiumFeaturesStatusView

app_name = 'profiles'

urlpatterns = [
    # Profile management
    path('geo/countries/', views.GeoCountryListView.as_view(), name='geo-countries'),
    path('geo/cities/', views.GeoCityListView.as_view(), name='geo-cities'),
    path('me/location/', views.update_profile_location_view, name='update-location'),
    path('me/complete/', views.update_profile_and_location_view, name='update-profile-and-location'),
    path('me/', views.MyProfileView.as_view(), name='my-profile'),
    path(
        '<uuid:user_id>/',
        protect_view_with_active_kyc(views.UserProfileView.as_view()),
        name='user-profile',
    ),
    
    # Photo management
    path(
        'media/photos/<uuid:photo_id>/<str:variant>/',
        views.profile_photo_media_view,
        name='profile-photo-media',
    ),
    path('me/photos/', views.upload_photo_view, name='upload-photo'),
    path('me/photos/<uuid:photo_id>/set-main/', views.set_main_photo_view, name='set-main-photo'),
    path('me/photos/reorder/', views.reorder_photos_view, name='reorder-photos'),
    path('me/photos/<uuid:photo_id>/', views.delete_photo_view, name='delete-photo'),
    
    # Premium features
    path(
        'likes-received/',
        protect_view_with_active_kyc(LikesReceivedView.as_view()),
        name='likes-received',
    ),
    path(
        'super-likes-received/',
        protect_view_with_active_kyc(SuperLikesReceivedView.as_view()),
        name='super-likes-received',
    ),
    path('premium-status/', PremiumFeaturesStatusView.as_view(), name='premium-status'),
    
    # Verification
    path('me/verification/', views.VerificationStatusView.as_view(), name='verification-status'),
    path('me/verification/start/', views.start_kyc_attempt_view, name='kyc-start'),
    path(
        'me/verification/upload-intents/',
        views.create_kyc_upload_intent_view,
        name='kyc-upload-intents',
    ),
    path(
        'me/verification/upload-intents/complete/',
        views.complete_kyc_upload_view,
        name='kyc-upload-complete',
    ),
    path('me/verification/submit/', views.submit_kyc_attempt_view, name='kyc-submit'),
    path('me/verification/generate-upload-url/', views.generate_upload_url_view, name='generate-upload-url'),
    path('me/verification/submit-documents/', views.submit_verification_documents_view, name='submit-documents'),
]
