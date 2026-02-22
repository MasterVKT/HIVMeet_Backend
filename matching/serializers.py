"""
Serializers for matching app with premium features integration.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

from .models import Like, Match, Boost, InteractionHistory
from profiles.serializers import PublicProfileSerializer
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

    class Meta:
        model = Match
        fields = [
            'id', 'matched_user', 'created_at',
            'unread_count_for_me'
        ]
        read_only_fields = ['id', 'created_at']

    def get_matched_user(self, obj):
        """Get the other user in the match."""
        request = self.context.get('request')
        if request and request.user:
            other_user = obj.user2 if obj.user1 == request.user else obj.user1
            from profiles.serializers import PublicProfileSerializer
            return PublicProfileSerializer(
                other_user.profile,
                context=self.context
            ).data
        return None

    def get_unread_count_for_me(self, obj):
        """Get unread message count for current user."""
        # This would be implemented with messaging app
        return 0


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
        """Calculate distance between users."""
        request = self.context.get('request')
        if request and request.user and hasattr(request.user, 'profile'):
            user_profile = request.user.profile
            if user_profile.latitude and user_profile.longitude and obj.latitude and obj.longitude:
                # Calculate distance using Haversine formula
                from math import radians, cos, sin, asin, sqrt

                lat1, lon1 = radians(user_profile.latitude), radians(user_profile.longitude)
                lat2, lon2 = radians(obj.latitude), radians(obj.longitude)

                dlon = lon2 - lon1
                dlat = lat2 - lat1
                a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                c = 2 * asin(sqrt(a))
                r = 6371  # Radius of earth in kilometers

                return round(c * r, 1)
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
        Handles both absolute URLs and relative paths, converting them to absolute URLs.
        """
        from django.conf import settings
        from rest_framework.request import Request
        
        photos = []
        
        # Get approved photos, ordered by priority
        approved_photos = obj.photos.filter(is_approved=True).order_by('order')
        
        if approved_photos.exists():
            # Return main photo URLs
            for photo in approved_photos:
                if photo.photo_url:
                    url = photo.photo_url.strip()
                    
                    # Check if it's already an absolute URL
                    if url.startswith('http://') or url.startswith('https://'):
                        photos.append(url)
                    else:
                        # Convert relative path to absolute URL using request context
                        request = self.context.get('request')
                        if request:
                            # Build absolute URL using request
                            if url.startswith('/'):
                                # Already has leading slash
                                absolute_url = request.build_absolute_uri(url)
                            else:
                                # Add /media/ prefix if not present
                                media_path = f"/media/{url}" if not url.startswith('media/') else f"/{url}"
                                absolute_url = request.build_absolute_uri(media_path)
                            photos.append(absolute_url)
                        else:
                            # Fallback without request context
                            if url.startswith('/'):
                                photos.append(url)
                            else:
                                photos.append(f"/media/{url}" if not url.startswith('media/') else f"/{url}")
        
        # If no photos, use Gravatar as default avatar
        if not photos:
            import hashlib
            user = obj.user
            # Create a Gravatar URL using email hash
            email_hash = hashlib.md5(user.email.lower().encode()).hexdigest()
            gravatar_url = f"https://www.gravatar.com/avatar/{email_hash}?d=identicon&s=400"
            photos.append(gravatar_url)
        
        return photos

    def get_is_online(self, obj):
        """Check if user is online."""
        from django.utils import timezone
        return (timezone.now() - obj.user.last_active).total_seconds() < 300

    def get_distance_km(self, obj):
        """Get distance from current user."""
        # This would be calculated in the service
        return getattr(obj, 'distance_km', None)


class LikeActionSerializer(serializers.Serializer):
    """
    Serializer for like/dislike actions.
    """
    target_user_id = serializers.UUIDField()


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
        """Get main photo URL."""
        photo = obj.from_user.profile.photos.filter(is_main=True).first()
        return photo.thumbnail_url if photo else None


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
        # Validate age range
        if 'age_min' in data and 'age_max' in data:
            if data['age_min'] > data['age_max']:
                raise serializers.ValidationError({
                    'age_min': _('Minimum age must be less than or equal to maximum age.')
                })
        
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
            if 'all' in genders or not genders:
                profile.genders_sought = []
            else:
                profile.genders_sought = genders
        
        if 'relationship_types' in self.validated_data:
            rel_types = self.validated_data['relationship_types']
            # Handle "all" case - store empty list
            if 'all' in rel_types or not rel_types:
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
        
        request = self.context.get('request')
        if request and request.user:
            match = Match.objects.filter(
                Q(user1=request.user, user2=obj.target_user) |
                Q(user1=obj.target_user, user2=request.user),
                status=Match.ACTIVE
            ).first()
            return bool(match)
        return False
    
    def get_match_id(self, obj):
        """Get match ID if exists."""
        if obj.interaction_type == InteractionHistory.DISLIKE:
            return None
        
        request = self.context.get('request')
        if request and request.user:
            match = Match.objects.filter(
                Q(user1=request.user, user2=obj.target_user) |
                Q(user1=obj.target_user, user2=request.user),
                status=Match.ACTIVE
            ).first()
            return str(match.id) if match else None
        return None
    
    def get_can_rematch(self, obj):
        """Check if user can rematch (for likes)."""
        if obj.interaction_type == InteractionHistory.DISLIKE:
            return False
        
        is_matched = self.get_is_matched(obj)
        return not is_matched and not obj.is_revoked
    
    def get_can_reconsider(self, obj):
        """Check if user can reconsider (for dislikes)."""
        return not obj.is_revoked


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
