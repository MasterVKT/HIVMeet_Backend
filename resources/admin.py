"""
Admin configuration for resources app.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import Category, Resource, ResourceFavorite, FeedPost, FeedPostLike, FeedPostComment


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'order', 'is_active', 'is_premium_only']
    list_filter = ['is_active', 'is_premium_only', 'parent']
    search_fields = ['name', 'name_en', 'name_fr', 'slug']
    prepopulated_fields = {'slug': ('name_en',)}
    ordering = ['order', 'name']
    
    fieldsets = (
        (_('Names'), {
            'fields': ('name', 'name_en', 'name_fr', 'slug')
        }),
        (_('Descriptions'), {
            'fields': ('description', 'description_en', 'description_fr')
        }),
        (_('Settings'), {
            'fields': ('parent', 'icon_url', 'order', 'is_active', 'is_premium_only')
        }),
    )


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ['title', 'resource_type', 'category', 'is_published', 'is_featured', 'is_premium', 'publication_date']
    list_filter = ['resource_type', 'is_published', 'is_featured', 'is_premium', 'is_verified_expert', 'language']
    search_fields = ['title', 'title_en', 'title_fr', 'content', 'tags']
    prepopulated_fields = {'slug': ('title_en',)}
    date_hierarchy = 'publication_date'
    readonly_fields = ['view_count', 'created_at', 'updated_at']
    
    fieldsets = (
        (_('Titles'), {
            'fields': ('title', 'title_en', 'title_fr', 'slug')
        }),
        (_('Content'), {
            'fields': ('summary', 'summary_en', 'summary_fr', 'content', 'content_en', 'content_fr')
        }),
        (_('Metadata'), {
            'fields': ('resource_type', 'category', 'tags', 'author_name', 'source_name', 
                      'language', 'available_languages', 'estimated_read_time')
        }),
        (_('Media'), {
            'fields': ('thumbnail_url', 'main_image_url', 'external_link', 'video_url')
        }),
        (_('Status'), {
            'fields': ('is_published', 'is_featured', 'is_premium', 'is_verified_expert', 'publication_date')
        }),
        (_('Contact Info'), {
            'fields': ('contact_info',),
            'classes': ('collapse',)
        }),
        (_('Statistics'), {
            'fields': ('view_count', 'created_at', 'updated_at')
        }),
    )
    
    actions = ['publish_resources', 'unpublish_resources', 'mark_as_featured']
    
    def publish_resources(self, request, queryset):
        queryset.update(is_published=True)
        self.message_user(request, _('Selected resources have been published.'))
    publish_resources.short_description = _('Publish selected resources')
    
    def unpublish_resources(self, request, queryset):
        queryset.update(is_published=False)
        self.message_user(request, _('Selected resources have been unpublished.'))
    unpublish_resources.short_description = _('Unpublish selected resources')
    
    def mark_as_featured(self, request, queryset):
        queryset.update(is_featured=True)
        self.message_user(request, _('Selected resources have been marked as featured.'))
    mark_as_featured.short_description = _('Mark as featured')


@admin.register(FeedPost)
class FeedPostAdmin(admin.ModelAdmin):
    list_display = ['author', 'content_preview', 'status', 'like_count', 'comment_count', 'created_at']
    list_filter = ['status', 'created_at', 'allow_comments']
    search_fields = ['author__email', 'author__display_name', 'content', 'tags']
    date_hierarchy = 'created_at'
    readonly_fields = ['like_count', 'comment_count', 'created_at', 'updated_at']
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = _('Content')
    
    fieldsets = (
        (_('Post Info'), {
            'fields': ('author', 'content', 'image_url', 'tags', 'allow_comments')
        }),
        (_('Moderation'), {
            'fields': ('status', 'moderated_by', 'moderation_notes', 'moderated_at')
        }),
        (_('Statistics'), {
            'fields': ('like_count', 'comment_count', 'created_at', 'updated_at')
        }),
    )
    
    actions = ['approve_posts', 'reject_posts']
    
    def approve_posts(self, request, queryset):
        queryset.update(
            status=FeedPost.APPROVED,
            moderated_by=request.user,
            moderated_at=timezone.now()
        )
        self.message_user(request, _('Selected posts have been approved.'))
    approve_posts.short_description = _('Approve selected posts')
    
    def reject_posts(self, request, queryset):
        queryset.update(
            status=FeedPost.REJECTED,
            moderated_by=request.user,
            moderated_at=timezone.now()
        )
        self.message_user(request, _('Selected posts have been rejected.'))
    reject_posts.short_description = _('Reject selected posts')


@admin.register(FeedPostComment)
class FeedPostCommentAdmin(admin.ModelAdmin):
    list_display = ['author', 'post', 'content', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['author__email', 'author__display_name', 'content']
    date_hierarchy = 'created_at'
    
    actions = ['approve_comments', 'reject_comments']
    
    def approve_comments(self, request, queryset):
        queryset.update(status=FeedPostComment.APPROVED)
        self.message_user(request, _('Selected comments have been approved.'))
    approve_comments.short_description = _('Approve selected comments')
    
    def reject_comments(self, request, queryset):
        queryset.update(status=FeedPostComment.REJECTED)
        self.message_user(request, _('Selected comments have been rejected.'))
    reject_comments.short_description = _('Reject selected comments')