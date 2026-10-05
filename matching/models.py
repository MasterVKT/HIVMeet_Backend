"""
Matching models for HIVMeet.
"""
from django.db import IntegrityError, models, transaction
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models import Q
import uuid
from datetime import timedelta

User = get_user_model()


class InteractionActionRejected(Exception):
    """Business refusal raised while the pair is locked."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


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

    # Access policy.  ``full`` is deliberately the default: it keeps every
    # existing match usable during the additive rollout of the Free allowance.
    ACCESS_FULL = 'full'
    ACCESS_FREE_LIMITED = 'free_limited'
    ACCESS_LOCKED = 'locked'
    ACCESS_LEVEL_CHOICES = [
        (ACCESS_FULL, _('Full access')),
        (ACCESS_FREE_LIMITED, _('Free limited access')),
        (ACCESS_LOCKED, _('Locked monthly Free access')),
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

    access_level = models.CharField(
        max_length=20,
        choices=ACCESS_LEVEL_CHOICES,
        default=ACCESS_FULL,
        verbose_name=_('Access level'),
    )

    # These counters are only used for a Free-Free match that was unlocked by
    # both monthly allowances.  They are incremented while the Match is locked
    # by MessageService, so an HTTP retry cannot spend two messages.
    user1_free_messages_sent = models.PositiveSmallIntegerField(default=0)
    user2_free_messages_sent = models.PositiveSmallIntegerField(default=0)
    
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

    # A match is "new" independently for each participant.  A nullable
    # timestamp is intentional: null is the durable, queryable unread state;
    # it also avoids inferring the state from a client-side notification.
    user1_seen_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('User 1 seen at'),
    )
    user2_seen_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('User 2 seen at'),
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
            models.Index(
                fields=['user1', 'status', 'user1_seen_at'],
                name='match_u1_status_seen_idx',
            ),
            models.Index(
                fields=['user2', 'status', 'user2_seen_at'],
                name='match_u2_status_seen_idx',
            ),
        ]
    
    def __str__(self):
        return f"{self.user1.display_name} <-> {self.user2.display_name}"
    
    def get_other_user(self, user):
        """Get the other user in the match."""
        return self.user2 if user == self.user1 else self.user1
    
    def get_unread_count(self, user):
        """Get unread count for a specific user."""
        return self.user1_unread_count if user == self.user1 else self.user2_unread_count

    def get_free_messages_sent(self, user):
        return self.user1_free_messages_sent if user == self.user1 else self.user2_free_messages_sent

    def is_seen_by(self, user):
        """Return the participant-specific consultation state.

        This method deliberately rejects a non-participant instead of silently
        returning a value, so callers cannot accidentally use it as a match
        existence probe.
        """
        if user.pk == self.user1_id:
            return self.user1_seen_at is not None
        if user.pk == self.user2_id:
            return self.user2_seen_at is not None
        raise ValueError('The user is not a participant in this match.')

    def mark_seen_by(self, user, *, at=None):
        """Persist a participant consultation without altering the other one."""
        at = at or timezone.now()
        if user.pk == self.user1_id:
            if self.user1_seen_at is None:
                self.user1_seen_at = at
                self.save(update_fields=['user1_seen_at'])
            return
        if user.pk == self.user2_id:
            if self.user2_seen_at is None:
                self.user2_seen_at = at
                self.save(update_fields=['user2_seen_at'])
            return
        raise ValueError('The user is not a participant in this match.')
    
    def increment_unread(self, for_user):
        """Deprecated: counters are managed by the locked messaging service."""
        raise RuntimeError(
            'Unread counters must be updated by MessageService while the Match is locked.'
        )
    
    def reset_unread(self, for_user):
        """Deprecated: counters are managed by the locked messaging service."""
        raise RuntimeError(
            'Unread counters must be recalculated by MessageService while the Match is locked.'
        )
    
    @classmethod
    def get_match_between(cls, user1, user2):
        """Get match between two users if exists."""
        return cls.objects.filter(
            Q(user1=user1, user2=user2) | Q(user1=user2, user2=user1),
            status=cls.ACTIVE
        ).first()


class MonthlyFreeAccess(models.Model):
    """The single monthly Free allowance consumed by an explicit action.

    A row represents a consumption, never a reservation.  Its unique key
    makes the UTC civil-month rule database-enforced and allows a retried like
    reveal to return the same revealed profile without consuming another token.
    """

    LIKE_REVEAL = 'like_reveal'
    FREE_MATCH = 'free_match'
    PURPOSE_CHOICES = [
        (LIKE_REVEAL, _('Received like reveal')),
        (FREE_MATCH, _('Free match unlock')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='monthly_free_accesses',
    )
    month_start = models.DateField()
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    # Set only for LIKE_REVEAL.  Keeping this reference makes retries
    # idempotent without exposing a second received-like profile.
    revealed_like = models.ForeignKey(
        Like,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='monthly_reveals',
    )
    consumed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'monthly_free_accesses'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'month_start'],
                name='unique_monthly_free_access_per_user',
            ),
        ]
        indexes = [models.Index(fields=['user', 'month_start'])]

    def __str__(self):
        return f'{self.user_id} / {self.month_start} / {self.purpose}'


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
    
    def has_likes_remaining(self, user=None):
        """Return the canonical shared-swipe entitlement for this user."""
        from .daily_likes_service import DailyLikesService

        return DailyLikesService.get_likes_remaining(user or self.user) != 0
    
    def has_super_likes_remaining(self):
        """Return the canonical Premium super-like entitlement."""
        from .daily_likes_service import DailyLikesService

        return DailyLikesService.get_super_likes_remaining(self.user) > 0
    
    def has_rewinds_remaining(self):
        """Check if user has rewinds remaining."""
        return self.rewinds_count < 5


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

    # A rewind is a special, idempotent revocation.  Keeping its timestamp
    # lets a repeated request return the same result without consuming another
    # daily rewind and distinguishes it from a history-page revocation.
    rewound_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Rewound at'),
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
        # A discovery decision has one active projection per user-target pair.
        # Historical rows stay available after revocation, including a rewind.
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'target_user'],
                condition=Q(is_revoked=False),
                name='unique_active_interaction_pair',
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
    def create_or_reactivate(
        cls,
        user,
        target_user,
        interaction_type,
        *,
        before_create=None,
    ):
        """Record a discovery action without ever reactivating history.

        A retry of the currently active action is idempotent.  Once an action
        is revoked, including by rewind, a later action receives a new row and
        a new identifier.  Locking both participant rows in a stable order and
        the existing pair projection keeps competing swipes coherent.

        An existing match protects the pair: a stale client cannot replace the
        previous discovery action and must use the explicit unmatch flow.
        """
        if interaction_type not in {
            cls.LIKE,
            cls.SUPER_LIKE,
            cls.DISLIKE,
        }:
            raise ValueError('invalid_interaction_type')

        user_ids = sorted((user.pk, target_user.pk))
        for attempt in range(2):
            try:
                with transaction.atomic():
                    # The stable lock order avoids deadlocks between two
                    # opposite-direction swipes for the same pair.
                    locked_users = {
                        locked.pk: locked
                        for locked in (
                            User.objects.select_for_update()
                            .filter(pk__in=user_ids)
                            .order_by('pk')
                        )
                    }
                    locked_user = locked_users[user.pk]
                    locked_target = locked_users[target_user.pk]
                    active = list(
                        cls.objects.select_for_update()
                        .filter(
                            user=locked_user,
                            target_user=locked_target,
                            is_revoked=False,
                        )
                        .order_by('-created_at', '-id')
                    )

                    same_action = next(
                        (
                            interaction
                            for interaction in active
                            if interaction.interaction_type == interaction_type
                        ),
                        None,
                    )
                    if same_action is not None:
                        return same_action, False

                    if Match.objects.select_for_update().filter(
                        Q(user1=locked_user, user2=locked_target)
                        | Q(user1=locked_target, user2=locked_user),
                    ).exists():
                        raise InteractionActionRejected('match_exists_use_unmatch')

                    if before_create is not None:
                        before_create()

                    if active:
                        cls.objects.filter(
                            pk__in=[interaction.pk for interaction in active],
                            is_revoked=False,
                        ).update(
                            is_revoked=True,
                            revoked_at=timezone.now(),
                        )

                    return (
                        cls.objects.create(
                            user=locked_user,
                            target_user=locked_target,
                            interaction_type=interaction_type,
                        ),
                        True,
                    )
            except IntegrityError:
                # A database constraint can still win on engines where an
                # empty select_for_update query cannot lock a future insert.
                # Retry once, then return the now-active same action.
                if attempt:
                    raise

        raise RuntimeError('interaction_action_retry_exhausted')
