"""Server-side entitlement rules for the monthly Free matching allowance."""

from __future__ import annotations

from datetime import timezone as datetime_timezone
from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from subscriptions.utils import is_premium_user

from .models import Like, Match, MonthlyFreeAccess

if TYPE_CHECKING:
    from authentication.models import User


class FreeMatchAccessError(Exception):
    """A stable, client-safe reason for an entitlement denial."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class FreeMatchAccessService:
    FREE_TEXT_MESSAGE_LIMIT = 10

    @staticmethod
    def is_enabled() -> bool:
        return bool(getattr(settings, 'HIVMEET_FREE_MATCH_ACCESS_ENABLED', False))

    @staticmethod
    def month_start():
        """First day of the current civil month in UTC."""
        utc_date = timezone.now().astimezone(datetime_timezone.utc).date()
        return utc_date.replace(day=1)

    @classmethod
    def _lock_users(cls, *users: 'User'):
        """Lock participants in a deterministic order before their allowance."""
        User = get_user_model()
        ids = sorted((user.pk for user in users), key=str)
        locked = User.objects.select_for_update().filter(pk__in=ids).order_by('pk')
        return {user.pk: user for user in locked}

    @classmethod
    def _consumption_for_locked_user(cls, user: 'User'):
        return MonthlyFreeAccess.objects.filter(
            user=user,
            month_start=cls.month_start(),
        ).first()

    @classmethod
    def _set_full_access(cls, match: Match) -> Match:
        if match.access_level != Match.ACCESS_FULL:
            match.access_level = Match.ACCESS_FULL
            match.save(update_fields=['access_level', 'updated_at'])
        return match

    @classmethod
    def initialize_new_match(cls, match: Match) -> Match:
        """Apply policy to a newly created active match exactly once.

        Free-Free matches are unlocked only when both tokens can be consumed in
        the same database transaction.  A failed attempt persists only the
        locked state; neither participant loses an allowance.
        """
        if not cls.is_enabled():
            return match

        with transaction.atomic():
            locked_users = cls._lock_users(match.user1, match.user2)
            locked_match = Match.objects.select_for_update().select_related(
                'user1', 'user2'
            ).get(pk=match.pk)
            if locked_match.status != Match.ACTIVE:
                return locked_match
            user1 = locked_users[locked_match.user1_id]
            user2 = locked_users[locked_match.user2_id]
            if is_premium_user(user1) or is_premium_user(user2):
                return cls._set_full_access(locked_match)
            return cls._unlock_if_both_tokens_available(locked_match, user1, user2)

    @classmethod
    def retry_unlock(cls, user: 'User', match: Match) -> Match:
        """Explicit, idempotent retry for a locked Free-Free match."""
        if not cls.is_enabled():
            return match

        with transaction.atomic():
            locked_users = cls._lock_users(match.user1, match.user2)
            locked_match = Match.objects.select_for_update().select_related(
                'user1', 'user2'
            ).get(pk=match.pk)
            if user.pk not in (locked_match.user1_id, locked_match.user2_id):
                raise FreeMatchAccessError('match_not_found', _('Match not found.'))
            if locked_match.status != Match.ACTIVE:
                raise FreeMatchAccessError('match_not_found', _('Match not found.'))
            user1 = locked_users[locked_match.user1_id]
            user2 = locked_users[locked_match.user2_id]
            if is_premium_user(user1) or is_premium_user(user2):
                return cls._set_full_access(locked_match)
            if locked_match.access_level in (
                Match.ACCESS_FULL,
                Match.ACCESS_FREE_LIMITED,
            ):
                return locked_match
            return cls._unlock_if_both_tokens_available(locked_match, user1, user2)

    @classmethod
    def _unlock_if_both_tokens_available(
        cls,
        match: Match,
        user1: 'User',
        user2: 'User',
    ) -> Match:
        month_start = cls.month_start()
        user1_consumption = MonthlyFreeAccess.objects.filter(
            user=user1, month_start=month_start
        ).first()
        user2_consumption = MonthlyFreeAccess.objects.filter(
            user=user2, month_start=month_start
        ).first()

        if user1_consumption or user2_consumption:
            if match.access_level != Match.ACCESS_LOCKED:
                match.access_level = Match.ACCESS_LOCKED
                match.save(update_fields=['access_level', 'updated_at'])
            return match

        # The participant rows are locked, so these two creates cannot race a
        # like reveal or another unlock for either participant.
        MonthlyFreeAccess.objects.create(
            user=user1,
            month_start=month_start,
            purpose=MonthlyFreeAccess.FREE_MATCH,
        )
        MonthlyFreeAccess.objects.create(
            user=user2,
            month_start=month_start,
            purpose=MonthlyFreeAccess.FREE_MATCH,
        )
        match.access_level = Match.ACCESS_FREE_LIMITED
        match.save(update_fields=['access_level', 'updated_at'])
        return match

    @classmethod
    def reveal_received_like(cls, user: 'User') -> tuple[Like, bool]:
        """Reveal one received like and consume the Free allowance once.

        Returns ``(like, already_revealed)``.  The second value is true for a
        network retry, so callers can safely render the canonical first reveal.
        """
        if not cls.is_enabled():
            raise FreeMatchAccessError('feature_disabled', _('This feature is not available yet.'))
        if is_premium_user(user):
            raise FreeMatchAccessError('premium_not_required', _('Premium accounts already have this access.'))

        with transaction.atomic():
            locked_user = cls._lock_users(user).get(user.pk)
            month_start = cls.month_start()
            consumption = MonthlyFreeAccess.objects.filter(
                user=locked_user,
                month_start=month_start,
            ).select_related('revealed_like__from_user__profile').first()
            if consumption:
                if (
                    consumption.purpose == MonthlyFreeAccess.LIKE_REVEAL
                    and consumption.revealed_like_id
                ):
                    return consumption.revealed_like, True
                raise FreeMatchAccessError(
                    'monthly_token_used',
                    _('Your monthly Free access has already been used.'),
                )

            # A monthly reveal must obey the same bilateral block boundary as
            # profile discovery.  A stale Like cannot reveal a person either
            # participant has blocked.
            like = Like.objects.filter(to_user=locked_user).exclude(
                from_user__in=locked_user.blocked_users.all()
            ).exclude(
                from_user__blocked_users=locked_user
            ).select_related('from_user__profile').distinct().order_by(
                '-created_at', '-id'
            ).first()
            if like is None:
                raise FreeMatchAccessError('no_received_like', _('No received like is available to reveal.'))
            MonthlyFreeAccess.objects.create(
                user=locked_user,
                month_start=month_start,
                purpose=MonthlyFreeAccess.LIKE_REVEAL,
                revealed_like=like,
            )
            return like, False

    @classmethod
    def state_for(cls, match: Match, user: 'User') -> dict:
        """Return the DTO fragment that drives all client-side access UI."""
        if not cls.is_enabled() or is_premium_user(user):
            level = Match.ACCESS_FULL
        else:
            level = match.access_level
        if level == Match.ACCESS_FREE_LIMITED:
            sent = match.get_free_messages_sent(user)
            remaining = max(0, cls.FREE_TEXT_MESSAGE_LIMIT - sent)
            return {
                'access_level': level,
                'can_view_profile': True,
                'can_send_messages': remaining > 0,
                'free_messages_remaining': remaining,
                'access_locked_reason': None,
            }
        if level == Match.ACCESS_LOCKED:
            return {
                'access_level': level,
                'can_view_profile': False,
                'can_send_messages': False,
                'free_messages_remaining': 0,
                'access_locked_reason': 'monthly_token_unavailable',
            }
        return {
            'access_level': Match.ACCESS_FULL,
            'can_view_profile': True,
            'can_send_messages': True,
            'free_messages_remaining': None,
            'access_locked_reason': None,
        }

    @classmethod
    def ensure_conversation_access(cls, match: Match, user: 'User') -> None:
        if not cls.state_for(match, user)['can_view_profile']:
            raise FreeMatchAccessError(
                'free_match_locked',
                _('This Free match is locked until both monthly accesses are available.'),
            )

    @classmethod
    def ensure_can_send_text(cls, match: Match, user: 'User') -> None:
        state = cls.state_for(match, user)
        if state['access_level'] == Match.ACCESS_LOCKED:
            raise FreeMatchAccessError(
                'free_match_locked',
                _('This Free match is locked until both monthly accesses are available.'),
            )
        if not state['can_send_messages']:
            raise FreeMatchAccessError(
                'free_message_limit_reached',
                _('Your ten Free messages for this match have been sent.'),
            )

    @classmethod
    def record_sent_text(cls, match: Match, user: 'User') -> None:
        """Increment only after a new message was persisted under match lock."""
        if not cls.is_enabled() or is_premium_user(user):
            return
        if match.access_level != Match.ACCESS_FREE_LIMITED:
            return
        field = (
            'user1_free_messages_sent'
            if user.pk == match.user1_id
            else 'user2_free_messages_sent'
        )
        setattr(match, field, getattr(match, field) + 1)
        match.save(update_fields=[field, 'updated_at'])
