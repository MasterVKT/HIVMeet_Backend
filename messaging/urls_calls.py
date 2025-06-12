"""
URLs for call endpoints.
"""
from django.urls import path
from . import views

app_name = 'calls'

urlpatterns = [
    # Call management
    path('initiate', views.initiate_call, name='initiate'),
    path('<uuid:call_id>/answer', views.answer_call, name='answer'),
    path('<uuid:call_id>/ice-candidate', views.add_ice_candidate, name='ice-candidate'),
    path('<uuid:call_id>/terminate', views.end_call, name='terminate'),
]