"""
Serializers for matching app with premium features integration.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

from .models import Like, Match, Boost, InteractionHistory
from profiles.models import Profile
from profiles.serializers import PublicProfileSerializer
from profiles.geography import distance_between
from subscriptions.utils import is_premium_user, get_premium_limits

User = get_user_model()


class LikeSerializer(serializers.ModelSerializer):
    """
    Serializer for likes.
    """
    target_user_id = serializers.CharField(source='target_user.id', read_only=True)

    class Meta:
        model = Like
        fields = ['id', 'target_user_id', 'is_super_like', 'created_at']
        read_only_fields = ['id', 'created_at']


class MatchSerializer(serializers.ModelSerializer):
    """
    Serializer for matches.
    """
    matched_user = serializers.SerializerMethodField()
    unread_count_for_me = serializers.SerializerMethodField()
    access_level = serializers.SerializerMethodField()
    can_view_profile = serializers.SerializerMethodField()
    can_send_messages = serializers.SerializerMethodField()
    free_messages_remaining = serializers.SerializerMethodField()
    access_locked_reason = serializers.SerializerMethodField()
    is_new = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = [
            'id', 'matched_user', 'created_at',
            'unread_count_for_me', 'access_level', 'can_view_profile',
            'can_send_messages', 'free_messages_remaining',
            'access_locked_reason', 'is_new',
        ]
        read_only_fields = ['id', 'created_at']

    def get_matched_user(self, obj):
        """Get the other user in the match."""
        request = self.context.get('request')
        if request and request.user:
            from .free_access import FreeMatchAccessService

            other_user = obj.user2 if obj.user1 == request.user else obj.user1
            access = FreeMatchAccessService.state_for(obj, request.user)
            # A locked match can remain in the list but must not leak the
            # counterpart's profile or location before both tokens exist.
            if not access['can_view_profile']:
                return {
                    'id': str(other_user.id),
                    'user_id': str(other_user.id),
                    'display_name': _('Match verrouillÃ©'),
                    'age': 0,
                    'bio': '',
                    'city': '',
                    'country': '',
                    'interests': [],
                    'relationship_types_sought': [],
                    'photos': [],
                    'is_locked': True,
                }
            from profiles.serializers import PublicProfileSerializer
            return PublicProfileSerializer(
                other_user.profile,
                context=self.context
            ).data
        return None

    def get_unread_count_for_me(self, obj):
        request = self.context.get('request')
        return obj.get_unread_count(request.user) if request and request.user else 0

    def _access(self, obj):
        from .free_access import FreeMatchAccessService

        request = self.context.get('request')
        return (
            FreeMatchAccessService.state_for(obj, request.user)
            if request and request.user else
            FreeMatchAccessService.state_for(obj, obj.user1)
        )

    def get_access_level(self, obj):
        return self._access(obj)['access_level']

    def get_can_view_profile(self, obj):
        return self._access(obj)['can_view_profile']

    def get_can_send_messages(self, obj):
        return self._access(obj)['can_send_messages']

    def get_free_messages_remaining(self, obj):
        return self._access(obj)['free_messages_remaining']

    def get_access_locked_reason(self, obj):
        return self._access(obj)['access_locked_reason']

    def get_is_new(self, obj):
        request = self.context.get('request')
        if not request or not request.user:
            return False
        return not obj.is_seen_by(request.user)


class RecommendedProfileSerializer(serializers.ModelSerializer):
    """
    Enhanced profile serializer with premium features.
    """
    user_id = serializers.CharField(source='user.id', read_only=True)
    display_name = serializers.CharField(source='user.display_name', read_only=True)
    age = serializers.IntegerField(source='user.age', read_only=True)
    distance = serializers.SerializerMethodField()
    has_liked_you = serializers.SerializerMethodField()
    is_boosted = serializers.SerializerMethodField()
    premium_user = serializers.SerializerMethodField()

    class Meta:
        from profiles.models import Profile
        model = Profile
        fields = [
            'user_id', 'display_name', 'age', 'bio', 'photos',
            'location', 'distance', 'has_liked_you', 'is_boosted',
            'premium_user', 'interests', 'hiv_status'
        ]

    def get_distance(self, obj):
        """Return a privacy-safe precise or city-estimated distance."""
        request = self.context.get('request')
        if request and request.user and hasattr(request.user, 'profile'):
            return distance_between(request.user.profile, obj).km
        return None

    def get_has_liked_you(self, obj):
        """Check if this user has liked the current user (Premium only)."""
        request = self.context.get('request')
        if request and request.user:
            # Only show if current user is premium
            if is_premium_user(request.user):
                return Like.objects.filter(
                    user=obj.user,
                    target_user=request.user
                ).exists()
            else:
                # Non-premium users see None
                return None
        return None

    def get_is_boosted(self, obj):
        """Check if this profile is currently boosted."""
        from django.utils import timezone
        return Boost.objects.filter(
            user=obj.user,
            is_active=True,
            expires_at__gt=timezone.now()
        ).exists()

    def get_premium_user(self, obj):
        """Check if this user has premium subscription."""
        return is_premium_user(obj.user)


class BoostSerializer(serializers.ModelSerializer):
    """
    Serializer for profile boosts.
    """
    time_remaining = serializers.SerializerMethodField()

    class Meta:
        model = Boost
        fields = ['id', 'is_active', 'created_at', 'expires_at', 'time_remaining']
        read_only_fields = ['id', 'created_at']

    def get_time_remaining(self, obj):
        """Get remaining time for the boost in minutes."""
        if obj.is_active:
            from django.utils import timezone
            remaining = (obj.expires_at - timezone.now()).total_seconds() / 60
            return max(0, int(remaining))
        return 0


class PremiumFeaturesSerializer(serializers.Serializer):
    """
    Serializer for user's premium features status.
    """
    is_premium = serializers.BooleanField()
    unlimited_likes = serializers.BooleanField()
    can_see_likers = serializers.BooleanField()
    can_rewind = serializers.BooleanField()
    super_likes_remaining = serializers.IntegerField()
    boosts_remaining = serializers.IntegerField()

    def to_representation(self, user):
        """Convert user to premium features representation."""
        if is_premium_user(user):
            limits = get_premium_limits(user)
            return {
                'is_premium': True,
                'unlimited_likes': limits['limits']['features']['unlimited_likes'],
                'can_see_likers': limits['limits']['features']['can_see_likers'],
                'can_rewind': limits['limits']['features']['can_rewind'],
                'super_likes_remaining': limits['limits']['super_likes']['remaining'],
                'boosts_remaining': limits['limits']['boosts']['remaining']
            }
        else:
            return {
                'is_premium': False,
                'unlimited_likes': False,
                'can_see_likers': False,
                'can_rewind': False,
                'super_likes_remaining': 0,
                'boosts_remaining': 0
            }
        return None

    def get_unread_count_for_me(self, obj):
        """Get unread count for current user."""
        request = self.context.get('request')
        if request and request.user:
            return obj.get_unread_count(request.user)
        return 0

    def _get_last_active_display(self, user):
        """Get display-friendly last active time."""
        from django.utils import timezone
        last_active = user.last_active
        now = timezone.now()
        diff = now - last_active

        if diff.total_seconds() < 300:  # 5 minutes
            return _("Online")
        elif diff.total_seconds() < 3600:  # 1 hour
            return _("Active recently")
        elif diff.days == 0:
            return _("Active today")
        elif diff.days == 1:
            return _("Active yesterday")
        else:
            return _("Active %(days)d days ago") % {'days': diff.days}


class DiscoveryProfileSerializer(serializers.Serializer):
    """
    Serializer for profiles in discovery.
    """
    user_id = serializers.UUIDField(source='user.id')
    display_name = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    bio = serializers.CharField()
    city = serializers.CharField()
    country = serializers.CharField()
    photos = serializers.SerializerMethodField()
    interests = serializers.ListField()
    relationship_types_sought = serializers.ListField()
    is_verified = serializers.BooleanField(source='user.is_verified')
    is_online = serializers.SerializerMethodField()
    distance_km = serializers.SerializerMethodField()
    distance_estimated = serializers.SerializerMethodField()
    same_city = serializers.SerializerMethodField()

    def get_display_name(self, obj):
        """
        Construct a readable display name from user data.
        Fallback chain: display_name -> first_name -> email prefix
        """
        user = obj.user
        
        # Priority 1: Use the display_name field if not empty
        if user.display_name and user.display_name.strip():
            return user.display_name.strip()
        
        # Fallback: Use email prefix (before @)
        return user.email.split('@')[0]

    def get_age(self, obj):
        """Get user's age."""
        return obj.user.age

    def get_photos(self, obj):
        """
        Get profile photo URLs or return a default avatar.
        Returns a list of photo URLs (strings, not objects).
        Uses normalize_media_url for consistent URL normalization (LOG-05).
        """
        from profiles.photo_storage import profile_photo_delivery_url

        photos = []
        request = self.context.get('request')

        # Get approved photos, ordered by priority
        approved_photos = obj.photos.filter(is_approved=True).order_by('order')

        if approved_photos.exists():
            for photo in approved_photos:
                normalized = profile_photo_delivery_url(photo, request)
                if normalized:
                    photos.append(normalized)

        # If no photos, use Gravatar as default avatar
        if not photos:
            import hashlib
            user = obj.user
            email_hash = hashlib.md5(user.email.lower().encode()).hexdigest()
            gravatar_url = f"https://www.gravatar.com/avatar/{email_hash}?d=identicon&s=400"
            photos.append(gravatar_url)

        return photos

    def get_is_online(self, obj):
        """Check if user is online."""
        from django.utils import timezone
        return (timezone.now() - obj.user.last_active).total_seconds() < 300

    def get_distance_km(self, obj):
        result = self._distance(obj)
        return result.km if result else None

    def _distance(self, obj):
        request = self.context.get('request')
        if not request or not hasattr(request.user, 'profile'):
            return None
        cache = self.context.setdefault('_discovery_distance_cache', {})
        key = str(obj.pk)
        if key not in cache:
            cache[key] = distance_between(request.user.profile, obj)
        return cache[key]

    def get_distance_estimated(self, obj):
        result = self._distance(obj)
        return result.estimated if result else None

    def get_same_city(self, obj):
        result = self._distance(obj)
        return result.same_city if result else False


