"""
Match URLs for matching app.
"""
from django.urls import path
from . import views_matches

app_name = 'matches'

urlpatterns = [
    # Match list
    path('', views_matches.MatchListView.as_view(), name='list'),
    path('likes-received/reveal/', views_matches.reveal_received_like, name='reveal-received-like'),
    path('<uuid:match_id>/unlock-free/', views_matches.unlock_free_match, name='unlock-free'),
    
    # Match management
    path('<uuid:match_id>', views_matches.unmatch_user, name='unmatch'),
]
