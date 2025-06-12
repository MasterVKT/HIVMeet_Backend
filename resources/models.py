"""
Resources models for HIVMeet.
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

User = get_user_model()


class Category(models.Model):
    """
    Model for resource categories.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    name = models.CharField(
        max_length=100,
        verbose_name=_('Name')
    )
    
    name_en = models.CharField(
        max_length=100,
        verbose_name=_('Name (English)')
    )
    
    name_fr = models.CharField(
        max_length=100,
        verbose_name=_('Name (French)')
    )
    
    slug = models.SlugField(
        max_length=100,
        unique=True,
        verbose_name=_('Slug')
    )
    
    description = models.TextField(
        blank=True,
        verbose_name=_('Description')
    )
    
    description_en = models.TextField(
        blank=True,
        verbose_name=_('Description (English)')
    )
    
    description_fr = models.TextField(
        blank=True,
        verbose_name=_('Description (French)')
    )
    
    icon_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name=_('Icon URL')
    )
    
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories',
        verbose_name=_('Parent category')
    )
    
    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Display order')
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is active')
    )
    
    is_premium_only = models.BooleanField(
        default=False,
        verbose_name=_('Premium only')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at')
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated at')
    )
    
    class Meta:
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')
        db_table = 'resource_categories'
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name_en or self.name)
        super().save(*args, **kwargs)
    
    def get_name(self, language='fr'):
        """Get localized name."""
        if language == 'en':
            return self.name_en or self.name
        return self.name_fr or self.name
    
    def get_description(self, language='fr'):
        """Get localized description."""
        if language == 'en':
            return self.description_en or self.description
        return self.description_fr or self.description