class LikeActionSerializer(serializers.Serializer):
    """
    Serializer for like/dislike actions.
    Accepts both 'target_user_id' and 'target_profile_id' (frontend alias).
    """
    target_user_id = serializers.UUIDField(required=False)
    target_profile_id = serializers.UUIDField(required=False)

    def validate(self, data):
        # Normalise: accept target_profile_id as an alias for target_user_id
        if not data.get('target_user_id') and data.get('target_profile_id'):
            data['target_user_id'] = data['target_profile_id']
        if not data.get('target_user_id'):
            raise serializers.ValidationError(
                {'target_user_id': 'This field is required.'}
            )
        return data


class BoostSerializer(serializers.ModelSerializer):
    """
    Serializer for boosts.
    """
    is_active = serializers.SerializerMethodField()
    time_remaining_seconds = serializers.SerializerMethodField()

    class Meta:
        model = Boost
        fields = [
            'id', 'started_at', 'expires_at', 'is_active',
            'time_remaining_seconds', 'views_gained', 'likes_gained'
        ]
        read_only_fields = ['id', 'started_at', 'expires_at', 'views_gained', 'likes_gained']

    def get_is_active(self, obj):
        """Check if boost is active."""
        return obj.is_active()

    def get_time_remaining_seconds(self, obj):
        """Get remaining time in seconds."""
        from django.utils import timezone
        if obj.is_active():
            remaining = (obj.expires_at - timezone.now()).total_seconds()
            return max(0, int(remaining))
        return 0


