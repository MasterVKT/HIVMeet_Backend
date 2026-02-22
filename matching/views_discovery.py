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
    LikesReceivedSerializer,
    SearchFilterSerializer
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
    user = request.user
    
    # LOG 1: Utilisateur
    logger.info(f"🔍 Discovery request - User: {user.display_name if hasattr(user, 'display_name') else user.email} ({user.email})")
    logger.info(f"🔍 Is authenticated: {user.is_authenticated}")
    
    if not user.is_authenticated:
        logger.error("❌ User not authenticated for discovery endpoint")
        return Response({
            'error': True,
            'message': _('Authentication required')
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    # Get query parameters
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 10))
    
    # Calculate offset
    offset = (page - 1) * page_size
    
    # LOG 2: Préférences utilisateur
    try:
        user_profile = user.profile
        logger.info(f"📋 User preferences:")
        logger.info(f"   - Age range: {user_profile.age_min_preference}-{user_profile.age_max_preference}")
        logger.info(f"   - Max distance: {user_profile.distance_max_km}km")
        logger.info(f"   - Genders sought: {user_profile.genders_sought}")
        logger.info(f"   - Verified only: {user_profile.verified_only}")
        logger.info(f"   - Online only: {user_profile.online_only}")
        logger.info(f"   - Allow in discovery: {user_profile.allow_profile_in_discovery}")
    except Exception as e:
        logger.warning(f"⚠️  Could not log user preferences: {str(e)}")
    
    # Get recommendations
    profiles = RecommendationService.get_recommendations(
        user=user,
        limit=page_size,
        offset=offset
    )
    
    # LOG 3: Résultats
    logger.info(f"✅ Recommendations service returned: {len(profiles)} profiles")
    
    # Serialize profiles with request context for proper URL handling
    serializer = DiscoveryProfileSerializer(
        profiles, 
        many=True,
        context={'request': request}
    )
    
    # LOG 4: Réponse finale
    logger.info(f"📤 Sending response - count: {len(profiles)}, page: {page}, page_size: {page_size}")
    
    # Build response with pagination info (standardised keys)
    return Response({
        'count': len(profiles),  # TODO: remplacer par total réel si dispo
        'next': f"?page={page + 1}&page_size={page_size}" if len(profiles) == page_size else None,
        'previous': f"?page={page - 1}&page_size={page_size}" if page > 1 else None,
        'results': serializer.data
    }, status=status.HTTP_200_OK)


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
        
        # Get updated counters
        daily_limit = MatchingService.get_daily_like_limit(request.user)
        super_likes_remaining = MatchingService.get_super_likes_remaining(request.user)
        
        return Response({
            'status': 'matched',
            'match_id': str(match.id),
            'matched_user_info': {
                'user_id': str(target_user.id),
                'display_name': target_user.display_name,
                'main_photo_url': target_user.profile.photos.filter(
                    is_main=True
                ).first().photo_url if hasattr(target_user, 'profile') else None
            },
            'daily_likes_remaining': daily_limit.get('remaining_likes', 0),
            'super_likes_remaining': super_likes_remaining
        }, status=status.HTTP_200_OK)
    
    # Get updated counters
    daily_limit = MatchingService.get_daily_like_limit(request.user)
    super_likes_remaining = MatchingService.get_super_likes_remaining(request.user)
    
    # Debug logging
    logger.info(f"✅ Like successful - User: {request.user.id}, is_premium: {getattr(request.user, 'is_premium', False)}, is_verified: {getattr(request.user, 'is_verified', False)}, Remaining likes: {daily_limit.get('remaining_likes', 0)}")
    
    return Response({
        'status': 'liked',
        'daily_likes_remaining': daily_limit.get('remaining_likes', 0),
        'super_likes_remaining': super_likes_remaining
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
    
    # Get updated counters
    daily_limit = MatchingService.get_daily_like_limit(request.user)
    super_likes_remaining = MatchingService.get_super_likes_remaining(request.user)
    
    return Response({
        'status': 'disliked',
        'daily_likes_remaining': daily_limit.get('remaining_likes', 0),
        'super_likes_remaining': super_likes_remaining
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
        
        # Get updated counters
        daily_limit = MatchingService.get_daily_like_limit(request.user)
        super_likes_remaining = MatchingService.get_super_likes_remaining(request.user)
        
        return Response({
            'status': 'matched_with_superlike',
            'match_id': str(match.id),
            'matched_user_info': {
                'user_id': str(target_user.id),
                'display_name': target_user.display_name,
                'main_photo_url': target_user.profile.photos.filter(
                    is_main=True
                ).first().photo_url if hasattr(target_user, 'profile') else None
            },
            'daily_likes_remaining': daily_limit.get('remaining_likes', 0),
            'super_likes_remaining': super_likes_remaining
        }, status=status.HTTP_200_OK)
    
    # Get updated counters
    daily_limit = MatchingService.get_daily_like_limit(request.user)
    super_likes_remaining = MatchingService.get_super_likes_remaining(request.user)
    
    return Response({
        'status': 'superliked',
        'daily_likes_remaining': daily_limit.get('remaining_likes', 0),
        'super_likes_remaining': super_likes_remaining
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


@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
@transaction.atomic
def update_discovery_filters(request):
    """
    Update discovery search filters.
    
    PUT /api/v1/discovery/filters
    
    Body:
    {
        "age_min": 25,
        "age_max": 40,
        "distance_max_km": 50,
        "genders": ["female", "non-binary"] or ["all"],
        "relationship_types": ["serious", "casual"] or ["all"],
        "verified_only": false,
        "online_only": false
    }
    """
    logger.info(f"📝 Updating discovery filters for user: {request.user.id}")
    
    # Check if user has a profile
    if not hasattr(request.user, 'profile'):
        return Response({
            'error': True,
            'message': _('Profile not found.')
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Validate input
    serializer = SearchFilterSerializer(data=request.data)
    
    if not serializer.is_valid():
        logger.warning(f"❌ Invalid filter data: {serializer.errors}")
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Update profile filters
    try:
        profile = serializer.update_profile_filters(request.user.profile)
        
        logger.info(f"✅ Filters updated successfully for user: {request.user.id}")
        logger.info(f"   - Age range: {profile.age_min_preference}-{profile.age_max_preference}")
        logger.info(f"   - Max distance: {profile.distance_max_km}km")
        logger.info(f"   - Genders: {profile.genders_sought}")
        logger.info(f"   - Relationship types: {profile.relationship_types_sought}")
        logger.info(f"   - Verified only: {profile.verified_only}")
        logger.info(f"   - Online only: {profile.online_only}")
        
        return Response({
            'status': 'success',
            'message': _('Filters updated successfully'),
            'filters': {
                'age_min': profile.age_min_preference,
                'age_max': profile.age_max_preference,
                'distance_max_km': profile.distance_max_km,
                'genders': profile.genders_sought if profile.genders_sought else ['all'],
                'relationship_types': profile.relationship_types_sought if profile.relationship_types_sought else ['all'],
                'verified_only': profile.verified_only,
                'online_only': profile.online_only
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ Error updating filters: {str(e)}")
        return Response({
            'error': True,
            'message': _('An error occurred while updating filters.')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_discovery_filters(request):
    """
    Get current discovery search filters.
    
    GET /api/v1/discovery/filters
    """
    logger.info(f"📖 Getting discovery filters for user: {request.user.id}")
    
    # Check if user has a profile
    if not hasattr(request.user, 'profile'):
        return Response({
            'error': True,
            'message': _('Profile not found.')
        }, status=status.HTTP_404_NOT_FOUND)
    
    profile = request.user.profile
    
    return Response({
        'filters': {
            'age_min': profile.age_min_preference,
            'age_max': profile.age_max_preference,
            'distance_max_km': profile.distance_max_km,
            'genders': profile.genders_sought if profile.genders_sought else ['all'],
            'relationship_types': profile.relationship_types_sought if profile.relationship_types_sought else ['all'],
            'verified_only': profile.verified_only,
            'online_only': profile.online_only
        }
    }, status=status.HTTP_200_OK)