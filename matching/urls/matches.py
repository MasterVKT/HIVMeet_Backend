"""
Match URLs for matching app.
"""
from django.urls import path
from matching import views_matches

app_name = 'matches'

urlpatterns = [
    # Match list
    path('', views_matches.MatchListView.as_view(), name='list'),
    
    # Match management
    path('<uuid:match_id>', views_matches.unmatch_user, name='unmatch'),
]
