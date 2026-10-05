"""Transactional rewind for one explicit discovery interaction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _


from .models import DailyLikeLimit, Dislike, InteractionHistory, Like, Match

User = get_user_model()


class RewindRejected(Exception):
    """Stable business error returned by the discovery API."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RewindResult:
    interaction_id: str
    profile: dict
    already_rewound: bool


class InteractionRewindService:
    WINDOW = timedelta(minutes=5)
    DAILY_LIMIT = 5

    @classmethod
    def expires_at(cls, interaction):
        return interaction.created_at + cls.WINDOW

    @classmethod
    def can_rewind(cls, interaction, now=None) -> bool:
        now = now or timezone.now()
        if interaction.is_revoked:
            return False
        if interaction.created_at <= now - cls.WINDOW:
            return False
        return not Match.objects.filter(
            Q(user1=interaction.user, user2=interaction.target_user)
            | Q(user1=interaction.target_user, user2=interaction.user)
        ).exists()

    @classmethod
    @transaction.atomic
    def rewind(cls, user, interaction_id) -> RewindResult:
        now = timezone.now()
        target_id = (
            InteractionHistory.objects.filter(pk=interaction_id, user=user)
            .values_list('target_user_id', flat=True)
            .first()
        )
        if target_id is None:
            raise RewindRejected('interaction_not_found', _('Interaction not found.'))

        # Lock both participants in a deterministic order. New actions use
        # the same order, so opposite-direction requests cannot deadlock.
        user_ids = sorted((user.pk, target_id))
        locked_users = {
            locked.pk: locked
            for locked in (
                User.objects.select_for_update()
                .filter(pk__in=user_ids)
                .order_by('pk')
            )
        }
        locked_user = locked_users.get(user.pk)
        target = locked_users.get(target_id)
        if locked_user is None or target is None:
            raise RewindRejected('interaction_not_found', _('Interaction not found.'))
        interaction = (
            InteractionHistory.objects.select_for_update()
            .filter(pk=interaction_id, user=locked_user)
            .first()
        )
        if interaction is None:
            raise RewindRejected('interaction_not_found', _('Interaction not found.'))

        if interaction.rewound_at is not None:
            return RewindResult(
                interaction_id=str(interaction.id),
                profile=cls._profile_payload(target),
                already_rewound=True,
            )

        if interaction.is_revoked:
            raise RewindRejected(
                'interaction_not_active',
                _('This interaction is no longer active.'),
            )
        if interaction.created_at <= now - cls.WINDOW:
            raise RewindRejected(
                'rewind_expired',
                _('The five-minute rewind window has expired.'),
            )

        # Any match row proves that a match has been created for this pair.
        # An unmatch remains final and must never be mutated by rewind.
        existing_match = (
            Match.objects.select_for_update()
            .filter(
                Q(user1=locked_user, user2=target)
                | Q(user1=target, user2=locked_user)
            )
            .first()
        )
        if existing_match is not None:
            raise RewindRejected(
                'match_exists_use_unmatch',
                _(
                    'This swipe created a match. Remove the match to end the connection.'
                ),
            )

        # New actions take the same user/history/match/projection lock order.
        # It prevents a rewind from deleting a later action projection.
        if interaction.interaction_type in (
            InteractionHistory.LIKE,
            InteractionHistory.SUPER_LIKE,
        ):
            projection = (
                Like.objects.select_for_update()
                .filter(from_user=locked_user, to_user=target)
                .first()
            )
        else:
            projection = (
                Dislike.objects.select_for_update()
                .filter(from_user=locked_user, to_user=target)
                .first()
            )
        if projection is None:
            raise RewindRejected(
                'interaction_projection_missing',
                _('This interaction can no longer be rewound.'),
            )

        limit, _created = DailyLikeLimit.objects.select_for_update().get_or_create(
            user=locked_user,
            date=timezone.localdate(),
        )
        if limit.rewinds_count >= cls.DAILY_LIMIT:
            raise RewindRejected(
                'rewind_daily_limit',
                _('Daily limit of 5 rewinds reached.'),
            )

        profile = cls._profile_payload(target)
        projection.delete()
        if interaction.interaction_type in (
            InteractionHistory.LIKE,
            InteractionHistory.SUPER_LIKE,
        ) and hasattr(target, 'profile'):
            target.profile.likes_received = max(0, target.profile.likes_received - 1)
            target.profile.save(update_fields=['likes_received'])

        interaction.is_revoked = True
        interaction.revoked_at = now
        interaction.rewound_at = now
        interaction.save(update_fields=['is_revoked', 'revoked_at', 'rewound_at'])
        limit.rewinds_count += 1
        limit.save(update_fields=['rewinds_count'])

        return RewindResult(
            interaction_id=str(interaction.id),
            profile=profile,
            already_rewound=False,
        )

    @staticmethod
    def _profile_payload(target) -> dict:
        profile = getattr(target, 'profile', None)
        photos = []
        if profile:
            photos = [
                {
                    # This service has no authenticated request context: it
                    # must never mint a private photo URL into an event.
                    'url': None,
                    'thumbnail_url': None,
                }
                for photo in profile.photos.all()
            ]
        return {
            'user_id': str(target.id),
            'display_name': target.display_name,
            'age': target.age,
            'bio': profile.bio if profile else '',
            'photos': photos,
        }
