"""
Interaction history views for matching app.
"""
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone
import logging

from .models import InteractionHistory, Match, DailyLikeLimit
from .serializers import InteractionHistorySerializer, InteractionStatsSerializer
from subscriptions.utils import get_premium_limits

logger = logging.getLogger('hivmeet.matching')
User = get_user_model()


class InteractionHistoryPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_my_likes(request):
    """
    Get list of profiles the user has liked.
    
    GET /api/v1/discovery/interactions/my-likes
    
    Query params:
    - page: integer (default: 1)
    - page_size: integer (default: 20, max: 100)
    - include_matched: boolean (default: false)
    - include_revoked: boolean (default: false)
    - order_by: string (default: 'recent') - Options: 'recent', 'oldest'
    """
    logger.info(f"📖 User {request.user.id} requesting likes history")
    
    # Get query parameters
    include_matched = request.query_params.get('include_matched', 'false').lower() == 'true'
    include_revoked = request.query_params.get('include_revoked', 'false').lower() == 'true'
    order_by = request.query_params.get('order_by', 'recent')
    
    # Get likes
    interactions = InteractionHistory.get_user_likes(
        user=request.user,
        include_revoked=include_revoked
    )
    
    # Filter out matched if needed
    if not include_matched:
        # Get IDs of users with active matches
        matched_user_ids = Match.objects.filter(
            Q(user1=request.user) | Q(user2=request.user),
            status=Match.ACTIVE
        ).values_list('user1_id', 'user2_id')
        
        # Flatten the list
        matched_ids = set()
        for user1_id, user2_id in matched_user_ids:
            matched_ids.add(user1_id)
            matched_ids.add(user2_id)
        matched_ids.discard(request.user.id)
        
        interactions = interactions.exclude(target_user_id__in=matched_ids)
    
    # Ordering
    if order_by == 'oldest':
        interactions = interactions.order_by('created_at')
    else:
        interactions = interactions.order_by('-created_at')
    
    # Paginate
    paginator = InteractionHistoryPagination()
    page = paginator.paginate_queryset(interactions, request)
    
    # Serialize
    serializer = InteractionHistorySerializer(
        page,
        many=True,
        context={'request': request}
    )
    
    logger.info(f"✅ Returning {len(serializer.data)} likes for user {request.user.id}")
    
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_my_passes(request):
    """
    Get list of profiles the user has passed/disliked.
    
    GET /api/v1/discovery/interactions/my-passes
    
    Query params:
    - page: integer (default: 1)
    - page_size: integer (default: 20, max: 100)
    - include_revoked: boolean (default: false)
    - order_by: string (default: 'recent')
    """
    logger.info(f"📖 User {request.user.id} requesting passes history")
    
    # Get query parameters
    include_revoked = request.query_params.get('include_revoked', 'false').lower() == 'true'
    order_by = request.query_params.get('order_by', 'recent')
    
    # Get passes
    interactions = InteractionHistory.get_user_passes(
        user=request.user,
        include_revoked=include_revoked
    )
    
    # Ordering
    if order_by == 'oldest':
        interactions = interactions.order_by('created_at')
    else:
        interactions = interactions.order_by('-created_at')
    
    # Paginate
    paginator = InteractionHistoryPagination()
    page = paginator.paginate_queryset(interactions, request)
    
    # Serialize
    serializer = InteractionHistorySerializer(
        page,
        many=True,
        context={'request': request}
    )
    
    logger.info(f"✅ Returning {len(serializer.data)} passes for user {request.user.id}")
    
    return paginator.get_paginated_response(serializer.data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@transaction.atomic
def revoke_interaction(request, interaction_id):
    """
    Revoke/cancel an interaction to allow the profile to reappear in discovery.
    
    POST /api/v1/discovery/interactions/{interaction_id}/revoke
    """
    logger.info(f"🔄 User {request.user.id} attempting to revoke interaction {interaction_id}")
    
    try:
        interaction = InteractionHistory.objects.get(
            id=interaction_id,
            user=request.user
        )
    except InteractionHistory.DoesNotExist:
        logger.warning(f"❌ Interaction {interaction_id} not found for user {request.user.id}")
        return Response({
            'error': 'interaction_not_found',
            'message': _("This interaction doesn't exist or doesn't belong to you")
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if already revoked
    if interaction.is_revoked:
        logger.warning(f"⚠️  Interaction {interaction_id} already revoked")
        return Response({
            'error': 'already_revoked',
            'message': _('This interaction has already been cancelled')
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if it's a like that resulted in an active match
    if interaction.interaction_type in [InteractionHistory.LIKE, InteractionHistory.SUPER_LIKE]:
        active_match = Match.objects.filter(
            Q(user1=request.user, user2=interaction.target_user) |
            Q(user1=interaction.target_user, user2=request.user),
            status=Match.ACTIVE
        ).exists()
        
        if active_match:
            logger.warning(f"⚠️  Cannot revoke interaction {interaction_id} - active match exists")
            return Response({
                'error': 'cannot_revoke_match',
                'message': _('Cannot cancel a like that resulted in an active match')
            }, status=status.HTTP_400_BAD_REQUEST)
    
    # Revoke the interaction
    interaction.revoke()
    
    logger.info(f"✅ Interaction {interaction_id} revoked successfully")
    
    # TODO: Log analytics event if analytics service is available
    
    return Response({
        'status': 'revoked',
        'interaction_id': str(interaction.id),
        'message': _("The interaction has been cancelled. This profile may reappear in your discovery.")
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_interaction_stats(request):
    """
    Get statistics about user's interactions.
    
    GET /api/v1/discovery/interactions/stats
    """
    logger.info(f"📊 User {request.user.id} requesting interaction stats")
    
    user = request.user
    today = timezone.now().date()
    
    # Count interactions by type
    likes_count = InteractionHistory.objects.filter(
        user=user,
        interaction_type=InteractionHistory.LIKE,
        is_revoked=False
    ).count()
    
    super_likes_count = InteractionHistory.objects.filter(
        user=user,
        interaction_type=InteractionHistory.SUPER_LIKE,
        is_revoked=False
    ).count()
    
    dislikes_count = InteractionHistory.objects.filter(
        user=user,
        interaction_type=InteractionHistory.DISLIKE,
        is_revoked=False
    ).count()
    
    # Count matches
    matches_count = Match.objects.filter(
        Q(user1=user) | Q(user2=user),
        status=Match.ACTIVE
    ).count()
    
    # Calculate like-to-match ratio
    total_likes = likes_count + super_likes_count
    like_to_match_ratio = matches_count / total_likes if total_likes > 0 else 0
    
    # Today's interactions
    interactions_today = InteractionHistory.objects.filter(
        user=user,
        created_at__date=today
    ).count()
    
    # Daily limits
    try:
        limits = get_premium_limits(user)
        daily_limit = limits['limits']['likes']['max'] if user.is_premium else 100
    except:
        daily_limit = 100 if user.is_premium else 30
    
    remaining_today = max(0, daily_limit - interactions_today)
    
    stats = {
        'total_likes': likes_count,
        'total_super_likes': super_likes_count,
        'total_dislikes': dislikes_count,
        'total_matches': matches_count,
        'like_to_match_ratio': round(like_to_match_ratio, 2),
        'total_interactions_today': interactions_today,
        'daily_limit': daily_limit,
        'remaining_today': remaining_today
    }
    
    serializer = InteractionStatsSerializer(stats)
    
    logger.info(f"✅ Stats returned for user {request.user.id}")
    
    return Response(serializer.data, status=status.HTTP_200_OK)