class LikesReceivedSerializer(serializers.Serializer):
    """
    Serializer for likes received (premium feature).
    """
    user_id = serializers.UUIDField(source='from_user.id')
    display_name = serializers.CharField(source='from_user.display_name')
    age = serializers.SerializerMethodField()
    main_photo_url = serializers.SerializerMethodField()
    is_verified = serializers.BooleanField(source='from_user.is_verified')
    liked_at = serializers.DateTimeField(source='created_at')
    like_type = serializers.CharField()

    def get_age(self, obj):
        """Get user's age."""
        return obj.from_user.age

    def get_main_photo_url(self, obj):
        """Get main photo URL (normalized — LOG-05)."""
        from profiles.photo_storage import profile_photo_delivery_url
        photo = obj.from_user.profile.photos.filter(is_main=True).first()
        if not photo:
            return None
        request = self.context.get('request')
        return profile_photo_delivery_url(photo, request, thumbnail=True)


class SearchFilterSerializer(serializers.Serializer):
    """
    Serializer for discovery search filters.
    """
    age_min = serializers.IntegerField(
        min_value=18,
        max_value=99,
        required=False
    )
    age_max = serializers.IntegerField(
        min_value=18,
        max_value=99,
        required=False
    )
    distance_max_km = serializers.IntegerField(
        min_value=5,
        max_value=100,
        required=False
    )
    genders = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )
    relationship_types = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )
    verified_only = serializers.BooleanField(
        required=False,
        default=False
    )
    online_only = serializers.BooleanField(
        required=False,
        default=False
    )

    def validate(self, data):
        """Validate filter data."""
        errors = {}

        # Validate age range
        if 'age_min' in data and 'age_max' in data:
            if data['age_min'] > data['age_max']:
                errors['age_min'] = _('Minimum age must be less than or equal to maximum age.')

        valid_genders = {choice[0] for choice in Profile.GENDER_CHOICES}
        valid_relationship_types = {choice[0] for choice in Profile.RELATIONSHIP_CHOICES}

        if 'genders' in data:
            normalized_genders = []
            for value in data['genders']:
                if not isinstance(value, str):
                    errors['genders'] = _('All gender values must be strings.')
                    normalized_genders = []
                    break
                normalized_value = value.strip().lower()
                if normalized_value == 'all':
                    normalized_genders = []
                    break
                normalized_genders.append(normalized_value)

            invalid_genders = [g for g in normalized_genders if g not in valid_genders]
            if invalid_genders:
                errors['genders'] = _('Invalid gender values: %(values)s') % {
                    'values': ', '.join(invalid_genders)
                }
            elif len(set(normalized_genders)) > 1:
                errors['genders'] = _(
                    'Choose one gender or leave the list empty for everyone.'
                )
            elif 'genders' not in errors:
                # Deduplicate while preserving deterministic order
                data['genders'] = list(dict.fromkeys(normalized_genders))

        if 'relationship_types' in data:
            normalized_relationship_types = []
            for value in data['relationship_types']:
                if not isinstance(value, str):
                    errors['relationship_types'] = _('All relationship type values must be strings.')
                    normalized_relationship_types = []
                    break
                normalized_value = value.strip().lower()
                if normalized_value == 'all':
                    normalized_relationship_types = []
                    break
                normalized_relationship_types.append(normalized_value)

            invalid_relationship_types = [
                r for r in normalized_relationship_types if r not in valid_relationship_types
            ]
            if invalid_relationship_types:
                errors['relationship_types'] = _('Invalid relationship types: %(values)s') % {
                    'values': ', '.join(invalid_relationship_types)
                }
            elif 'relationship_types' not in errors:
                # Deduplicate while preserving deterministic order
                data['relationship_types'] = list(dict.fromkeys(normalized_relationship_types))

        if errors:
            raise serializers.ValidationError(errors)
        
        return data

    def update_profile_filters(self, profile):
        """Update profile with validated filter data."""
        if 'age_min' in self.validated_data:
            profile.age_min_preference = self.validated_data['age_min']
        
        if 'age_max' in self.validated_data:
            profile.age_max_preference = self.validated_data['age_max']
        
        if 'distance_max_km' in self.validated_data:
            profile.distance_max_km = self.validated_data['distance_max_km']
        
        if 'genders' in self.validated_data:
            genders = self.validated_data['genders']
            # Handle "all" case - store empty list
            if not genders:
                profile.genders_sought = []
            else:
                profile.genders_sought = genders
        
        if 'relationship_types' in self.validated_data:
            rel_types = self.validated_data['relationship_types']
            # Handle "all" case - store empty list
            if not rel_types:
                profile.relationship_types_sought = []
            else:
                profile.relationship_types_sought = rel_types
        
        if 'verified_only' in self.validated_data:
            profile.verified_only = self.validated_data['verified_only']
        
        if 'online_only' in self.validated_data:
            profile.online_only = self.validated_data['online_only']
        
        profile.save()
        return profile


