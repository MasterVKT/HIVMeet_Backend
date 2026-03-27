"""
Premium feature views for profiles app.
"""
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.conf import settings
import logging

from .models import Profile
from .serializers import PublicProfileSerializer
from subscriptions.utils import (
    is_premium_user, 
    get_user_subscription,
    premium_required_response,
    get_premium_limits
)
from matching.models import Like

logger = logging.getLogger('hivmeet.profiles')
User = get_user_model()


class LikesReceivedView(generics.ListAPIView):
    """
    Get list of users who liked the current user (Premium only).
    GET /api/v1/profiles/likes-received/
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PublicProfileSerializer
    
    def get_queryset(self):
        if not is_premium_user(self.request.user):
            # Return empty queryset for non-premium users
            return Profile.objects.none()
        
        # Get users who liked the current user
        return Profile.objects.filter(
            user__in=Like.objects.filter(
                to_user=self.request.user
            ).values_list('from_user', flat=True)
        ).select_related('user').order_by('-user__date_joined')
    
    def list(self, request, *args, **kwargs):
        if not is_premium_user(request.user):
            return premium_required_response()
        
        return super().list(request, *args, **kwargs)


class SuperLikesReceivedView(generics.ListAPIView):
    """
    Get list of users who super liked the current user (Premium only).
    GET /api/v1/profiles/super-likes-received/
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PublicProfileSerializer
    
    def get_queryset(self):
        if not is_premium_user(self.request.user):
            return Profile.objects.none()
        
        # Get users who super liked the current user
        return Profile.objects.filter(
            user__in=Like.objects.filter(
                to_user=self.request.user,
                like_type=Like.SUPER
            ).values_list('from_user', flat=True)
        ).select_related('user').order_by('-user__date_joined')
    
    def list(self, request, *args, **kwargs):
        if not is_premium_user(request.user):
            return premium_required_response()
        
        return super().list(request, *args, **kwargs)


class PremiumFeaturesStatusView(APIView):
    """
    Get premium features status for current user.
    GET /api/v1/profiles/premium-status/
    
    Response structure:
    {
        "is_premium": bool,
        "subscription_type": str or null,
        "premium_until": datetime or null,
        "features": {
            "unlimited_likes": bool,
            "can_see_likers": bool,
            "can_rewind": bool,
            "media_messaging": bool,
            "calls": bool
        },
        "usage": {
            "super_likes": {
                "total": int,
                "remaining": int,
                "used": int,
                "reset_at": datetime or null
            },
            "boosts": {
                "total": int,
                "remaining": int,
                "used": int,
                "reset_at": datetime or null
            }
        }
    }
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        try:
            if is_premium_user(user):
                limits = get_premium_limits(user)
                subscription = get_user_subscription(user)
                
                # Safely extract nested dictionaries with defaults
                super_likes_limits = limits.get('limits', {}).get('super_likes', {})
                boosts_limits = limits.get('limits', {}).get('boosts', {})
                features = limits.get('limits', {}).get('features', {})
                
                # Calculate 'used' from total - remaining
                super_likes_total = super_likes_limits.get('total', 0)
                super_likes_remaining = super_likes_limits.get('remaining', 0)
                super_likes_used = max(0, super_likes_total - super_likes_remaining)
                
                boosts_total = boosts_limits.get('total', 0)
                boosts_remaining = boosts_limits.get('remaining', 0)
                boosts_used = max(0, boosts_total - boosts_remaining)
                
                return Response({
                    'is_premium': True,
                    'subscription_type': subscription.plan.name if subscription else 'unknown',
                    'premium_until': user.premium_until.isoformat() if user.premium_until else None,
                    'features': {
                        'unlimited_likes': features.get('unlimited_likes', False),
                        'can_see_likers': features.get('can_see_likers', False),
                        'can_rewind': features.get('can_rewind', False),
                        'media_messaging': features.get('media_messaging', False),
                        'calls': features.get('calls', False)
                    },
                    'usage': {
                        'super_likes': {
                            'total': super_likes_total,
                            'remaining': super_likes_remaining,
                            'used': super_likes_used,
                            'reset_at': super_likes_limits.get('reset_date')
                        },
                        'boosts': {
                            'total': boosts_total,
                            'remaining': boosts_remaining,
                            'used': boosts_used,
                            'reset_at': boosts_limits.get('reset_date')
                        }
                    }
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'is_premium': False,
                    'subscription_type': None,
                    'premium_until': None,
                    'features': {
                        'unlimited_likes': False,
                        'can_see_likers': False,
                        'can_rewind': False,
                        'media_messaging': False,
                        'calls': False
                    },
                    'usage': {
                        'super_likes': {'total': 0, 'remaining': 0, 'used': 0, 'reset_at': None},
                        'boosts': {'total': 0, 'remaining': 0, 'used': 0, 'reset_at': None}
                    }
                }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(
                f"Error fetching premium status - User: {user.id} - Error: {str(e)}",
                exc_info=True
            )
            return Response({
                'error': 'subscription_fetch_failed',
                'message': _('Impossible de récupérer les informations premium'),
                'detail': str(e) if getattr(settings, 'DEBUG', False) else _('Erreur serveur interne')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
