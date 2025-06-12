"""
Views for resources app.
"""
from django.db.models import Q
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import translation
from django.db.models import Count
import logging

from .models import Resource, Category, FeedPost, FeedPostComment
from .services import ResourceService, FeedService
from .serializers import (
    CategorySerializer,
    ResourceListSerializer,
    ResourceDetailSerializer,
    FeedPostSerializer,
    FeedPostCreateSerializer,
    FeedCommentSerializer,
    FeedCommentCreateSerializer
)

logger = logging.getLogger('hivmeet.resources')
User = get_user_model()


class CategoryListView(generics.ListAPIView):
    """
    Get list of resource categories.
    
    GET /api/v1/content/resource-categories
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CategorySerializer
    
    def get_queryset(self):
        """Get active categories with resource count."""
        user = self.request.user
        
        queryset = Category.objects.filter(
            is_active=True
        ).annotate(
            resource_count=Count('resources', filter=Q(
                resources__is_published=True
            ))
        ).order_by('order', 'name')
        
        # Filter premium categories for non-premium users
        if not user.is_premium:
            queryset = queryset.filter(is_premium_only=False)
        
        return queryset
    
    def get_serializer_context(self):
        """Add language to context."""
        context = super().get_serializer_context()
        context['language'] = self.request.GET.get('lang', translation.get_language())
        return context


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_resources(request):
    """
    Get list of resources with filters.
    
    GET /api/v1/content/resources
    """
    # Get query parameters
    category_id = request.GET.get('category_id')
    resource_type = request.GET.get('type')
    tags = request.GET.getlist('tags')
    search_query = request.GET.get('search_query')
    language = request.GET.get('language', translation.get_language())
    is_featured = request.GET.get('is_featured')
    
    # Pagination
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    offset = (page - 1) * page_size
    
    # Convert is_featured to boolean
    if is_featured is not None:
        is_featured = is_featured.lower() == 'true'
    
    # Get resources
    resources = ResourceService.get_resources(
        user=request.user,
        category_id=category_id,
        resource_type=resource_type,
        tags=tags,
        search_query=search_query,
        language=language,
        is_featured=is_featured,
        limit=page_size,
        offset=offset
    )
    
    # Serialize
    serializer = ResourceListSerializer(
        resources,
        many=True,
        context={'request': request, 'language': language}
    )
    
    # Build response
    return Response({
        'count': len(resources),  # Would need total count for proper pagination
        'next': f"?page={page + 1}" if len(resources) == page_size else None,
        'previous': f"?page={page - 1}" if page > 1 else None,
        'results': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_resource_detail(request, resource_id):
    """
    Get detailed resource information.
    
    GET /api/v1/content/resources/{resource_id}
    """
    language = request.GET.get('language', translation.get_language())
    
    # Get resource
    resource = ResourceService.get_resource_detail(resource_id, request.user)
    
    if not resource:
        return Response({
            'error': True,
            'message': _('Resource not found or access denied.')
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Serialize
    serializer = ResourceDetailSerializer(
        resource,
        context={'request': request, 'language': language}
    )
    
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def toggle_resource_favorite(request, resource_id):
    """
    Add or remove resource from favorites.
    
    POST /api/v1/content/resources/{resource_id}/favorite
    DELETE /api/v1/content/resources/{resource_id}/favorite
    """
    success, is_favorite = ResourceService.toggle_favorite(
        user=request.user,
        resource_id=resource_id
    )
    
    if not success:
        return Response({
            'error': True,
            'message': _('Resource not found or access denied.')
        }, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'POST' and is_favorite:
        return Response({
            'status': 'favorited'
        }, status=status.HTTP_201_CREATED)
    else:
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_favorite_resources(request):
    """
    Get user's favorite resources.
    
    GET /api/v1/content/favorites
    """
    # Get query parameters
    resource_type = request.GET.get('type')
    language = request.GET.get('language', translation.get_language())
    
    # Pagination
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    offset = (page - 1) * page_size
    
    # Get favorites
    favorites = ResourceService.get_user_favorites(
        user=request.user,
        resource_type=resource_type,
        limit=page_size,
        offset=offset
    )
    
    # Serialize
    serializer = ResourceListSerializer(
        favorites,
        many=True,
        context={'request': request, 'language': language}
    )
    
    # Build response
    return Response({
        'count': len(favorites),
        'next': f"?page={page + 1}" if len(favorites) == page_size else None,
        'previous': f"?page={page - 1}" if page > 1 else None,
        'results': serializer.data
    }, status=status.HTTP_200_OK)


# Feed views

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def create_feed_post(request):
    """
    Create a new feed post.
    
    POST /api/v1/feed/posts
    """
    serializer = FeedPostCreateSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Create post
    post, error_msg = FeedService.create_post(
        author=request.user,
        content=serializer.validated_data['content'],
        image_url=serializer.validated_data.get('image_url'),
        tags=serializer.validated_data.get('tags'),
        allow_comments=serializer.validated_data.get('allow_comments', True)
    )
    
    if not post:
        return Response({
            'error': True,
            'message': error_msg
        }, status=status.HTTP_403_FORBIDDEN)
    
    return Response({
        'post_id': str(post.id),
        'status': post.status,
        'message': _('Post submitted for moderation.')
    }, status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_feed_posts(request):
    """
    Get feed posts.
    
    GET /api/v1/feed/posts
    """
    # Get query parameters
    tag = request.GET.get('tag')
    sort = request.GET.get('sort', 'recent')
    
    # Pagination
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    offset = (page - 1) * page_size
    
    # Get posts
    posts = FeedService.get_feed_posts(
        user=request.user,
        tag=tag,
        sort=sort,
        limit=page_size,
        offset=offset
    )
    
    # Serialize
    serializer = FeedPostSerializer(posts, many=True)
    
    # Build response
    return Response({
        'count': len(posts),
        'next': f"?page={page + 1}" if len(posts) == page_size else None,
        'previous': f"?page={page - 1}" if page > 1 else None,
        'results': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def toggle_post_like(request, post_id):
    """
    Like or unlike a feed post.
    
    POST /api/v1/feed/posts/{post_id}/like
    """
    success, like_count = FeedService.toggle_post_like(
        user=request.user,
        post_id=post_id
    )
    
    if not success:
        return Response({
            'error': True,
            'message': _('Post not found.')
        }, status=status.HTTP_404_NOT_FOUND)
    
    return Response({
        'post_id': post_id,
        'like_count': like_count,
        'is_liked_by_me': True  # This would need proper implementation
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def add_comment(request, post_id):
    """
    Add a comment to a feed post.
    
    POST /api/v1/feed/posts/{post_id}/comments
    """
    serializer = FeedCommentCreateSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Add comment
    comment, error_msg = FeedService.add_comment(
        user=request.user,
        post_id=post_id,
        content=serializer.validated_data['content']
    )
    
    if not comment:
        return Response({
            'error': True,
            'message': error_msg
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Serialize
    response_serializer = FeedCommentSerializer(comment)
    
    return Response(response_serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_post_comments(request, post_id):
    """
    Get comments for a feed post.
    
    GET /api/v1/feed/posts/{post_id}/comments
    """
    # Pagination
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    offset = (page - 1) * page_size
    
    # Get comments
    comments = FeedService.get_post_comments(
        post_id=post_id,
        limit=page_size,
        offset=offset
    )
    
    # Serialize
    serializer = FeedCommentSerializer(comments, many=True)
    
    # Build response
    return Response({
        'count': len(comments),
        'next': f"?page={page + 1}" if len(comments) == page_size else None,
        'previous': f"?page={page - 1}" if page > 1 else None,
        'results': serializer.data
    }, status=status.HTTP_200_OK)