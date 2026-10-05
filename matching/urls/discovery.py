"""
Discovery URLs for matching app.
"""
from django.urls import path
from matching import views_discovery, views_history
from profiles.kyc import protect_view_with_active_kyc

app_name = 'discovery'

urlpatterns = [
    # Discovery profiles - endpoint principal pour le frontend
    path('', protect_view_with_active_kyc(views_discovery.get_discovery_profiles), name='discovery'),
    # Discovery profiles - alias pour compatibilité
    path('profiles', protect_view_with_active_kyc(views_discovery.get_discovery_profiles), name='profiles'),
    
    # Discovery filters
    path('filters', protect_view_with_active_kyc(views_discovery.update_discovery_filters), name='update-filters'),
    path('filters/get', protect_view_with_active_kyc(views_discovery.get_discovery_filters), name='get-filters'),
    # Conserver un alias legacy éventuel pour stabilité (optionnel)
    # path('list', views_discovery.get_discovery_profiles, name='list'),
    
    # Interactions
    path('interactions/like', protect_view_with_active_kyc(views_discovery.like_profile), name='like'),
    path('interactions/dislike', protect_view_with_active_kyc(views_discovery.dislike_profile), name='dislike'),
    path('interactions/superlike', protect_view_with_active_kyc(views_discovery.superlike_profile), name='superlike'),
    path('interactions/super-like', protect_view_with_active_kyc(views_discovery.superlike_profile), name='super-like'),
    path('interactions/<uuid:interaction_id>/rewind/', protect_view_with_active_kyc(views_discovery.rewind_interaction), name='rewind-interaction'),
    path('interactions/rewind', protect_view_with_active_kyc(views_discovery.rewind_last_swipe), name='rewind'),
    path('interactions/liked-me', protect_view_with_active_kyc(views_discovery.get_likes_received), name='liked-me'),
    path('interactions/status', protect_view_with_active_kyc(views_discovery.get_interaction_status), name='interaction-status'),
    
    # Interaction history
    path('interactions/my-likes', protect_view_with_active_kyc(views_history.get_my_likes), name='my-likes'),
    path('interactions/my-passes', protect_view_with_active_kyc(views_history.get_my_passes), name='my-passes'),
    path('interactions/revoke-bulk', protect_view_with_active_kyc(views_history.revoke_interactions_bulk), name='revoke-bulk'),
    path('interactions/<uuid:interaction_id>/revoke', protect_view_with_active_kyc(views_history.revoke_interaction), name='revoke'),
    path('interactions/stats', protect_view_with_active_kyc(views_history.get_interaction_stats), name='stats'),
    
    # Boost
    path('boost/activate', protect_view_with_active_kyc(views_discovery.activate_boost), name='activate-boost'),
]
