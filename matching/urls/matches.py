"""
Match URLs for matching app.
"""
from django.urls import path
from matching import views_matches
from profiles.kyc import protect_view_with_active_kyc

app_name = 'matches'

urlpatterns = [
    # Match list
    path('', protect_view_with_active_kyc(views_matches.MatchListView.as_view()), name='list'),
    path('unseen-count/', protect_view_with_active_kyc(views_matches.unseen_match_count), name='unseen-count'),
    path('seen/', protect_view_with_active_kyc(views_matches.mark_matches_seen), name='mark-seen'),
    path('likes-received/reveal/', protect_view_with_active_kyc(views_matches.reveal_received_like), name='reveal-received-like'),
    path('<uuid:match_id>/unlock-free/', protect_view_with_active_kyc(views_matches.unlock_free_match), name='unlock-free'),
    
    # Match management
    path('<uuid:match_id>', protect_view_with_active_kyc(views_matches.unmatch_user), name='unmatch'),
]
