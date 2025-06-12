"""
URLs for resources app.
"""
from django.urls import path
from . import views

app_name = 'resources'

urlpatterns = [
    # Categories
    path('resource-categories', views.CategoryListView.as_view(), name='category-list'),
    
    # Resources
    path('resources', views.get_resources, name='resource-list'),
    path('resources/<uuid:resource_id>', views.get_resource_detail, name='resource-detail'),
    path('resources/<uuid:resource_id>/favorite', views.toggle_resource_favorite, name='toggle-favorite'),
    
    # Favorites
    path('favorites', views.get_favorite_resources, name='favorite-list'),
]