class Resource(models.Model):
    """
    Model for informational resources.
    """
    
    # Resource types
    ARTICLE = 'article'
    VIDEO = 'video'
    LINK = 'link'
    CONTACT = 'contact'
    
    RESOURCE_TYPE_CHOICES = [
        (ARTICLE, _('Article')),
        (VIDEO, _('Video')),
        (LINK, _('External link')),
        (CONTACT, _('Contact/Organization')),
    ]
    
    # Languages
    FR = 'fr'
    EN = 'en'
    
    LANGUAGE_CHOICES = [
        (FR, _('French')),
        (EN, _('English')),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # Basic information
    title = models.CharField(
        max_length=200,
        verbose_name=_('Title')
    )
    
    title_en = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('Title (English)')
    )
    
    title_fr = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('Title (French)')
    )
    
    slug = models.SlugField(
        max_length=200,
        unique=True,
        verbose_name=_('Slug')
    )
    
    resource_type = models.CharField(
        max_length=10,
        choices=RESOURCE_TYPE_CHOICES,
        verbose_name=_('Resource type')
    )
    
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='resources',
        verbose_name=_('Category')
    )
    
    # Content
    content = models.TextField(
        blank=True,
        verbose_name=_('Content')
    )
    
    content_en = models.TextField(
        blank=True,
        verbose_name=_('Content (English)')
    )
    
    content_fr = models.TextField(
        blank=True,
        verbose_name=_('Content (French)')
    )
    
    summary = models.TextField(
        max_length=500,
        blank=True,
        verbose_name=_('Summary')
    )
    
    summary_en = models.TextField(
        max_length=500,
        blank=True,
        verbose_name=_('Summary (English)')
    )
    
    summary_fr = models.TextField(
        max_length=500,
        blank=True,
        verbose_name=_('Summary (French)')
    )
    
    # Media
    thumbnail_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name=_('Thumbnail URL')
    )
    
    main_image_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name=_('Main image URL')
    )
    
    external_link = models.URLField(
        max_length=500,
        blank=True,
        verbose_name=_('External link')
    )
    
    video_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name=_('Video URL')
    )
    
    # Metadata
    tags = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Tags')
    )
    
    author_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Author name')
    )
    
    source_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Source name')
    )
    
    language = models.CharField(
        max_length=2,
        choices=LANGUAGE_CHOICES,
        default=FR,
        verbose_name=_('Primary language')
    )
    
    available_languages = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Available languages')
    )
    
    # Status
    is_published = models.BooleanField(
        default=False,
        verbose_name=_('Is published')
    )
    
    is_featured = models.BooleanField(
        default=False,
        verbose_name=_('Is featured')
    )
    
    is_premium = models.BooleanField(
        default=False,
        verbose_name=_('Premium only')
    )
    
    is_verified_expert = models.BooleanField(
        default=False,
        verbose_name=_('Verified by expert')
    )
    
    # Dates
    publication_date = models.DateField(
        default=timezone.now,
        verbose_name=_('Publication date')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at')
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated at')
    )
    
    # Statistics
    view_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_('View count')
    )
    
    # Reading time (in minutes)
    estimated_read_time = models.PositiveIntegerField(
        default=5,
        verbose_name=_('Estimated read time (minutes)')
    )
    
    # Contact specific fields (stored in JSON)
    contact_info = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Contact information')
    )
    
    class Meta:
        verbose_name = _('Resource')
        verbose_name_plural = _('Resources')
        db_table = 'resources'
        ordering = ['-publication_date', '-created_at']
        indexes = [
            models.Index(fields=['resource_type', 'is_published']),
            models.Index(fields=['category', 'is_published']),
            models.Index(fields=['is_featured', '-publication_date']),
            models.Index(fields=['tags']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title_en or self.title)
        
        # Update available languages
        languages = [self.language]
        if self.title_en and self.content_en:
            languages.append('en')
        if self.title_fr and self.content_fr:
            languages.append('fr')
        self.available_languages = list(set(languages))
        
        super().save(*args, **kwargs)
    
    def get_title(self, language='fr'):
        """Get localized title."""
        if language == 'en':
            return self.title_en or self.title
        return self.title_fr or self.title
    
    def get_content(self, language='fr'):
        """Get localized content."""
        if language == 'en':
            return self.content_en or self.content
        return self.content_fr or self.content
    
    def get_summary(self, language='fr'):
        """Get localized summary."""
        if language == 'en':
            return self.summary_en or self.summary
        return self.summary_fr or self.summary
    
    def increment_views(self):
        """Increment view count."""
        self.view_count += 1
        self.save(update_fields=['view_count'])


class ResourceFavorite(models.Model):
    """
    Model for user's favorite resources.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='resource_favorites',
        verbose_name=_('User')
    )
    
    resource = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name='favorited_by',
        verbose_name=_('Resource')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at')
    )
    
    class Meta:
        verbose_name = _('Resource Favorite')
        verbose_name_plural = _('Resource Favorites')
        db_table = 'resource_favorites'
        unique_together = ['user', 'resource']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.display_name} - {self.resource.title}"


class FeedPost(models.Model):
    """
    Model for community feed posts.
    """
    
    # Post statuses
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    
    STATUS_CHOICES = [
        (PENDING, _('Pending moderation')),
        (APPROVED, _('Approved')),
        (REJECTED, _('Rejected')),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='feed_posts',
        verbose_name=_('Author')
    )
    
    content = models.TextField(
        max_length=500,
        verbose_name=_('Content')
    )
    
    image_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name=_('Image URL')
    )
    
    tags = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Tags')
    )
    
    allow_comments = models.BooleanField(
        default=True,
        verbose_name=_('Allow comments')
    )
    
    # Moderation
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=PENDING,
        verbose_name=_('Status')
    )
    
    moderated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posts_moderated',
        verbose_name=_('Moderated by')
    )
    
    moderation_notes = models.TextField(
        blank=True,
        verbose_name=_('Moderation notes')
    )
    
    moderated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Moderated at')
    )
    
    # Statistics
    like_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Like count')
    )
    
    comment_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Comment count')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at')
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated at')
    )
    
    class Meta:
        verbose_name = _('Feed Post')
        verbose_name_plural = _('Feed Posts')
        db_table = 'feed_posts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['author', 'status']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['tags']),
        ]
    
    def __str__(self):
        return f"Post by {self.author.display_name} - {self.created_at}"


class FeedPostLike(models.Model):
    """
    Model for feed post likes.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    post = models.ForeignKey(
        FeedPost,
        on_delete=models.CASCADE,
        related_name='likes',
        verbose_name=_('Post')
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='feed_likes',
        verbose_name=_('User')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at')
    )
    
    class Meta:
        verbose_name = _('Feed Post Like')
        verbose_name_plural = _('Feed Post Likes')
        db_table = 'feed_post_likes'
        unique_together = ['post', 'user']
    
    def __str__(self):
        return f"{self.user.display_name} likes {self.post.id}"


class FeedPostComment(models.Model):
    """
    Model for feed post comments.
    """
    
    # Comment statuses
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    
    STATUS_CHOICES = [
        (PENDING, _('Pending moderation')),
        (APPROVED, _('Approved')),
        (REJECTED, _('Rejected')),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    post = models.ForeignKey(
        FeedPost,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name=_('Post')
    )
    
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='feed_comments',
        verbose_name=_('Author')
    )
    
    content = models.TextField(
        max_length=200,
        verbose_name=_('Content')
    )
    
    # Moderation
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=APPROVED,  # Auto-approve by default
        verbose_name=_('Status')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at')
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated at')
    )
    
    class Meta:
        verbose_name = _('Feed Post Comment')
        verbose_name_plural = _('Feed Post Comments')
        db_table = 'feed_post_comments'
        ordering = ['created_at']
    
    def __str__(self):
        return f"Comment by {self.author.display_name} on {self.post.id}"