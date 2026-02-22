"""
URLs for interaction history.
"""
from django.urls import path
from . import views_history

app_name = 'history'

urlpatterns = [
    # History endpoints
    path('my-likes', views_history.get_my_likes, name='my-likes'),
    path('my-passes', views_history.get_my_passes, name='my-passes'),
    path('<uuid:interaction_id>/revoke', views_history.revoke_interaction, name='revoke'),
    path('stats', views_history.get_interaction_stats, name='stats'),
]
