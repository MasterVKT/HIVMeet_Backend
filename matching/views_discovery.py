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
from .rewind_service import InteractionRewindService, RewindRejected
from .daily_likes_service import DailyLikesService
from profiles.photo_storage import profile_photo_delivery_url
from .interaction_service import InteractionService
from .serializers import (
    DiscoveryProfileSerializer,
    LikeActionSerializer,
    BoostSerializer,
    LikesReceivedSerializer,
    SearchFilterSerializer
)
from .models import Like, Boost, InteractionHistory
from subscriptions.utils import check_feature_availability

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
    
    logger.info("Discovery request received")
    
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
    
    # Obtenir les informations de limite quotidienne pour le frontend
    daily_likes_info = DailyLikesService.get_status_summary(user)
    
    # Build response with pagination info (standardised keys)
    return Response({
        'count': len(profiles),
        'next': f"?page={page + 1}&page_size={page_size}" if len(profiles) == page_size else None,
        'previous': f"?page={page - 1}&page_size={page_size}" if page > 1 else None,
        'results': serializer.data,
        # Informations de limite quotidienne pour le frontend
        'daily_likes_remaining': daily_likes_info.get('daily_likes_remaining'),
        'daily_likes_limit': daily_likes_info.get('daily_likes_limit'),
        'daily_likes_used_today': daily_likes_info.get('likes_used_today'),
        'daily_likes_reset_at': daily_likes_info.get('reset_at'),
        'is_premium': daily_likes_info.get('is_premium'),
        'super_likes_remaining': daily_likes_info.get('super_likes_remaining'),
    }, status=status.HTTP_200_OK)


_REWINDABLE_INTERACTION_TYPES = (
    InteractionHistory.LIKE,
    InteractionHistory.SUPER_LIKE,
    InteractionHistory.DISLIKE,
)


def _rewind_metadata(user, target_user):
    """Attach a stable action id to every swipe response."""
    interaction = (
        InteractionHistory.objects.filter(
            user=user,
            target_user=target_user,
            interaction_type__in=_REWINDABLE_INTERACTION_TYPES,
            is_revoked=False,
        )
        .order_by('-created_at')
        .first()
    )
    if interaction is None:
        return {
            'interaction_id': None,
            'can_rewind': False,
            'rewind_expires_at': None,
        }

    feature = check_feature_availability(user, 'rewind')
    can_rewind = (
        bool(feature.get('available'))
        and InteractionRewindService.can_rewind(interaction)
    )
    return {
        'interaction_id': str(interaction.id),
        'can_rewind': can_rewind,
        'rewind_expires_at': InteractionRewindService.expires_at(
            interaction
        ).isoformat(),
    }


