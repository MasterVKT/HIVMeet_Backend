"""
Discovery URLs for matching app.
"""
from django.urls import path
from . import views_discovery

app_name = 'discovery'

urlpatterns = [
    # Discovery profiles
    path('profiles', views_discovery.get_discovery_profiles, name='profiles'),
    
    # Filters
    path('filters', views_discovery.update_discovery_filters, name='update-filters'),
    path('filters/get', views_discovery.get_discovery_filters, name='get-filters'),
    
    # Interactions
    path('interactions/like', views_discovery.like_profile, name='like'),
    path('interactions/dislike', views_discovery.dislike_profile, name='dislike'),
    path('interactions/superlike', views_discovery.superlike_profile, name='superlike'),
    path('interactions/rewind', views_discovery.rewind_last_swipe, name='rewind'),
    path('interactions/liked-me', views_discovery.get_likes_received, name='liked-me'),
    
    # Boost
    path('boost/activate', views_discovery.activate_boost, name='activate-boost'),
]