class InteractionHistorySerializer(serializers.Serializer):
    """
    Serializer for interaction history entries.
    """
    id = serializers.UUIDField(read_only=True)
    profile = serializers.SerializerMethodField()
    interaction_type = serializers.CharField(read_only=True)
    liked_at = serializers.DateTimeField(source='created_at', read_only=True)
    passed_at = serializers.DateTimeField(source='created_at', read_only=True)
    is_matched = serializers.SerializerMethodField()
    match_id = serializers.SerializerMethodField()
    can_revoke = serializers.SerializerMethodField()
    can_rematch = serializers.SerializerMethodField()
    can_reconsider = serializers.SerializerMethodField()
    
    def get_profile(self, obj):
        """Get the target user's profile."""
        # Use the DiscoveryProfileSerializer from this same file
        request = self.context.get('request')
        return DiscoveryProfileSerializer(
            obj.target_user.profile,
            context={'request': request}
        ).data
    
    def get_is_matched(self, obj):
        """Check if this interaction led to a match."""
        if obj.interaction_type == InteractionHistory.DISLIKE:
            return False
        
        return self._active_match_id(obj) is not None
    
    def get_match_id(self, obj):
        """Get match ID if exists."""
        if obj.interaction_type == InteractionHistory.DISLIKE:
            return None
        
        match_id = self._active_match_id(obj)
        return str(match_id) if match_id else None

    def _active_match_id(self, obj):
        """Use the batched context prepared by the history view when present."""
        active_matches = self.context.get('active_match_ids_by_target')
        if active_matches is not None:
            return active_matches.get(obj.target_user_id)

        request = self.context.get('request')
        if not request or not request.user:
            return None
        return Match.objects.filter(
            Q(user1=request.user, user2=obj.target_user) |
            Q(user1=obj.target_user, user2=request.user),
            status=Match.ACTIVE,
        ).values_list('id', flat=True).first()
    
    def get_can_rematch(self, obj):
        """Check if user can rematch (for likes)."""
        if obj.interaction_type == InteractionHistory.DISLIKE:
            return False
        
        is_matched = self.get_is_matched(obj)
        return not is_matched and not obj.is_revoked
    
    def get_can_reconsider(self, obj):
        """Check if user can reconsider (for dislikes)."""
        return not obj.is_revoked

    def get_can_revoke(self, obj):
        """A matched like must be removed through the match lifecycle."""
        if obj.is_revoked:
            return False
        if obj.interaction_type in (InteractionHistory.LIKE, InteractionHistory.SUPER_LIKE):
            return not self.get_is_matched(obj)
        return True


