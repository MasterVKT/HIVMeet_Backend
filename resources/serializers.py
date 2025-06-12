"""
Serializers for resources app.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import translation

from .models import Resource, Category, FeedPost, FeedPostComment

User = get_user_model()


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for resource categories.
    """
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    resource_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'icon_url',
            'resource_count', 'is_premium_only'
        ]
    
    def get_name(self, obj):
        """Get localized name."""
        language = self.context.get('language', translation.get_language())
        return obj.get_name(language)
    
    def get_description(self, obj):
        """Get localized description."""
        language = self.context.get('language', translation.get_language())
        return obj.get_description(language)


class ResourceListSerializer(serializers.ModelSerializer):
    """
    Serializer for resource list view.
    """
    title = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    is_favorite = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Resource
        fields = [
            'id', 'title', 'summary', 'resource_type', 'category_name',
            'tags', 'thumbnail_url', 'publication_date', 'is_premium',
            'is_verified_expert', 'estimated_read_time', 'is_favorite'
        ]
    
    def get_title(self, obj):
        """Get localized title."""
        language = self.context.get('language', translation.get_language())
        return obj.get_title(language)
    
    def get_summary(self, obj):
        """Get localized summary."""
        language = self.context.get('language', translation.get_language())
        return obj.get_summary(language)
    
    def get_category_name(self, obj):
        """Get localized category name."""
        if obj.category:
            language = self.context.get('language', translation.get_language())
            return obj.category.get_name(language)
        return None


class ResourceDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for resource detail view.
    """
    title = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    is_favorite = serializers.BooleanField(read_only=True)
    related_resources = serializers.SerializerMethodField()
    
    class Meta:
        model = Resource
        fields = [
            'id', 'title', 'content', 'summary', 'resource_type',
            'category_name', 'tags', 'main_image_url', 'external_link',
            'video_url', 'author_name', 'source_name', 'publication_date',
            'is_premium', 'is_verified_expert', 'language',
            'available_languages', 'view_count', 'estimated_read_time',
            'is_favorite', 'contact_info', 'related_resources',
            'created_at', 'updated_at'
        ]
    
    def get_title(self, obj):
        """Get localized title."""
        language = self.context.get('language', translation.get_language())
        return obj.get_title(language)
    
    def get_content(self, obj):
        """Get localized content."""
        language = self.context.get('language', translation.get_language())
        return obj.get_content(language)
    
    def get_summary(self, obj):
        """Get localized summary."""
        language = self.context.get('language', translation.get_language())
        return obj.get_summary(language)
    
    def get_category_name(self, obj):
        """Get localized category name."""
        if obj.category:
            language = self.context.get('language', translation.get_language())
            return obj.category.get_name(language)
        return None
    
    def get_related_resources(self, obj):
        """Get related resources (same category, different resource)."""
        if not obj.category:
            return []
        
        related = Resource.objects.filter(
            category=obj.category,
            is_published=True
        ).exclude(
            id=obj.id
        ).order_by('-publication_date')[:3]
        
        return ResourceListSerializer(
            related,
            many=True,
            context=self.context
        ).data


class FeedPostAuthorSerializer(serializers.Serializer):
    """
    Serializer for feed post author info.
    """
    user_id = serializers.UUIDField(source='id')
    display_name = serializers.CharField()
    profile_photo_url = serializers.SerializerMethodField()
    is_verified = serializers.BooleanField()
    
    def get_profile_photo_url(self, obj):
        """Get profile photo URL."""
        if hasattr(obj, 'profile') and obj.profile.photos.exists():
            main_photo = obj.profile.photos.filter(is_main=True).first()
            if main_photo:
                return main_photo.thumbnail_url
        return None


class FeedPostSerializer(serializers.ModelSerializer):
    """
    Serializer for feed posts.
    """
    author = FeedPostAuthorSerializer(read_only=True)
    is_liked_by_me = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = FeedPost
        fields = [
            'id', 'author', 'content', 'image_url', 'tags',
            'allow_comments', 'like_count', 'comment_count',
            'is_liked_by_me', 'created_at'
        ]
        read_only_fields = [
            'id', 'author', 'like_count', 'comment_count',
            'is_liked_by_me', 'created_at'
        ]


class FeedPostCreateSerializer(serializers.Serializer):
    """
    Serializer for creating feed posts.
    """
    content = serializers.CharField(max_length=500)
    image_url = serializers.URLField(required=False, allow_blank=True)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        allow_empty=True
    )
    allow_comments = serializers.BooleanField(default=True)
    
    def validate_content(self, value):
        """Validate content."""
        # Basic content moderation
        prohibited_words = []  # Add prohibited words list
        content_lower = value.lower()
        
        for word in prohibited_words:
            if word in content_lower:
                raise serializers.ValidationError(
                    _("Content contains prohibited words.")
                )
        
        return value


class FeedCommentSerializer(serializers.ModelSerializer):
    """
    Serializer for feed comments.
    """
    author = FeedPostAuthorSerializer(read_only=True)
    
    class Meta:
        model = FeedPostComment
        fields = [
            'id', 'author', 'content', 'created_at'
        ]
        read_only_fields = ['id', 'author', 'created_at']


class FeedCommentCreateSerializer(serializers.Serializer):
    """
    Serializer for creating comments.
    """
    content = serializers.CharField(max_length=200)
    
    def validate_content(self, value):
        """Validate content."""
        # Basic content moderation
        if len(value.strip()) < 2:
            raise serializers.ValidationError(
                _("Comment is too short.")
            )
        return value