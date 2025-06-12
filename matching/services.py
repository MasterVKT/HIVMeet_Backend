"""
Matching and recommendation services.
"""
from __future__ import annotations
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q, F, Value, FloatField, ExpressionWrapper, Case, When, IntegerField
from django.db.models.functions import Radians, Cos, Sin, ACos, Least
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import timedelta, date
import math
import logging
from typing import List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from authentication.models import User as UserType

from profiles.models import Profile
from .models import Like, Dislike, Match, ProfileView, Boost, DailyLikeLimit

logger = logging.getLogger('hivmeet.matching')
User = get_user_model()


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
        
        # Convert to radians
        lat_rad = math.radians(float(user_profile.latitude))
        lon_rad = math.radians(float(user_profile.longitude))
        
        # Rough bounding box to limit initial query
        # 1 degree of latitude is approximately 111 km
        lat_diff = max_distance / 111.0
        # 1 degree of longitude varies by latitude
        lon_diff = max_distance / (111.0 * math.cos(lat_rad))
        
        # Create bounding box filter
        bbox_filter = Q(
            latitude__gte=user_profile.latitude - lat_diff,
            latitude__lte=user_profile.latitude + lat_diff,
            longitude__gte=user_profile.longitude - lon_diff,
            longitude__lte=user_profile.longitude + lon_diff
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
        if not hasattr(user, 'profile'):
            return []
        
        user_profile = user.profile
        
        # Get IDs of users already interacted with
        liked_user_ids = Like.objects.filter(
            from_user=user
        ).values_list('to_user_id', flat=True)
        
        disliked_user_ids = Dislike.objects.filter(
            from_user=user,
            expires_at__gt=timezone.now()
        ).values_list('to_user_id', flat=True)
        
        blocked_user_ids = user.blocked_users.values_list('id', flat=True)
        blocked_by_ids = User.objects.filter(
            blocked_users=user
        ).values_list('id', flat=True)
        
        # Combine all excluded user IDs
        excluded_ids = set(liked_user_ids) | set(disliked_user_ids) | \
                      set(blocked_user_ids) | set(blocked_by_ids) | {user.id}
        
        # Base query
        query = Profile.objects.select_related('user').prefetch_related('photos').filter(
            user__is_active=True,
            user__email_verified=True,
            is_hidden=False,
            allow_profile_in_discovery=True
        ).exclude(
            user_id__in=excluded_ids
        )
        
        # Apply age preferences (mutual)
        user_age = user.age
        if user_age:
            query = query.filter(
                age_min_preference__lte=user_age,
                age_max_preference__gte=user_age
            )
        
        # Apply user's age preferences
        query = query.annotate(
            user_age=timezone.now().year - F('user__birth_date__year')
        ).filter(
            user_age__gte=user_profile.age_min_preference,
            user_age__lte=user_profile.age_max_preference
        )
        
        # Apply gender preferences (mutual)
        if user_profile.genders_sought:
            query = query.filter(gender__in=user_profile.genders_sought)
        
        if user_profile.gender and user_profile.gender != 'prefer_not_to_say':
            query = query.filter(
                Q(genders_sought__contains=[user_profile.gender]) |
                Q(genders_sought=[])
            )
        
        # Apply relationship type preferences
        if user_profile.relationship_types_sought:
            # Find profiles with overlapping relationship preferences
            relationship_filter = Q()
            for rel_type in user_profile.relationship_types_sought:
                relationship_filter |= Q(relationship_types_sought__contains=[rel_type])
            query = query.filter(relationship_filter)
        
        # Apply distance filter
        distance_filter = RecommendationService.get_distance_filter(user_profile)
        if distance_filter:
            query = query.filter(distance_filter)
        
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
            '-profile_completeness'
        ).distinct()
        
        # Apply pagination
        profiles = query[offset:offset + limit]
        
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
        """
        # Get or create today's limit record
        today = date.today()
        limit, created = DailyLikeLimit.objects.get_or_create(
            user=user,
            date=today
        )
        
        if not limit.has_likes_remaining(user):
            if user.is_premium:
                return True, None
            elif user.is_verified:
                return False, _("Daily limit of 30 likes reached.")
            else:
                return False, _("Daily limit of 20 likes reached. Verify your account to get 30 likes per day.")
        
        return True, None
    
    @staticmethod
    def like_profile(from_user: 'UserType', to_user: 'UserType', is_super_like: bool = False) -> Tuple[bool, bool, Optional[str]]:
        """
        Process a like action.
        Returns (success, is_match, error_message).
        """
        # Check if already liked
        if Like.objects.filter(from_user=from_user, to_user=to_user).exists():
            return False, False, _("Already liked this profile.")
        
        # Check daily limits
        if is_super_like:
            today = date.today()
            limit, created = DailyLikeLimit.objects.get_or_create(
                user=from_user,
                date=today
            )
            
            if not from_user.is_premium:
                return False, False, _("Super likes are a premium feature.")
            
            if not limit.has_super_likes_remaining():
                return False, False, _("Daily limit of 3 super likes reached.")
            
            limit.super_likes_count += 1
            limit.save()
        else:
            can_like, error_msg = MatchingService.can_user_like(from_user)
            if not can_like:
                return False, False, error_msg
            
            # Update daily count
            today = date.today()
            limit, created = DailyLikeLimit.objects.get_or_create(
                user=from_user,
                date=today
            )
            limit.likes_count += 1
            limit.save()
        
        # Create like
        like = Like.objects.create(
            from_user=from_user,
            to_user=to_user,
            like_type=Like.SUPER if is_super_like else Like.REGULAR
        )
        
        # Check for mutual like (match)
        mutual_like = Like.objects.filter(
            from_user=to_user,
            to_user=from_user
        ).first()
        
        if mutual_like:
            # Create match
            # Ensure consistent ordering for unique constraint
            if from_user.id < to_user.id:
                user1, user2 = from_user, to_user
            else:
                user1, user2 = to_user, from_user
            
            match, created = Match.objects.get_or_create(
                user1=user1,
                user2=user2,
                defaults={'status': Match.ACTIVE}
            )
            
            if created:
                logger.info(f"Match created between {user1.email} and {user2.email}")
                
                # TODO: Send match notifications
                
            return True, True, None
          # Update likes received count
        if hasattr(to_user, 'profile'):
            to_user.profile.likes_received += 1
            to_user.profile.save(update_fields=['likes_received'])
        
        return True, False, None
    
    @staticmethod
    def dislike_profile(from_user: 'UserType', to_user: 'UserType') -> Tuple[bool, Optional[str]]:
        """
        Process a dislike (pass) action.
        Returns (success, error_message).
        """
        # Check if already disliked
        existing = Dislike.objects.filter(
            from_user=from_user,
            to_user=to_user,
            expires_at__gt=timezone.now()
        ).first()
        
        if existing:
            return False, _("Already passed on this profile.")
          # Create dislike
        Dislike.objects.create(
            from_user=from_user,
            to_user=to_user
        )
        
        return True, None
    
    @staticmethod
    def rewind_last_action(user: 'UserType') -> Tuple[bool, Optional[dict], Optional[str]]:
        """
        Rewind (undo) the last swipe action.
        Returns (success, previous_profile_data, error_message).
        """
        if not user.is_premium:
            return False, None, _("Rewind is a premium feature.")
        
        # Check daily limit
        today = date.today()
        limit, created = DailyLikeLimit.objects.get_or_create(
            user=user,
            date=today
        )
        
        if not limit.has_rewinds_remaining():
            return False, None, _("Daily limit of 3 rewinds reached.")
        
        # Find last action (within 5 minutes)
        five_minutes_ago = timezone.now() - timedelta(minutes=5)
        
        # Check likes
        last_like = Like.objects.filter(
            from_user=user,
            created_at__gte=five_minutes_ago
        ).order_by('-created_at').first()
        
        # Check dislikes
        last_dislike = Dislike.objects.filter(
            from_user=user,
            created_at__gte=five_minutes_ago
        ).order_by('-created_at').first()
        
        # Determine which was more recent
        if last_like and last_dislike:
            if last_like.created_at > last_dislike.created_at:
                last_action = last_like
                action_type = 'like'
            else:
                last_action = last_dislike
                action_type = 'dislike'
        elif last_like:
            last_action = last_like
            action_type = 'like'
        elif last_dislike:
            last_action = last_dislike
            action_type = 'dislike'
        else:
            return False, None, _("No recent action to rewind.")
        
        # Get profile data before deletion
        profile = last_action.to_user.profile
        profile_data = {
            'user_id': str(last_action.to_user.id),
            'display_name': last_action.to_user.display_name,
            'age': last_action.to_user.age,
            'bio': profile.bio,
            'photos': [
                {
                    'url': photo.photo_url,
                    'thumbnail_url': photo.thumbnail_url
                }
                for photo in profile.photos.all()
            ]
        }
        
        # Delete the action
        if action_type == 'like':
            # Check if this broke a match
            match = Match.get_match_between(user, last_action.to_user)
            if match:
                match.delete()
        
        last_action.delete()
        
        # Update rewind count
        limit.rewinds_count += 1
        limit.save()
        
        return True, profile_data, None