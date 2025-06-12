"""
Matching models for HIVMeet.
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models import Q
import uuid
from datetime import timedelta

User = get_user_model()


class Like(models.Model):
    """
    Model for tracking likes between users.
    """
    
    # Like types
    REGULAR = 'regular'
    SUPER = 'super'
    
    LIKE_TYPE_CHOICES = [
        (REGULAR, _('Regular like')),
        (SUPER, _('Super like')),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # Who liked
    from_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='likes_sent',
        verbose_name=_('From user')
    )
    
    # Who was liked
    to_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='likes_received',
        verbose_name=_('To user')
    )
    
    # Type of like
    like_type = models.CharField(
        max_length=10,
        choices=LIKE_TYPE_CHOICES,
        default=REGULAR,
        verbose_name=_('Like type')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at')
    )
    
    class Meta:
        verbose_name = _('Like')
        verbose_name_plural = _('Likes')
        db_table = 'likes'
        unique_together = ['from_user', 'to_user']
        indexes = [
            models.Index(fields=['from_user', 'created_at']),
            models.Index(fields=['to_user', 'created_at']),
            models.Index(fields=['like_type']),
        ]
    
    def __str__(self):
        return f"{self.from_user.display_name} -> {self.to_user.display_name}"


class Dislike(models.Model):
    """
    Model for tracking dislikes (passes) between users.
    Stored temporarily for preventing re-appearance.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    from_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='dislikes_sent',
        verbose_name=_('From user')
    )
    
    to_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='dislikes_received',
        verbose_name=_('To user')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at')
    )
    
    # Auto-expire after 30 days
    expires_at = models.DateTimeField(
        verbose_name=_('Expires at')
    )
    
    class Meta:
        verbose_name = _('Dislike')
        verbose_name_plural = _('Dislikes')
        db_table = 'dislikes'
        unique_together = ['from_user', 'to_user']
        indexes = [
            models.Index(fields=['from_user', 'expires_at']),
            models.Index(fields=['expires_at']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=30)
        super().save(*args, **kwargs)


class Match(models.Model):
    """
    Model for tracking matches between users.
    """
    
    # Match statuses
    ACTIVE = 'active'
    BLOCKED = 'blocked'
    DELETED = 'deleted'
    
    STATUS_CHOICES = [
        (ACTIVE, _('Active')),
        (BLOCKED, _('Blocked')),
        (DELETED, _('Deleted')),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # The two users in the match
    user1 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='matches_as_user1',
        verbose_name=_('User 1')
    )
    
    user2 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='matches_as_user2',
        verbose_name=_('User 2')
    )
    
    # Match status
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=ACTIVE,
        verbose_name=_('Status')
    )
    
    # Messaging info
    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Last message at')
    )
    
    last_message_preview = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Last message preview')
    )
    
    # Unread counts for each user
    user1_unread_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_('User 1 unread count')
    )
    
    user2_unread_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_('User 2 unread count')
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
        verbose_name = _('Match')
        verbose_name_plural = _('Matches')
        db_table = 'matches'
        unique_together = ['user1', 'user2']
        indexes = [
            models.Index(fields=['user1', 'status', '-last_message_at']),
            models.Index(fields=['user2', 'status', '-last_message_at']),
            models.Index(fields=['status', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user1.display_name} <-> {self.user2.display_name}"
    
    def get_other_user(self, user):
        """Get the other user in the match."""
        return self.user2 if user == self.user1 else self.user1
    
    def get_unread_count(self, user):
        """Get unread count for a specific user."""
        return self.user1_unread_count if user == self.user1 else self.user2_unread_count
    
    def increment_unread(self, for_user):
        """Increment unread count for a user."""
        if for_user == self.user1:
            self.user1_unread_count += 1
        else:
            self.user2_unread_count += 1
        self.save(update_fields=['user1_unread_count', 'user2_unread_count'])
    
    def reset_unread(self, for_user):
        """Reset unread count for a user."""
        if for_user == self.user1:
            self.user1_unread_count = 0
        else:
            self.user2_unread_count = 0
        self.save(update_fields=['user1_unread_count', 'user2_unread_count'])
    
    @classmethod
    def get_match_between(cls, user1, user2):
        """Get match between two users if exists."""
        return cls.objects.filter(
            Q(user1=user1, user2=user2) | Q(user1=user2, user2=user1),
            status=cls.ACTIVE
        ).first()


class ProfileView(models.Model):
    """
    Model for tracking profile views.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    viewer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='profile_views_sent',
        verbose_name=_('Viewer')
    )
    
    viewed = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='profile_views_received',
        verbose_name=_('Viewed')
    )
    
    viewed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Viewed at')
    )
    
    class Meta:
        verbose_name = _('Profile View')
        verbose_name_plural = _('Profile Views')
        db_table = 'profile_views'
        indexes = [
            models.Index(fields=['viewer', '-viewed_at']),
            models.Index(fields=['viewed', '-viewed_at']),
        ]
        
    def __str__(self):
        return f"{self.viewer.display_name} viewed {self.viewed.display_name}"


class Boost(models.Model):
    """
    Model for profile boosts (premium feature).
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='boosts',
        verbose_name=_('User')
    )
    
    # Boost timing
    started_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Started at')
    )
    
    expires_at = models.DateTimeField(
        verbose_name=_('Expires at')
    )
    
    # Statistics
    views_gained = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Views gained')
    )
    
    likes_gained = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Likes gained')
    )
    
    class Meta:
        verbose_name = _('Boost')
        verbose_name_plural = _('Boosts')
        db_table = 'boosts'
        indexes = [
            models.Index(fields=['user', '-started_at']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Boost for {self.user.display_name}"
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = self.started_at + timedelta(minutes=30)
        super().save(*args, **kwargs)
    
    def is_active(self):
        """Check if boost is currently active."""
        return timezone.now() < self.expires_at


class DailyLikeLimit(models.Model):
    """
    Model for tracking daily like limits.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='daily_like_limits',
        verbose_name=_('User')
    )
    
    date = models.DateField(
        default=timezone.now,
        verbose_name=_('Date')
    )
    
    likes_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Likes count')
    )
    
    super_likes_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Super likes count')
    )
    
    rewinds_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Rewinds count')
    )
    
    class Meta:
        verbose_name = _('Daily Like Limit')
        verbose_name_plural = _('Daily Like Limits')
        db_table = 'daily_like_limits'
        unique_together = ['user', 'date']
        indexes = [
            models.Index(fields=['user', 'date']),
        ]
    
    def __str__(self):
        return f"{self.user.display_name} - {self.date}"
    
    def has_likes_remaining(self, user):
        """Check if user has regular likes remaining."""
        if user.is_premium:
            return True
        
        limit = 30 if user.is_verified else 20
        return self.likes_count < limit
    
    def has_super_likes_remaining(self):
        """Check if user has super likes remaining."""
        return self.super_likes_count < 3
    
    def has_rewinds_remaining(self):
        """Check if user has rewinds remaining."""
        return self.rewinds_count < 3