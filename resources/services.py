"""
Services for resources app.
"""
from django.contrib.auth import get_user_model
from django.db.models import Q, F, Count, Exists, OuterRef
from django.utils import translation
from django.utils.translation import gettext as _
from typing import List, Optional, Tuple, TYPE_CHECKING
import logging

from .models import Resource, Category, ResourceFavorite, FeedPost, FeedPostLike, FeedPostComment

if TYPE_CHECKING:
    from authentication.models import User as UserType

logger = logging.getLogger('hivmeet.resources')
User = get_user_model()


class ResourceService:
    """
    Service for handling resources.
    """
    
    @staticmethod
    def get_resources(
        user: 'UserType',
        category_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        search_query: Optional[str] = None,
        language: Optional[str] = None,
        is_featured: Optional[bool] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Resource]:
        """
        Get resources with filters.
        """
        # Base query - only published resources
        query = Resource.objects.filter(is_published=True)
        
        # Filter premium content for non-premium users
        if not user.is_premium:
            query = query.filter(is_premium=False)
        
        # Apply filters
        if category_id:
            query = query.filter(category_id=category_id)
        
        if resource_type:
            query = query.filter(resource_type=resource_type)
        
        if tags:
            # Filter by tags (PostgreSQL JSON field)
            tag_filter = Q()
            for tag in tags:
                tag_filter |= Q(tags__contains=tag)
            query = query.filter(tag_filter)
        
        if search_query:
            # Search in title and content
            lang = language or translation.get_language()
            if lang == 'en':
                query = query.filter(
                    Q(title_en__icontains=search_query) |
                    Q(content_en__icontains=search_query) |
                    Q(summary_en__icontains=search_query)
                )
            else:
                query = query.filter(
                    Q(title_fr__icontains=search_query) |
                    Q(content_fr__icontains=search_query) |
                    Q(summary_fr__icontains=search_query) |
                    Q(title__icontains=search_query) |
                    Q(content__icontains=search_query) |
                    Q(summary__icontains=search_query)
                )
        
        if language:
            query = query.filter(available_languages__contains=language)
        
        if is_featured is not None:
            query = query.filter(is_featured=is_featured)
        
        # Order by featured first, then by publication date
        query = query.order_by('-is_featured', '-publication_date')
        
        # Add favorite annotation
        query = query.annotate(
            is_favorite=Exists(
                ResourceFavorite.objects.filter(
                    user=user,
                    resource=OuterRef('pk')
                )
            )
        )
          # Apply pagination
        resources = query[offset:offset + limit]
        
        return list(resources)
    
    @staticmethod
    def get_resource_detail(resource_id: str, user: 'UserType') -> Optional[Resource]:
        """
        Get detailed resource information.
        """
        try:
            resource = Resource.objects.annotate(
                is_favorite=Exists(
                    ResourceFavorite.objects.filter(
                        user=user,
                        resource=OuterRef('pk')
                    )
                )
            ).get(id=resource_id, is_published=True)
              # Check premium access
            if resource.is_premium and not user.is_premium:
                return None
            
            # Increment view count
            resource.increment_views()
            
            return resource
            
        except Resource.DoesNotExist:
            return None
    
    @staticmethod
    def toggle_favorite(user: 'UserType', resource_id: str) -> Tuple[bool, bool]:
        """
        Toggle favorite status for a resource.
        Returns (success, is_now_favorite).
        """
        try:
            resource = Resource.objects.get(id=resource_id, is_published=True)
              # Check premium access
            if resource.is_premium and not user.is_premium:
                return False, False
            
            favorite, created = ResourceFavorite.objects.get_or_create(
                user=user,
                resource=resource
            )
            
            if not created:
                # Already favorited, so remove it
                favorite.delete()
                return True, False
            
            return True, True
            
        except Resource.DoesNotExist:
            return False, False
    
    @staticmethod
    def get_user_favorites(
        user: 'UserType',
        resource_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Resource]:
        """
        Get user's favorite resources.
        """
        query = Resource.objects.filter(
            favorited_by__user=user,
            is_published=True
        )
        
        if resource_type:
            query = query.filter(resource_type=resource_type)
        
        # Order by when it was favorited
        query = query.annotate(
            favorited_at=F('favorited_by__created_at')
        ).order_by('-favorited_at')
        
        return list(query[offset:offset + limit])


