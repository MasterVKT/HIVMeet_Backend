"""
URLs for matching app with premium features.
"""
from django.urls import path, include
from . import views
from .views_premium import RewindLastSwipeView, SendSuperLikeView, ProfileBoostView

app_name = 'matching'

urlpatterns = [
    # Discovery endpoints
    path('discovery/', views.RecommendedProfilesView.as_view(), name='discovery'),
    
    # Discovery with separate URL configuration
    path('discovery/', include('matching.urls_discovery')),
    
    # Interaction history endpoints
    path('discovery/interactions/', include('matching.urls_history')),
    
    # Like/Match endpoints
    path('like/', views.SendLikeView.as_view(), name='send_like'),
    path('<uuid:user_id>/super-like/', SendSuperLikeView.as_view(), name='send_super_like'),
    
    # Premium features
    path('rewind/', RewindLastSwipeView.as_view(), name='rewind'),
    path('boost/', ProfileBoostView.as_view(), name='boost'),
    path('likes-received/', views.WhoLikedMeView.as_view(), name='likes_received'),
    
    # Matches
    path('', views.get_matches, name='matches'),
]
