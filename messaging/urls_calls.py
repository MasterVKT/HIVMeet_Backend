"""
URLs for call endpoints.
"""
from django.urls import path
from . import views
from profiles.kyc import protect_view_with_active_kyc

app_name = 'calls'

urlpatterns = [
    # Call management
    path('initiate', protect_view_with_active_kyc(views.initiate_call), name='initiate'),
    path('<uuid:call_id>/answer', protect_view_with_active_kyc(views.answer_call), name='answer'),
    path('<uuid:call_id>/ice-candidate', protect_view_with_active_kyc(views.add_ice_candidate), name='ice-candidate'),
    path('<uuid:call_id>/terminate', protect_view_with_active_kyc(views.end_call), name='terminate'),
]