def _rewind_response(user, interaction_id):
    feature = check_feature_availability(user, 'rewind')
    if not feature.get('available'):
        return Response(
            {
                'error': True,
                'code': 'premium_required',
                'message': _('Rewind is a premium feature.'),
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        result = InteractionRewindService.rewind(user, interaction_id)
    except RewindRejected as exc:
        status_map = {
            'interaction_not_found': status.HTTP_404_NOT_FOUND,
            'match_exists_use_unmatch': status.HTTP_409_CONFLICT,
            'rewind_daily_limit': status.HTTP_429_TOO_MANY_REQUESTS,
            'rewind_expired': status.HTTP_410_GONE,
            'interaction_not_active': status.HTTP_409_CONFLICT,
            'interaction_projection_missing': status.HTTP_409_CONFLICT,
        }
        return Response(
            {'error': True, 'code': exc.code, 'message': str(exc)},
            status=status_map.get(exc.code, status.HTTP_400_BAD_REQUEST),
        )

    return Response(
        {
            'status': 'rewound',
            'interaction_id': result.interaction_id,
            'previous_profile': result.profile,
            'already_rewound': result.already_rewound,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@transaction.atomic
def like_profile(request):
    """
    Like a profile.
    
    POST /api/v1/discovery/interactions/like
    
    Response:
        {
            "status": "liked" | "matched",
            "match_id": "uuid" | null,
            "daily_likes_remaining": int,
            "super_likes_remaining": int,
            "message": str (optional)
        }
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
    
    # Log debug info avant le like
    DailyLikesService.log_status(request.user, "BEFORE_LIKE")
    
    # Process like
    success, is_match, error_msg, error_code = MatchingService.like_profile(
        from_user=request.user,
        to_user=target_user
    )
    
    if not success:
        _error_status_map = {
            'daily_limit': status.HTTP_429_TOO_MANY_REQUESTS,
            'premium_required': status.HTTP_403_FORBIDDEN,
            'already_liked': status.HTTP_409_CONFLICT,
            'match_exists_use_unmatch': status.HTTP_409_CONFLICT,
        }
        http_status = _error_status_map.get(error_code, status.HTTP_400_BAD_REQUEST)
        return Response({
            'error': True,
            'message': error_msg,
            'code': error_code,
        }, status=http_status)
    
    # Obtenir les compteurs APRÈS le like en utilisant DailyLikesService
    daily_likes_remaining = DailyLikesService.get_likes_remaining(request.user)
    super_likes_remaining = DailyLikesService.get_super_likes_remaining(request.user)
    
    if is_match:
        # Get match details
        from .models import Match
        match = Match.get_match_between(request.user, target_user)
        
        logger.info("Match created from discovery")
        
        # Log debug info
        DailyLikesService.log_status(request.user, "AFTER_MATCH")
        
        # Safely get main photo URL (normalized — LOG-05)
        main_photo_url = None
        if hasattr(target_user, 'profile'):
            main_photo = target_user.profile.photos.filter(is_main=True).first()
            if main_photo:
                main_photo_url = profile_photo_delivery_url(main_photo, request)
        
        return Response({
            'status': 'matched',
            'match_id': str(match.id),
            'matched_user_info': {
                'user_id': str(target_user.id),
                'display_name': target_user.display_name,
                'main_photo_url': main_photo_url
            },
            'daily_likes_remaining': daily_likes_remaining,
            'super_likes_remaining': super_likes_remaining,
            **_rewind_metadata(request.user, target_user),
            'message': _("C'est un match!")
        }, status=status.HTTP_200_OK)
    
    # Log debug info
    DailyLikesService.log_status(request.user, "AFTER_LIKE")
    logger.info("Like successful; remaining=%s", daily_likes_remaining)
    
    return Response({
        'status': 'liked',
        'daily_likes_remaining': daily_likes_remaining,
        'super_likes_remaining': super_likes_remaining,
        **_rewind_metadata(request.user, target_user),
        'message': _("Like envoyé avec succès")
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@transaction.atomic
def dislike_profile(request):
    """
    Dislike (pass) a profile.
    
    POST /api/v1/discovery/interactions/dislike
    
    Response:
        {
            "status": "disliked",
            "daily_likes_remaining": int,
            "super_likes_remaining": int
        }
    """
    serializer = LikeActionSerializer(data=request.data)
    
    if not serializer.is_valid():
        logger.warning("Dislike validation error: %s", serializer.errors)
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
    
    # Process dislike — idempotent: already-disliked returns success
    success, error_msg = MatchingService.dislike_profile(
        from_user=request.user,
        to_user=target_user
    )
    
    if not success:
        is_existing_match = error_msg == 'match_exists_use_unmatch'
        return Response({
            'error': True,
            'message': (
                _('This connection already exists. Use unmatch to remove it.')
                if is_existing_match
                else error_msg
            ),
            'code': 'match_exists_use_unmatch' if is_existing_match else 'daily_limit',
        }, status=(
            status.HTTP_409_CONFLICT
            if is_existing_match
            else status.HTTP_429_TOO_MANY_REQUESTS
        ))
    
    # Obtenir les compteurs (inchangés par un dislike)
    daily_likes_remaining = DailyLikesService.get_likes_remaining(request.user)
    super_likes_remaining = DailyLikesService.get_super_likes_remaining(request.user)
    
    logger.info("Dislike successful; remaining=%s", daily_likes_remaining)
    
    return Response({
        'status': 'disliked',
        'daily_likes_remaining': daily_likes_remaining,
        'super_likes_remaining': super_likes_remaining,
        **_rewind_metadata(request.user, target_user),
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@transaction.atomic
def superlike_profile(request):
    """
    Super like a profile (premium feature).
    
    POST /api/v1/discovery/interactions/superlike
    
    Response:
        {
            "status": "superliked" | "matched_with_superlike",
            "match_id": "uuid" | null,
            "daily_likes_remaining": int,
            "super_likes_remaining": int,
            "message": str (optional)
        }
    """
    feature = check_feature_availability(request.user, 'super_like')
    if not feature['available'] and feature['reason'] != 'limit_reached':
        return Response({
            'error': True,
            'message': _('Super likes are a premium feature.'),
            'code': 'premium_required',
        }, status=status.HTTP_403_FORBIDDEN)

    # Vérifier si l'utilisateur peut encore super-liker
    can_super_like, error_msg = DailyLikesService.can_user_super_like(request.user)
    if not can_super_like:
        return Response({
            'error': True,
            'message': error_msg,
            'code': 'super_like_limit',
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)
    
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
    
    # Log debug info avant le super like
    DailyLikesService.log_status(request.user, "BEFORE_SUPERLIKE")
    
    # Process super like
    success, is_match, error_msg, error_code = MatchingService.like_profile(
        from_user=request.user,
        to_user=target_user,
        is_super_like=True
    )
    
    if not success:
        _error_status_map = {
            'daily_limit': status.HTTP_429_TOO_MANY_REQUESTS,
            'super_like_limit': status.HTTP_429_TOO_MANY_REQUESTS,
            'premium_required': status.HTTP_403_FORBIDDEN,
            'already_liked': status.HTTP_409_CONFLICT,
        }
        http_status = _error_status_map.get(error_code, status.HTTP_400_BAD_REQUEST)
        return Response({
            'error': True,
            'message': error_msg,
            'code': error_code,
        }, status=http_status)
    
    # Obtenir les compteurs APRÈS le super like
    daily_likes_remaining = DailyLikesService.get_likes_remaining(request.user)
    super_likes_remaining = DailyLikesService.get_super_likes_remaining(request.user)
    
    if is_match:
        # Get match details
        from .models import Match
        match = Match.get_match_between(request.user, target_user)
        
        logger.info("Super-like match created from discovery")
        
        # Log debug info
        DailyLikesService.log_status(request.user, "AFTER_SUPERLIKE_MATCH")
        
        return Response({
            'status': 'matched_with_superlike',
            'match_id': str(match.id),
            'matched_user_info': {
                'user_id': str(target_user.id),
                'display_name': target_user.display_name,
                'main_photo_url': (
                    profile_photo_delivery_url(
                        target_user.profile.photos.filter(is_main=True).first(), request,
                    )
                    if hasattr(target_user, 'profile') and target_user.profile.photos.exists()
                    else None
                )
            },
            'daily_likes_remaining': daily_likes_remaining,
            'super_likes_remaining': super_likes_remaining,
            **_rewind_metadata(request.user, target_user),
            'message': _("C'est un match avec un super like!")
        }, status=status.HTTP_200_OK)
    
    # Log debug info
    DailyLikesService.log_status(request.user, "AFTER_SUPERLIKE")
    logger.info("Super like successful; remaining=%s", super_likes_remaining)
    
    return Response({
        'status': 'superliked',
        'daily_likes_remaining': daily_likes_remaining,
        'super_likes_remaining': super_likes_remaining,
        **_rewind_metadata(request.user, target_user),
        'message': _("Super like envoyé avec succès")
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_interaction_status(request):
    """
    Get current interaction status (daily likes remaining, etc.).
    
    GET /api/v1/discovery/interactions/status
    
    Response:
        {
            "daily_likes_remaining": int,
            "daily_likes_limit": int | null,
            "super_likes_remaining": int,
            "super_likes_limit": int,
            "is_premium": bool,
            "reset_at": str (ISO timestamp),
            "likes_used_today": int,
            "super_likes_used_today": int
        }
    """
    status_summary = DailyLikesService.get_status_summary(request.user)
    
    logger.info(
        "Interaction status returned; daily_likes_remaining=%s",
        status_summary['daily_likes_remaining'],
    )
    
    return Response(status_summary, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@transaction.atomic
def rewind_interaction(request, interaction_id):
    """Rewind one explicit interaction.

    POST /api/v1/discovery/interactions/{interaction_id}/rewind/
    """
    return _rewind_response(request.user, interaction_id)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@transaction.atomic
def rewind_last_swipe(request):
    """Compatibility endpoint for older clients.

    Current clients always call the explicit interaction endpoint. Keeping this
    route avoids an unlocalized transport error while rollout is in progress.
    """
    interaction = (
        InteractionHistory.objects.filter(
            user=request.user,
            interaction_type__in=_REWINDABLE_INTERACTION_TYPES,
            is_revoked=False,
        )
        .order_by('-created_at')
        .first()
    )
    if interaction is None:
        return Response(
            {
                'error': True,
                'code': 'no_rewindable_interaction',
                'message': _('No recent action to rewind.'),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    return _rewind_response(request.user, interaction.id)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_likes_received(request):
    """
    Get list of users who liked you (premium feature).
    
    GET /api/v1/discovery/interactions/liked-me
    """
    if not check_feature_availability(request.user, 'see_likers')['available']:
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
    if not check_feature_availability(request.user, 'boost')['available']:
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
    
    logger.info("Boost activated")
    
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
    logger.info("Updating discovery filters")
    
    # Check if user has a profile
    if not hasattr(request.user, 'profile'):
        return Response({
            'error': True,
            'message': _('Profile not found.')
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Validate input
    serializer = SearchFilterSerializer(data=request.data)
    
    if not serializer.is_valid():
        logger.warning("Invalid discovery filter data")
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Update profile filters
    try:
        profile = serializer.update_profile_filters(request.user.profile)
        
        logger.info("Discovery filters updated successfully")
        
        return Response({
            'status': 'success',
            'message': _('Filters updated successfully'),
            'filters': {
                'age_min': profile.age_min_preference,
                'age_max': profile.age_max_preference,
                'distance_max_km': profile.distance_max_km,
                'genders': profile.genders_sought if profile.genders_sought else [],
                'relationship_types': profile.relationship_types_sought if profile.relationship_types_sought else [],
                'verified_only': profile.verified_only,
                'online_only': profile.online_only
            }
        }, status=status.HTTP_200_OK)
        
    except Exception:
        logger.exception("Error updating discovery filters")
        return Response({
            'error': True,
            'message': _('An error occurred while updating filters.')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_discovery_filters(request):
    """
    Get current discovery search filters.
    
    GET /api/v1/discovery/filters/get
    """
    logger.info("Getting discovery filters")
    
    # Check if user has a profile
    if not hasattr(request.user, 'profile'):
        return Response({
            'error': True,
            'message': _('Profile not found.')
        }, status=status.HTTP_404_NOT_FOUND)
    
    profile = request.user.profile
    
    return Response({
        'status': 'success',
        'filters': {
            'age_min': profile.age_min_preference,
            'age_max': profile.age_max_preference,
            'distance_max_km': profile.distance_max_km,
            'genders': profile.genders_sought if profile.genders_sought else [],
            'relationship_types': profile.relationship_types_sought if profile.relationship_types_sought else [],
            'verified_only': profile.verified_only,
            'online_only': profile.online_only
        }
    }, status=status.HTTP_200_OK)
