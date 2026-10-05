"""
Matching and recommendation services.
"""
from __future__ import annotations
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.db.models import Q, F, Value, FloatField, ExpressionWrapper, Case, When, IntegerField
from django.db.models.functions import Radians, Cos, Sin, ACos, Least
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import timedelta, date
import math
import logging
from typing import List, Optional, Tuple, TYPE_CHECKING

from hivmeet_backend.utils import normalize_media_url

if TYPE_CHECKING:
    from authentication.models import User as UserType

from profiles.models import Profile
from .models import (
    Like,
    Dislike,
    Match,
    ProfileView,
    Boost,
    DailyLikeLimit,
    InteractionActionRejected,
    InteractionHistory,
)
from .free_access import FreeMatchAccessService
from .interaction_service import InteractionService

logger = logging.getLogger('hivmeet.matching')
User = get_user_model()


class SwipeQuotaExceeded(Exception):
    """Abort an action before a new interaction consumes a daily swipe."""

    def __init__(self, message, code):
        super().__init__(message)
        self.message = message
        self.code = code


class RecommendationService:
    """
    Service for generating profile recommendations.
    """
    
    @staticmethod
    def get_distance_filter(user_profile: Profile, max_distance_km: Optional[int] = None):
        """
        Create a distance filter for database queries.
        Uses the Haversine formula for calculating distances.
        """
        if not user_profile.latitude or not user_profile.longitude:
            return Q()
        
        max_distance = max_distance_km or user_profile.distance_max_km
        
        # Earth's radius in kilometers
        earth_radius = 6371.0
        
        # Convert Decimal to float for calculations
        user_lat = float(user_profile.latitude)
        user_lon = float(user_profile.longitude)
        
        # Convert to radians
        lat_rad = math.radians(user_lat)
        lon_rad = math.radians(user_lon)
        
        # Rough bounding box to limit initial query
        # 1 degree of latitude is approximately 111 km
        lat_diff = max_distance / 111.0
        # 1 degree of longitude varies by latitude
        lon_diff = max_distance / (111.0 * math.cos(lat_rad))
        
        # Create bounding box filter
        bbox_filter = Q(
            latitude__gte=user_lat - lat_diff,
            latitude__lte=user_lat + lat_diff,
            longitude__gte=user_lon - lon_diff,
            longitude__lte=user_lon + lon_diff
        )
        
        return bbox_filter
    
    @staticmethod
    def calculate_distance_annotation():
        """
        Create database annotation for calculating distance.
        This would be used with the user's coordinates.
        """        # This is a simplified version. In production, you'd use
        # PostGIS or a similar geographic database extension
        return Value(0, output_field=FloatField())
    
    @staticmethod
    def get_recommendations(user: 'UserType', limit: int = 20, offset: int = 0) -> List[Profile]:
        """
        Get profile recommendations for a user.
        """
        # LOG 1: Début
        logger.info("Recommendation request: limit=%s offset=%s", limit, offset)
        
        if not hasattr(user, 'profile'):
            logger.warning("Recommendation request has no profile")
            return []
        
        user_profile = user.profile
        
        # Get IDs of users with active (non-revoked) interactions from InteractionHistory
        # IMPORTANT: Evaluate QuerySets to list NOW to avoid stale data in same request
        interacted_user_ids_list = list(
            InteractionHistory.objects.filter(
                user=user,
                is_revoked=False
            ).values_list('target_user_id', flat=True)
        )
        
        # Also get legacy data (backwards compatibility)
        # Only exclude legacy likes/dislikes that haven't been revoked in InteractionHistory
        revoked_user_ids_list = list(
            InteractionHistory.objects.filter(
                user=user,
                is_revoked=True
            ).values_list('target_user_id', flat=True)
        )
        
        legacy_liked_ids_list = list(
            Like.objects.filter(
                from_user=user
            ).exclude(
                to_user_id__in=revoked_user_ids_list
            ).values_list('to_user_id', flat=True)
        )
        
        legacy_disliked_ids_list = list(
            Dislike.objects.filter(
                from_user=user,
                expires_at__gt=timezone.now()
            ).exclude(
                to_user_id__in=revoked_user_ids_list
            ).values_list('to_user_id', flat=True)
        )
        
        blocked_user_ids_list = list(user.blocked_users.values_list('id', flat=True))
        blocked_by_ids_list = list(
            User.objects.filter(
                blocked_users=user
            ).values_list('id', flat=True)
        )
        
        # Combine all excluded user IDs
        excluded_ids = set(interacted_user_ids_list) | set(legacy_liked_ids_list) | set(legacy_disliked_ids_list) | \
                      set(blocked_user_ids_list) | set(blocked_by_ids_list) | {user.id}
        
        # LOG 2: Profils exclus
        logger.info(f"🚫 Excluding {len(excluded_ids)} profiles:")
        logger.info(f"   - Active interactions (is_revoked=False): {len(interacted_user_ids_list)}")
        logger.info(f"   - Legacy likes: {len(legacy_liked_ids_list)}")
        logger.info(f"   - Legacy dislikes: {len(legacy_disliked_ids_list)}")
        logger.info(f"   - Blocked users: {len(blocked_user_ids_list)}")
        logger.info(f"   - Blocked by: {len(blocked_by_ids_list)}")
        
        # Base query
        query = Profile.objects.select_related('user').prefetch_related('photos').filter(
            user__is_active=True,
            user__email_verified=True,
            is_hidden=False,
            allow_profile_in_discovery=True,
            gender__in=[Profile.MALE, Profile.FEMALE],
        ).exclude(
            user_id__in=excluded_ids
        )
        
        # LOG 3: Après filtres de base
        count_after_base = query.count()
        logger.info(f"📊 After base filters (active, email_verified, not hidden, discovery enabled): {count_after_base} profiles")
        
        # Apply age preferences (mutual)
        user_age = user.age
        if user_age:
            query = query.filter(
                age_min_preference__lte=user_age,
                age_max_preference__gte=user_age
            )
            logger.debug(
                "After mutual age compatibility: %s profiles",
                query.count(),
            )
        
        # Apply user's age preferences
        query = query.annotate(
            user_age=timezone.now().year - F('user__birth_date__year')
        ).filter(
            user_age__gte=user_profile.age_min_preference,
            user_age__lte=user_profile.age_max_preference
        )
        logger.debug("After age filter: %s profiles", query.count())
        
        # Apply gender preferences (mutual)
        # If genders_sought is empty list, it means "all" - no filter applied
        if user_profile.genders_sought:
            query = query.filter(gender__in=user_profile.genders_sought)
            logger.debug("After gender filter: %s profiles", query.count())
        
        # Apply mutual gender compatibility (target profile seeks user's gender)
        # Accept if: genders_sought is empty ([]), is NULL, or contains user's gender
        if user_profile.gender and user_profile.gender != 'prefer_not_to_say':
            query = query.filter(
                Q(genders_sought__contains=[user_profile.gender]) |  # Contains user's gender
                Q(genders_sought=[]) |  # Empty list means "all"
                Q(genders_sought__isnull=True)  # NULL means no preference set (accept all)
            )
            logger.debug(
                "After mutual gender compatibility: %s profiles",
                query.count(),
            )
        
        # Apply relationship type preferences
        # If relationship_types_sought is empty list, it means "all" - no filter applied
        if user_profile.relationship_types_sought:
            # Find profiles with overlapping relationship preferences
            # Also accept profiles with [] (meaning "all types")
            relationship_filter = Q(relationship_types_sought=[])
            for rel_type in user_profile.relationship_types_sought:
                relationship_filter |= Q(relationship_types_sought__contains=[rel_type])
            query = query.filter(relationship_filter)
            logger.debug(
                "After relationship type filter: %s profiles",
                query.count(),
            )
        
        # Apply distance filter
        distance_filter = RecommendationService.get_distance_filter(user_profile)
        if distance_filter:
            query = query.filter(distance_filter)
            logger.debug("After distance filter: %s profiles", query.count())
        
        # Apply "verified only" filter
        if user_profile.verified_only:
            query = query.filter(user__is_verified=True)
            logger.info(f"   After verified_only filter: {query.count()} profiles ⚠️")
        
        # Apply "online only" filter (last active within 5 minutes)
        if user_profile.online_only:
            cutoff_time = timezone.now() - timedelta(minutes=5)
            query = query.filter(user__last_active__gte=cutoff_time)
            logger.info(f"   After online_only filter (last 5 min): {query.count()} profiles ⚠️")
        
        # Apply boost priority
        active_boosts = Boost.objects.filter(
            expires_at__gt=timezone.now()
        ).values_list('user_id', flat=True)
          # Order by various factors
        query = query.annotate(
            is_boosted=Case(
                When(user_id__in=active_boosts, then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            ),
            has_verified=Case(
                When(user__is_verified=True, then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            ),
            profile_completeness=Case(
                When(bio__isnull=False, then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            ) + Case(
                When(photos__isnull=False, then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            )
        ).order_by(
            '-is_boosted',
            '-user__last_active',
            '-has_verified',
            '-profile_completeness',
            'user__date_joined'  # Stable ordering to prevent pagination cycling (User model uses date_joined, not created_at)
        ).distinct()
        
        # LOG 4: Avant pagination
        logger.info(f"📊 Total profiles after all filters: {query.count()}")
        
        # Apply pagination
        profiles = query[offset:offset + limit]
        
        # LOG 5: Résultat final
        logger.info(f"✅ Final result after pagination [{offset}:{offset+limit}]: {len(profiles)} profiles")
        if len(profiles) == 0 and query.count() > 0:
            logger.warning(f"⚠️  Pagination returned 0 profiles but {query.count()} are available (offset issue?)")
        
        # Log profile view events
        for profile in profiles:
            ProfileView.objects.get_or_create(
                viewer=user,
                viewed=profile.user
            )
        
        return list(profiles)
    
    @staticmethod
    def get_compatibility_score(user_profile: Profile, target_profile: Profile) -> float:
        """
        Calculate compatibility score between two profiles.
        Returns a score between 0 and 100.
        """
        score = 0.0
        
        # Age compatibility (20 points)
        user_age = user_profile.user.age
        target_age = target_profile.user.age
        
        if user_age and target_age:
            if (user_profile.age_min_preference <= target_age <= user_profile.age_max_preference and
                target_profile.age_min_preference <= user_age <= target_profile.age_max_preference):
                score += 20
        
        # Gender compatibility (20 points)
        if (user_profile.gender in target_profile.genders_sought or not target_profile.genders_sought):
            score += 10
        if (target_profile.gender in user_profile.genders_sought or not user_profile.genders_sought):
            score += 10
        
        # Relationship type compatibility (20 points)
        if user_profile.relationship_types_sought and target_profile.relationship_types_sought:
            common_types = set(user_profile.relationship_types_sought) & \
                          set(target_profile.relationship_types_sought)
            if common_types:
                score += 20
        
        # Interest compatibility (20 points)
        if user_profile.interests and target_profile.interests:
            common_interests = set(user_profile.interests) & set(target_profile.interests)
            interest_score = (len(common_interests) / max(len(user_profile.interests), 
                                                         len(target_profile.interests))) * 20
            score += interest_score
        
        # Activity level (10 points)
        days_inactive = (timezone.now() - target_profile.user.last_active).days
        if days_inactive <= 1:
            score += 10
        elif days_inactive <= 7:
            score += 5
        
        # Profile completeness (10 points)
        if target_profile.bio:
            score += 5
        if target_profile.photos.exists():
            score += 5
        
        return min(score, 100)


class MatchingService:
    """
    Service for handling likes, dislikes, and matches.
    """
    
    @staticmethod
    def can_user_like(user: 'UserType') -> Tuple[bool, Optional[str]]:
        """
        Check if user can send a like.
        Returns (can_like, error_message).
        
        NOTE: This uses the OLD DailyLikeLimit model. For the new implementation,
        use DailyLikesService from daily_likes_service.py instead.
        This method is kept for backward compatibility.
        """
        # Import the new service
        from .daily_likes_service import DailyLikesService
        
        return DailyLikesService.can_user_like(user)
    
    @staticmethod
    @transaction.atomic
    def like_profile(from_user: 'UserType', to_user: 'UserType', is_super_like: bool = False) -> Tuple[bool, bool, Optional[str], Optional[str]]:
        """Process a like under one lock order for every pair projection."""
        if is_super_like:
            from subscriptions.utils import check_feature_availability
            feature = check_feature_availability(from_user, 'super_like')
            if not feature['available']:
                code = (
                    'super_like_limit'
                    if feature['reason'] == 'limit_reached'
                    else 'premium_required'
                )
                return False, False, _("Super likes are a premium feature."), code

        interaction_type = (
            InteractionHistory.SUPER_LIKE
            if is_super_like
            else InteractionHistory.LIKE
        )
        expected_like_type = Like.SUPER if is_super_like else Like.REGULAR

        # Historical deployments can have a Like/Match pair from before
        # InteractionHistory was introduced. Retrying that exact old like is
        # idempotent and must never recreate a deleted match. A different
        # action still goes through the locked history path and is refused.
        legacy_like = Like.objects.filter(
            from_user=from_user,
            to_user=to_user,
            like_type=expected_like_type,
        ).first()
        legacy_match = Match.objects.filter(
            Q(user1=from_user, user2=to_user)
            | Q(user1=to_user, user2=from_user)
        ).first()
        if legacy_like is not None and legacy_match is not None:
            return True, legacy_match.status == Match.ACTIVE, None, None

        from .daily_likes_service import DailyLikesService

        def check_quota():
            can_swipe, error_msg = DailyLikesService.can_user_swipe(from_user)
            if not can_swipe:
                raise SwipeQuotaExceeded(error_msg, 'daily_limit')
            if is_super_like:
                can_super_like, error_msg = DailyLikesService.can_user_super_like(
                    from_user
                )
                if not can_super_like:
                    raise SwipeQuotaExceeded(error_msg, 'super_like_limit')

        try:
            _interaction, created_interaction = InteractionHistory.create_or_reactivate(
                user=from_user,
                target_user=to_user,
                interaction_type=interaction_type,
                before_create=check_quota,
            )
        except SwipeQuotaExceeded as error:
            return False, False, error.message, error.code
        except InteractionActionRejected as error:
            return (
                False,
                False,
                _("This connection already exists. Use unmatch to remove it."),
                error.code,
            )

        # InteractionHistory already locked the two users and their pair.
        # Rewind takes these projection locks after the same locks, so neither
        # path can delete the other action's Like/Dislike projection.
        existing_like = (
            Like.objects.select_for_update()
            .filter(from_user=from_user, to_user=to_user)
            .first()
        )
        existing_dislike = (
            Dislike.objects.select_for_update()
            .filter(from_user=from_user, to_user=to_user)
            .first()
        )
        if existing_dislike is not None:
            existing_dislike.delete()

        like_was_created = existing_like is None
        if existing_like is None:
            Like.objects.create(
                from_user=from_user,
                to_user=to_user,
                like_type=expected_like_type,
            )
        elif existing_like.like_type != expected_like_type:
            existing_like.like_type = expected_like_type
            existing_like.save(update_fields=['like_type'])

        if created_interaction:
            # The authoritative quota is InteractionHistory. The check above
            # occurred before the new row was saved; this legacy row remains
            # for dashboard compatibility only.
            limit, _limit_created = DailyLikeLimit.objects.select_for_update().get_or_create(
                user=from_user,
                date=timezone.localdate(),
            )
            if is_super_like:
                limit.super_likes_count += 1
                limit.save(update_fields=['super_likes_count'])
            else:
                limit.likes_count += 1
                limit.save(update_fields=['likes_count'])

        mutual_like = (
            Like.objects.select_for_update()
            .filter(from_user=to_user, to_user=from_user)
            .first()
        )
        if mutual_like:
            if from_user.id < to_user.id:
                user1, user2 = from_user, to_user
            else:
                user1, user2 = to_user, from_user

            match = (
                Match.objects.select_for_update()
                .filter(
                    Q(user1=from_user, user2=to_user)
                    | Q(user1=to_user, user2=from_user)
                )
                .first()
            )
            created_match = match is None
            if match is None:
                match = Match.objects.create(
                    user1=user1,
                    user2=user2,
                    status=Match.ACTIVE,
                )
            if not created_match and match.status != Match.ACTIVE:
                return True, False, None, None
            if created_match:
                FreeMatchAccessService.initialize_new_match(match)
                logger.info('Match created')
            return True, True, None, None

        if like_was_created and hasattr(to_user, 'profile'):
            to_user.profile.likes_received += 1
            to_user.profile.save(update_fields=['likes_received'])

        return True, False, None, None

    @staticmethod
    @transaction.atomic
    def dislike_profile(from_user: 'UserType', to_user: 'UserType') -> Tuple[bool, Optional[str]]:
        """Process a pass with the same pair locks as a like and a rewind."""
        from .daily_likes_service import DailyLikesService

        def check_quota():
            can_swipe, error_msg = DailyLikesService.can_user_swipe(from_user)
            if not can_swipe:
                raise SwipeQuotaExceeded(error_msg, 'daily_limit')

        try:
            _interaction, created_interaction = InteractionHistory.create_or_reactivate(
                user=from_user,
                target_user=to_user,
                interaction_type=InteractionHistory.DISLIKE,
                before_create=check_quota,
            )
        except SwipeQuotaExceeded as error:
            return False, error.message
        except InteractionActionRejected as error:
            return False, error.code

        existing_like = (
            Like.objects.select_for_update()
            .filter(from_user=from_user, to_user=to_user)
            .first()
        )
        existing_dislike = (
            Dislike.objects.select_for_update()
            .filter(from_user=from_user, to_user=to_user)
            .first()
        )
        if existing_like is not None:
            existing_like.delete()
            if hasattr(to_user, 'profile'):
                to_user.profile.likes_received = max(
                    0, to_user.profile.likes_received - 1
                )
                to_user.profile.save(update_fields=['likes_received'])

        expiry = timezone.now() + timedelta(days=30)
        if existing_dislike is None:
            Dislike.objects.create(
                from_user=from_user,
                to_user=to_user,
                expires_at=expiry,
            )
        elif existing_dislike.expires_at <= timezone.now() or created_interaction:
            existing_dislike.expires_at = expiry
            existing_dislike.save(update_fields=['expires_at'])

        return True, None

    @staticmethod
    def rewind_last_action(user: 'UserType') -> Tuple[bool, Optional[dict], Optional[str]]:
        """Legacy adapter for callers not yet carrying an interaction id.

        The discovery API no longer uses this method. It delegates to the
        explicit transactional service so a legacy caller cannot bypass match,
        expiry, idempotency or quota protections.
        """
        from .rewind_service import InteractionRewindService, RewindRejected

        interaction = (
            InteractionHistory.objects.filter(
                user=user,
                interaction_type__in=(
                    InteractionHistory.LIKE,
                    InteractionHistory.SUPER_LIKE,
                    InteractionHistory.DISLIKE,
                ),
                is_revoked=False,
            )
            .order_by('-created_at')
            .first()
        )
        if interaction is None:
            return False, None, _("No recent action to rewind.")

        try:
            result = InteractionRewindService.rewind(user, interaction.id)
        except RewindRejected as exc:
            return False, None, exc.code
        return True, result.profile, None

    @staticmethod
    def get_daily_like_limit(user: 'UserType') -> dict:
        """
        Get user's daily like limit information.
        Returns a dict with remaining_likes and total_likes.
        
        NOTE: This method is kept for backward compatibility.
        For the new implementation, use DailyLikesService from daily_likes_service.py.
        """
        # Import the new service
        from .daily_likes_service import DailyLikesService
        
        remaining = DailyLikesService.get_likes_remaining(user)
        daily_limit = DailyLikesService.get_user_daily_limit(user)
        
        # If unlimited (premium), return -1 to indicate unlimited
        if remaining == DailyLikesService.UNLIMITED:
            return {
                'remaining_likes': -1,  # -1 indicates unlimited
                'total_likes': -1,
                'likes_used': 0
            }
        
        return {
            'remaining_likes': remaining,
            'total_likes': daily_limit if daily_limit != DailyLikesService.UNLIMITED else -1,
            'likes_used': daily_limit - remaining if daily_limit != DailyLikesService.UNLIMITED else 0
        }
    
    @staticmethod
    def get_super_likes_remaining(user: 'UserType') -> int:
        """
        Get user's remaining super likes for today.
        Returns the number of super likes remaining.
        
        NOTE: This method is kept for backward compatibility.
        For the new implementation, use DailyLikesService from daily_likes_service.py.
        """
        # Import the new service
        from .daily_likes_service import DailyLikesService
        
        return DailyLikesService.get_super_likes_remaining(user)
