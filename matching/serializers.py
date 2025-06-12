"""
Serializers for matching app.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from .models import Like, Match, Boost
from profiles.serializers import PublicProfileSerializer

User = get_user_model()


class LikeSerializer(serializers.ModelSerializer):
    """
    Serializer for likes.
    """
    from_user = serializers.StringRelatedField()
    to_user = serializers.StringRelatedField()
    
    class Meta:
        model = Like
        fields = ['id', 'from_user', 'to_user', 'like_type', 'created_at']
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
            'id', 'matched_user', 'status', 'created_at',
            'last_message_at', 'last_message_preview',
            'unread_count_for_me'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_matched_user(self, obj):
        """Get the other user in the match."""
        request = self.context.get('request')
        if request and request.user:
            other_user = obj.get_other_user(request.user)
            return {
                'user_id': str(other_user.id),
                'display_name': other_user.display_name,
                'age': other_user.age,
                'main_photo_url': other_user.profile.photos.filter(
                    is_main=True
                ).first().photo_url if other_user.profile.photos.exists() else None,
                'is_verified': other_user.is_verified,
                'last_active_display': self._get_last_active_display(other_user)
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
    display_name = serializers.CharField(source='user.display_name')
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
    
    def get_age(self, obj):
        """Get user's age."""
        return obj.user.age
    
    def get_photos(self, obj):
        """Get profile photos."""
        photos = []
        for photo in obj.photos.filter(is_approved=True).order_by('order'):
            photos.append({
                'url': photo.photo_url,
                'thumbnail_url': photo.thumbnail_url,
                'is_main': photo.is_main
            })
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