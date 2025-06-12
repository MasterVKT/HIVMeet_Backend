"""
URLs for feed functionality.
"""
from django.urls import path
from . import views

app_name = 'feed'

urlpatterns = [
    # Feed posts
    path('posts', views.create_feed_post, name='create-post'),
    path('posts', views.get_feed_posts, name='post-list'),
    path('posts/<uuid:post_id>/like', views.toggle_post_like, name='toggle-like'),
    
    # Comments
    path('posts/<uuid:post_id>/comments', views.add_comment, name='add-comment'),
    path('posts/<uuid:post_id>/comments', views.get_post_comments, name='comment-list'),
]