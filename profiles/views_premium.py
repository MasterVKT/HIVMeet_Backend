"""
Premium feature views for profiles app.
"""
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
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
                target_user=self.request.user,
                is_like=True
            ).values_list('user', flat=True)
        ).select_related('user')
    
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
                target_user=self.request.user,
                is_like=True,
                is_super_like=True
            ).values_list('user', flat=True)
        ).select_related('user')
    
    def list(self, request, *args, **kwargs):
        if not is_premium_user(request.user):
            return premium_required_response()
        
        return super().list(request, *args, **kwargs)


class PremiumFeaturesStatusView(APIView):
    """
    Get premium features status for current user.
    GET /api/v1/profiles/premium-status/
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        if is_premium_user(user):
            limits = get_premium_limits(user)
            subscription = get_user_subscription(user)
            
            return Response({
                'is_premium': True,
                'subscription_type': subscription.plan.name if subscription else 'unknown',
                'premium_until': user.premium_until.isoformat() if user.premium_until else None,
                'features': limits['limits']['features'],
                'usage': {
                    'super_likes': {
                        'used': limits['limits']['super_likes']['used'],
                        'remaining': limits['limits']['super_likes']['remaining'],
                        'total': limits['limits']['super_likes']['total']
                    },
                    'boosts': {
                        'used': limits['limits']['boosts']['used'],
                        'remaining': limits['limits']['boosts']['remaining'],
                        'total': limits['limits']['boosts']['total']
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
                    'super_likes': {'used': 0, 'remaining': 0, 'total': 0},
                    'boosts': {'used': 0, 'remaining': 0, 'total': 0}
                }
            }, status=status.HTTP_200_OK)
