"""
URLs for feed functionality.
"""
from django.urls import path
from . import views

app_name = 'feed'

urlpatterns = [
    # Feed posts (GET to list, POST to create)
    path('posts', views.feed_posts_view, name='posts'),
    path('posts/<uuid:post_id>/like', views.toggle_post_like, name='toggle-like'),

    # Comments (GET to list, POST to add)
    path('posts/<uuid:post_id>/comments', views.post_comments_view, name='post-comments'),
]