"""
Discovery views for matching app.
"""
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.db import transaction
import logging
from django.utils import timezone

from .services import RecommendationService, MatchingService
from .serializers import (
    DiscoveryProfileSerializer,
    LikeActionSerializer,
    BoostSerializer,
    LikesReceivedSerializer
)
from .models import Like, Boost

logger = logging.getLogger('hivmeet.matching')
User = get_user_model()


class DiscoveryPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_discovery_profiles(request):
    """
    Get recommended profiles for discovery.
    
    GET /api/v1/discovery/profiles
    """
    # Get query parameters
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 10))
    
    # Calculate offset
    offset = (page - 1) * page_size
    
    # Get recommendations
    profiles = RecommendationService.get_recommendations(
        user=request.user,
        limit=page_size,
        offset=offset
    )
    
    # Serialize profiles
    serializer = DiscoveryProfileSerializer(profiles, many=True)
    
    # Build response with pagination info
    response_data = {
        'count': len(profiles),  # This would be total count in production
        'next': f"?page={page + 1}" if len(profiles) == page_size else None,
        'previous': f"?page={page - 1}" if page > 1 else None,
        'results': serializer.data
    }
    
    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@transaction.atomic
def like_profile(request):
    """
    Like a profile.
    
    POST /api/v1/discovery/interactions/like
    """
    serializer = LikeActionSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        target_user = User.objects.get(id=serializer.validated_data['target_user_id'])
    except User.DoesNotExist:
        return Response({
            'error': True,
            'message': _('User not found.')
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Process like
    success, is_match, error_msg = MatchingService.like_profile(
        from_user=request.user,
        to_user=target_user
    )
    
    if not success:
        return Response({
            'error': True,
            'message': error_msg
        }, status=status.HTTP_400_BAD_REQUEST if 'limit' in error_msg else status.HTTP_429_TOO_MANY_REQUESTS)
    
    if is_match:
        # Get match details
        from .models import Match
        match = Match.get_match_between(request.user, target_user)
        
        return Response({
            'status': 'matched',
            'match_id': str(match.id),
            'matched_user_info': {
                'user_id': str(target_user.id),
                'display_name': target_user.display_name,
                'main_photo_url': target_user.profile.photos.filter(
                    is_main=True
                ).first().photo_url if hasattr(target_user, 'profile') else None
            }
        }, status=status.HTTP_200_OK)
    
    return Response({
        'status': 'liked'
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def dislike_profile(request):
    """
    Dislike (pass) a profile.
    
    POST /api/v1/discovery/interactions/dislike
    """
    serializer = LikeActionSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        target_user = User.objects.get(id=serializer.validated_data['target_user_id'])
    except User.DoesNotExist:
        return Response({
            'error': True,
            'message': _('User not found.')
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Process dislike
    success, error_msg = MatchingService.dislike_profile(
        from_user=request.user,
        to_user=target_user
    )
    
    if not success:
        return Response({
            'error': True,
            'message': error_msg
        }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({
        'status': 'disliked'
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@transaction.atomic
def superlike_profile(request):
    """
    Super like a profile (premium feature).
    
    POST /api/v1/discovery/interactions/superlike
    """
    if not request.user.is_premium:
        return Response({
            'error': True,
            'message': _('Super likes are a premium feature.')
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = LikeActionSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        target_user = User.objects.get(id=serializer.validated_data['target_user_id'])
    except User.DoesNotExist:
        return Response({
            'error': True,
            'message': _('User not found.')
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Process super like
    success, is_match, error_msg = MatchingService.like_profile(
        from_user=request.user,
        to_user=target_user,
        is_super_like=True
    )
    
    if not success:
        return Response({
            'error': True,
            'message': error_msg
        }, status=status.HTTP_400_BAD_REQUEST if 'limit' not in error_msg else status.HTTP_429_TOO_MANY_REQUESTS)
    
    if is_match:
        # Get match details
        from .models import Match
        match = Match.get_match_between(request.user, target_user)
        
        return Response({
            'status': 'matched_with_superlike',
            'match_id': str(match.id),
            'matched_user_info': {
                'user_id': str(target_user.id),
                'display_name': target_user.display_name,
                'main_photo_url': target_user.profile.photos.filter(
                    is_main=True
                ).first().photo_url if hasattr(target_user, 'profile') else None
            }
        }, status=status.HTTP_200_OK)
    
    return Response({
        'status': 'superliked'
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def rewind_last_swipe(request):
    """
    Rewind the last swipe (premium feature).
    
    POST /api/v1/discovery/interactions/rewind
    """
    if not request.user.is_premium:
        return Response({
            'error': True,
            'message': _('Rewind is a premium feature.')
        }, status=status.HTTP_403_FORBIDDEN)
    
    success, profile_data, error_msg = MatchingService.rewind_last_action(request.user)
    
    if not success:
        return Response({
            'error': True,
            'message': error_msg
        }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({
        'status': 'rewound',
        'previous_profile': profile_data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_likes_received(request):
    """
    Get list of users who liked you (premium feature).
    
    GET /api/v1/discovery/interactions/liked-me
    """
    if not request.user.is_premium:
        return Response({
            'error': True,
            'message': _('Viewing likes is a premium feature.')
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get likes received
    likes = Like.objects.filter(
        to_user=request.user
    ).select_related(
        'from_user__profile'
    ).order_by('-created_at')
    
    # Paginate
    paginator = DiscoveryPagination()
    page = paginator.paginate_queryset(likes, request)
    
    # Serialize
    serializer = LikesReceivedSerializer(page, many=True)
    
    return paginator.get_paginated_response(serializer.data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@transaction.atomic
def activate_boost(request):
    """
    Activate a profile boost (premium feature).
    
    POST /api/v1/discovery/boost/activate
    """
    if not request.user.is_premium:
        return Response({
            'error': True,
            'message': _('Boost is a premium feature.')
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Check if user has an active boost
    active_boost = Boost.objects.filter(
        user=request.user,
        expires_at__gt=timezone.now()
    ).first()
    
    if active_boost:
        return Response({
            'error': True,
            'message': _('You already have an active boost.')
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if user has a free boost available
    # (1 free boost per month for premium users)
    from datetime import timedelta
    month_ago = timezone.now() - timedelta(days=30)
    recent_boosts = Boost.objects.filter(
        user=request.user,
        started_at__gte=month_ago
    ).count()
    
    if recent_boosts >= 1:
        return Response({
            'error': True,
            'message': _('You have already used your free boost this month.')
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Create boost
    boost = Boost.objects.create(user=request.user)
    
    logger.info(f"Boost activated for user: {request.user.email}")
    
    serializer = BoostSerializer(boost)
    
    return Response({
        'status': 'boost_activated',
        'boost': serializer.data
    }, status=status.HTTP_200_OK)