class FeedService:
    """
    Service for handling community feed.
    """
    
    @staticmethod
    def create_post(
        author: 'UserType',
        content: str,
        image_url: Optional[str] = None,
        tags: Optional[List[str]] = None,
        allow_comments: bool = True
    ) -> Tuple[Optional[FeedPost], Optional[str]]:
        """
        Create a new feed post.
        Returns (post, error_message).
        """
        # Check if user is verified
        if not author.is_verified:
            return None, _("Only verified users can create posts.")
        
        # Create post
        try:
            post = FeedPost.objects.create(
                author=author,
                content=content,
                image_url=image_url or '',
                tags=tags or [],
                allow_comments=allow_comments,
                status=FeedPost.PENDING  # All posts go through moderation
            )            
            logger.info(f"Feed post created by {author.email}, pending moderation")
            return post, None
        except Exception as e:
            logger.error(f"Error creating feed post: {str(e)}")
            return None, _("Failed to create post. Please try again.")
    
    @staticmethod
    def get_feed_posts(
        user: 'UserType',
        tag: Optional[str] = None,
        sort: str = 'recent',
        limit: int = 20,
        offset: int = 0
    ) -> List[FeedPost]:
        """
        Get feed posts.
        """
        # Base query - only approved posts
        query = FeedPost.objects.filter(
            status=FeedPost.APPROVED
        ).select_related('author__profile')
        
        # Filter by tag
        if tag:
            query = query.filter(tags__contains=tag)
        
        # Add user interaction annotations
        query = query.annotate(
            is_liked_by_me=Exists(
                FeedPostLike.objects.filter(
                    post=OuterRef('pk'),
                    user=user
                )
            )
        )
        
        # Sorting
        if sort == 'popular':
            query = query.order_by('-like_count', '-created_at')
        else:
            query = query.order_by('-created_at')
          # Apply pagination
        posts = query[offset:offset + limit]
        
        return list(posts)
    
    @staticmethod
    def toggle_post_like(user: 'UserType', post_id: str) -> Tuple[bool, int]:
        """
        Toggle like on a post.
        Returns (success, new_like_count).        """
        try:
            post = FeedPost.objects.get(
                id=post_id,
                status=FeedPost.APPROVED
            )
            
            like, created = FeedPostLike.objects.get_or_create(
                post=post,
                user=user
            )
            
            if not created:
                # Already liked, so unlike
                like.delete()
                post.like_count = F('like_count') - 1
            else:
                # New like
                post.like_count = F('like_count') + 1
            
            post.save(update_fields=['like_count'])
            post.refresh_from_db()
            return True, post.like_count
            
        except FeedPost.DoesNotExist:
            return False, 0
    
    @staticmethod
    def add_comment(
        user: 'UserType',
        post_id: str,
        content: str
    ) -> Tuple[Optional[FeedPostComment], Optional[str]]:
        """
        Add a comment to a post.
        Returns (comment, error_message).
        """
        try:
            post = FeedPost.objects.get(
                id=post_id,
                status=FeedPost.APPROVED
            )
            
            if not post.allow_comments:
                return None, _("Comments are disabled for this post.")
            
            # Create comment
            comment = FeedPostComment.objects.create(
                post=post,
                author=user,
                content=content
            )
            
            # Update comment count
            post.comment_count = F('comment_count') + 1
            post.save(update_fields=['comment_count'])
            
            return comment, None
            
        except FeedPost.DoesNotExist:
            return None, _("Post not found.")
        except Exception as e:
            logger.error(f"Error adding comment: {str(e)}")
            return None, _("Failed to add comment.")
    
    @staticmethod
    def get_post_comments(
        post_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[FeedPostComment]:
        """
        Get comments for a post.
        """
        comments = FeedPostComment.objects.filter(
            post_id=post_id,
            status=FeedPostComment.APPROVED
        ).select_related(
            'author__profile'
        ).order_by('created_at')[offset:offset + limit]
        
        return list(comments)