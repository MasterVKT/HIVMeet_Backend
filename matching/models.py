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


class InteractionHistory(models.Model):
    """
    Model for tracking complete history of user interactions (likes and dislikes).
    Allows users to review their past interactions and revoke them if needed.
    """
    
    # Interaction types
    LIKE = 'like'
    SUPER_LIKE = 'super_like'
    DISLIKE = 'dislike'
    
    INTERACTION_TYPE_CHOICES = [
        (LIKE, _('Like')),
        (SUPER_LIKE, _('Super like')),
        (DISLIKE, _('Dislike/Pass')),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # Who performed the interaction
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='interactions_sent',
        verbose_name=_('User')
    )
    
    # Target of the interaction
    target_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='interactions_received',
        verbose_name=_('Target user')
    )
    
    # Type of interaction
    interaction_type = models.CharField(
        max_length=20,
        choices=INTERACTION_TYPE_CHOICES,
        verbose_name=_('Interaction type')
    )
    
    # Revocation status
    is_revoked = models.BooleanField(
        default=False,
        verbose_name=_('Is revoked'),
        help_text=_('Whether this interaction has been cancelled by the user')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at')
    )
    
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Revoked at')
    )
    
    class Meta:
        verbose_name = _('Interaction History')
        verbose_name_plural = _('Interaction Histories')
        db_table = 'interaction_history'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['target_user', '-created_at']),
            models.Index(fields=['interaction_type']),
            models.Index(fields=['user', 'is_revoked'], name='idx_ih_user_revoked'),
            models.Index(fields=['user', 'interaction_type', 'is_revoked'], name='idx_ih_user_type_revoked'),
        ]
        # Ensure unique active interaction per user-target-type combination
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'target_user', 'interaction_type'],
                condition=Q(is_revoked=False),
                name='unique_active_interaction'
            )
        ]
    
    def __str__(self):
        status = "revoked" if self.is_revoked else "active"
        return f"{self.user.display_name} {self.interaction_type} {self.target_user.display_name} ({status})"
    
    def revoke(self):
        """Revoke this interaction."""
        if not self.is_revoked:
            self.is_revoked = True
            self.revoked_at = timezone.now()
            self.save(update_fields=['is_revoked', 'revoked_at'])
    
    @classmethod
    def get_user_likes(cls, user, include_revoked=False):
        """Get all likes sent by a user."""
        queryset = cls.objects.filter(
            user=user,
            interaction_type__in=[cls.LIKE, cls.SUPER_LIKE]
        )
        if not include_revoked:
            queryset = queryset.filter(is_revoked=False)
        return queryset.select_related('target_user__profile').prefetch_related('target_user__profile__photos')
    
    @classmethod
    def get_user_passes(cls, user, include_revoked=False):
        """Get all dislikes/passes sent by a user."""
        queryset = cls.objects.filter(
            user=user,
            interaction_type=cls.DISLIKE
        )
        if not include_revoked:
            queryset = queryset.filter(is_revoked=False)
        return queryset.select_related('target_user__profile').prefetch_related('target_user__profile__photos')
    
    @classmethod
    def get_active_interaction(cls, user, target_user):
        """Get active interaction between two users."""
        return cls.objects.filter(
            user=user,
            target_user=target_user,
            is_revoked=False
        ).first()
    
    @classmethod
    def create_or_reactivate(cls, user, target_user, interaction_type):
        """
        Create a new interaction or reactivate a revoked one.
        Returns (interaction, created) tuple.
        
        IMPORTANT: Handles the case where an active interaction already exists
        to avoid violating the unique constraint.
        """
        from django.db import IntegrityError
        
        try:
            # Check if an ACTIVE interaction already exists
            existing_active = cls.objects.filter(
                user=user,
                target_user=target_user,
                interaction_type=interaction_type,
                is_revoked=False
            ).first()
            
            if existing_active:
                # Update the existing active interaction instead of creating a new one
                existing_active.created_at = timezone.now()
                existing_active.save(update_fields=['created_at'])
                return existing_active, False
            
            # Check for existing revoked interaction
            existing_revoked = cls.objects.filter(
                user=user,
                target_user=target_user,
                interaction_type=interaction_type,
                is_revoked=True
            ).first()
            
            if existing_revoked:
                # Reactivate existing interaction
                existing_revoked.is_revoked = False
                existing_revoked.created_at = timezone.now()
                existing_revoked.revoked_at = None
                existing_revoked.save()
                return existing_revoked, False
            
            # Create new interaction
            interaction = cls.objects.create(
                user=user,
                target_user=target_user,
                interaction_type=interaction_type
            )
            return interaction, True
            
        except IntegrityError:
            # In case of race condition, get the existing active interaction
            existing = cls.objects.get(
                user=user,
                target_user=target_user,
                interaction_type=interaction_type,
                is_revoked=False
            )
            # Update the timestamp
            existing.created_at = timezone.now()
            existing.save(update_fields=['created_at'])
            return existing, False