"""
Premium feature views for matching app.
"""
import logging
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.models import User
from .models import Like, Match, Boost
from subscriptions.middleware import premium_required, check_feature_limit
from subscriptions.utils import (
    is_premium_user, 
    check_feature_availability, 
    consume_premium_feature,
    premium_required_response
)

logger = logging.getLogger('hivmeet.matching')


class RewindLastSwipeView(APIView):
    """
    Rewind last swipe (Premium feature).
    POST /api/v1/matches/rewind/
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @premium_required
    def post(self, request):
        try:
            # Get the last like from the user
            last_like = Like.objects.filter(user=request.user).order_by('-created_at').first()
            
            if not last_like:
                return Response({
                    'success': False,
                    'message': _('No swipe to rewind')
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if it was created within the last 24 hours
            if (timezone.now() - last_like.created_at).days > 0:
                return Response({
                    'success': False,
                    'message': _('Cannot rewind swipes older than 24 hours')
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Delete the like and any potential match
            target_user = last_like.target_user
            with transaction.atomic():
                # Remove potential match
                Match.objects.filter(
                    user1=request.user, user2=target_user
                ).delete()
                Match.objects.filter(
                    user1=target_user, user2=request.user
                ).delete()
                
                # Delete the like
                last_like.delete()
                
                logger.info(f"User {request.user.id} rewound swipe on {target_user.id}")
            
            return Response({
                'success': True,
                'message': _('Swipe rewound successfully'),
                'rewound_user_id': str(target_user.id)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Rewind failed for user {request.user.id}: {str(e)}")
            return Response({
                'success': False,
                'message': _('Failed to rewind swipe')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SendSuperLikeView(APIView):
    """
    Send a super like (Premium feature with daily limit).
    POST /api/v1/matches/{user_id}/super-like/
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @check_feature_limit('super_like', use_feature=True)
    def post(self, request, user_id):
        try:
            target_user = get_object_or_404(User, id=user_id)
            
            # Check if already liked/disliked
            existing_like = Like.objects.filter(
                user=request.user, 
                target_user=target_user
            ).first()
            
            if existing_like:
                return Response({
                    'success': False,
                    'message': _('You have already interacted with this user')
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create super like
            with transaction.atomic():
                like = Like.objects.create(
                    user=request.user,
                    target_user=target_user,
                    is_like=True,
                    is_super_like=True
                )
                
                # Check for match
                reverse_like = Like.objects.filter(
                    user=target_user,
                    target_user=request.user,
                    is_like=True
                ).first()
                
                match_created = False
                if reverse_like:
                    match = Match.objects.create(
                        user1=request.user,
                        user2=target_user
                    )
                    match_created = True
                    logger.info(f"Super like match created between {request.user.id} and {target_user.id}")
                
                logger.info(f"Super like sent from {request.user.id} to {target_user.id}")
            
            # Send notification (handled by signal)
            
            return Response({
                'success': True,
                'message': _('Super like sent successfully'),
                'match_created': match_created
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Super like failed from {request.user.id} to {user_id}: {str(e)}")
            return Response({
                'success': False,
                'message': _('Failed to send super like')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProfileBoostView(APIView):
    """
    Boost profile visibility (Premium feature with monthly limit).
    POST /api/v1/profiles/boost/
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @check_feature_limit('boost', use_feature=True)
    def post(self, request):
        try:
            # Check if user already has an active boost
            active_boost = Boost.objects.filter(
                user=request.user,
                is_active=True,
                expires_at__gt=timezone.now()
            ).first()
            
            if active_boost:
                return Response({
                    'success': False,
                    'message': _('You already have an active boost'),
                    'expires_at': active_boost.expires_at.isoformat()
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create boost (30 minutes duration)
            boost_duration = timezone.timedelta(minutes=30)
            boost = Boost.objects.create(
                user=request.user,
                expires_at=timezone.now() + boost_duration,
                is_active=True
            )
            
            logger.info(f"Profile boost activated for user {request.user.id}")
            
            return Response({
                'success': True,
                'message': _('Profile boost activated'),
                'boost_id': str(boost.id),
                'expires_at': boost.expires_at.isoformat(),
                'duration_minutes': 30
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Profile boost failed for user {request.user.id}: {str(e)}")
            return Response({
                'success': False,
                'message': _('Failed to activate boost')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)