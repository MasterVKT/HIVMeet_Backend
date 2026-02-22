"""
Discovery URLs for matching app.
"""
from django.urls import path
from matching import views_discovery, views_history

app_name = 'discovery'

urlpatterns = [
    # Discovery profiles - endpoint principal pour le frontend
    path('', views_discovery.get_discovery_profiles, name='discovery'),
    # Discovery profiles - alias pour compatibilité
    path('profiles', views_discovery.get_discovery_profiles, name='profiles'),
    # Conserver un alias legacy éventuel pour stabilité (optionnel)
    # path('list', views_discovery.get_discovery_profiles, name='list'),
    
    # Interactions
    path('interactions/like', views_discovery.like_profile, name='like'),
    path('interactions/dislike', views_discovery.dislike_profile, name='dislike'),
    path('interactions/superlike', views_discovery.superlike_profile, name='superlike'),
    path('interactions/rewind', views_discovery.rewind_last_swipe, name='rewind'),
    path('interactions/liked-me', views_discovery.get_likes_received, name='liked-me'),
    
    # Interaction history
    path('interactions/my-likes', views_history.get_my_likes, name='my-likes'),
    path('interactions/my-passes', views_history.get_my_passes, name='my-passes'),
    path('interactions/<uuid:interaction_id>/revoke', views_history.revoke_interaction, name='revoke'),
    path('interactions/stats', views_history.get_interaction_stats, name='stats'),
    
    # Boost
    path('boost/activate', views_discovery.activate_boost, name='activate-boost'),
]
