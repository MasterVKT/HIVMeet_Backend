"""
URLs for feed functionality.
"""
from django.urls import path
from . import views
from profiles.kyc import protect_view_with_active_kyc

app_name = 'feed'

urlpatterns = [
    # Feed posts (GET to list, POST to create)
    path('posts', protect_view_with_active_kyc(views.feed_posts_view), name='posts'),
    path('posts/<uuid:post_id>/like', protect_view_with_active_kyc(views.toggle_post_like), name='toggle-like'),

    # Comments (GET to list, POST to add)
    path('posts/<uuid:post_id>/comments', protect_view_with_active_kyc(views.post_comments_view), name='post-comments'),
]