class BulkRevokeInteractionsSerializer(serializers.Serializer):
    """Strict input contract for atomic history revocation."""

    HISTORY_LIKES = 'likes'
    HISTORY_PASSES = 'passes'
    HISTORY_CHOICES = ((HISTORY_LIKES, HISTORY_LIKES), (HISTORY_PASSES, HISTORY_PASSES))
    MATCH_ALL = 'all'
    MATCH_MATCHED = 'matched'
    MATCH_UNMATCHED = 'unmatched'
    MATCH_CHOICES = (
        (MATCH_ALL, MATCH_ALL),
        (MATCH_MATCHED, MATCH_MATCHED),
        (MATCH_UNMATCHED, MATCH_UNMATCHED),
    )

    history_type = serializers.ChoiceField(choices=HISTORY_CHOICES)
    interaction_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=False, max_length=100
    )
    select_all = serializers.BooleanField(default=False)
    q = serializers.CharField(required=False, allow_blank=True, max_length=100)
    match_state = serializers.ChoiceField(choices=MATCH_CHOICES, default=MATCH_ALL)
    include_revoked = serializers.BooleanField(default=False)

    def validate(self, attrs):
        select_all = attrs['select_all']
        interaction_ids = attrs.get('interaction_ids', [])
        if select_all == bool(interaction_ids):
            raise serializers.ValidationError(
                'Provide interaction_ids or select_all=true, but not both.'
            )
        return attrs


class MarkMatchesSeenSerializer(serializers.Serializer):
    """A missing list means all active matches of the authenticated user."""

    match_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True, max_length=100
    )

    def validate_match_ids(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError('Each match can be supplied only once.')
        return value


class InteractionStatsSerializer(serializers.Serializer):
    """
    Serializer for interaction statistics.
    """
    total_likes = serializers.IntegerField()
    total_super_likes = serializers.IntegerField()
    total_dislikes = serializers.IntegerField()
    total_matches = serializers.IntegerField()
    like_to_match_ratio = serializers.FloatField()
    total_interactions_today = serializers.IntegerField()
    daily_limit = serializers.IntegerField()
    remaining_today = serializers.IntegerField()
