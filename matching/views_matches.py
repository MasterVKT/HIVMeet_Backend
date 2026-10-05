"""
Match management views for matching app.
"""
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
import logging

from .models import Match
from .serializers import MarkMatchesSeenSerializer, MatchSerializer
from .free_access import FreeMatchAccessError, FreeMatchAccessService
from .signals import dispatch_group_event

logger = logging.getLogger('hivmeet.matching')
User = get_user_model()


class MatchListView(generics.ListAPIView):
    """
    Get list of matches.
    
    GET /api/v1/matches
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MatchSerializer
    
    def get_queryset(self):
        """Get matches for current user."""
        user = self.request.user
        
        # Get all matches where user is involved
        queryset = Match.objects.filter(
            Q(user1=user) | Q(user2=user),
            status=Match.ACTIVE
        ).select_related('user1__profile', 'user2__profile')
        
        # Apply filters
        sort = self.request.query_params.get('sort', 'recent_activity')
        if sort == 'recent_activity':
            queryset = queryset.order_by('-last_message_at', '-created_at')
        else:
            queryset = queryset.order_by('-created_at')
        
        return queryset


def _unseen_matches_queryset(user):
    """The only authoritative source for the Matches tab badge."""
    return Match.objects.filter(status=Match.ACTIVE).filter(
        Q(user1=user, user1_seen_at__isnull=True)
        | Q(user2=user, user2_seen_at__isnull=True)
    )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def unseen_match_count(request):
    """Return the exact number of matches this participant has not opened."""
    return Response({'unseen_count': _unseen_matches_queryset(request.user).count()})


@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
@transaction.atomic
def mark_matches_seen(request):
    """Mark only the authenticated participant's matches as consulted.

    Supplying no IDs is an intentional convenience for a complete Matches
    page; a supplied list is all-or-nothing and never modifies a non-member's
    resource.
    """
    serializer = MarkMatchesSeenSerializer(data=request.data or {})
    serializer.is_valid(raise_exception=True)
    match_ids = serializer.validated_data.get('match_ids')
    queryset = Match.objects.select_for_update().filter(
        Q(user1=request.user) | Q(user2=request.user), status=Match.ACTIVE
    )
    if match_ids is not None:
        matches = list(queryset.filter(id__in=match_ids))
        if len(matches) != len(match_ids):
            return Response(
                {'error': 'match_not_found', 'message': _('A match is no longer available.')},
                status=status.HTTP_404_NOT_FOUND,
            )
    else:
        matches = list(queryset)

    now = timezone.now()
    user1_ids = [match.id for match in matches if match.user1_id == request.user.id]
    user2_ids = [match.id for match in matches if match.user2_id == request.user.id]
    updated = 0
    if user1_ids:
        updated += Match.objects.filter(
            id__in=user1_ids, user1_seen_at__isnull=True
        ).update(user1_seen_at=now)
    if user2_ids:
        updated += Match.objects.filter(
            id__in=user2_ids, user2_seen_at__isnull=True
        ).update(user2_seen_at=now)
    return Response(
        {
            'seen_count': updated,
            'unseen_count': _unseen_matches_queryset(request.user).count(),
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def unlock_free_match(request, match_id):
    """Retry a locked Free-Free match after a monthly reset.

    The service owns both token checks and uses a transaction; this endpoint
    never consumes the caller's allowance by itself.
    """
    match = Match.objects.filter(
        Q(user1=request.user) | Q(user2=request.user),
        id=match_id,
        status=Match.ACTIVE,
    ).select_related('user1__profile', 'user2__profile').first()
    if match is None:
        return Response({'error': 'match_not_found'}, status=status.HTTP_404_NOT_FOUND)
    try:
        updated = FreeMatchAccessService.retry_unlock(request.user, match)
    except FreeMatchAccessError as exc:
        return Response({'error': exc.code, 'message': str(exc)}, status=status.HTTP_409_CONFLICT)
    return Response(MatchSerializer(updated, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def reveal_received_like(request):
    """Consume the single Free monthly allowance by an explicit user action."""
    try:
        like, already_revealed = FreeMatchAccessService.reveal_received_like(
            request.user
        )
    except FreeMatchAccessError as exc:
        response_status = (
            status.HTTP_404_NOT_FOUND
            if exc.code == 'no_received_like'
            else status.HTTP_409_CONFLICT
        )
        return Response(
            {'error': exc.code, 'message': str(exc)}, status=response_status
        )

    from .serializers import DiscoveryProfileSerializer

    return Response(
        {
            'profile': DiscoveryProfileSerializer(
                like.from_user.profile, context={'request': request}
            ).data,
            'already_revealed': already_revealed,
            'monthly_token_consumed': True,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
@transaction.atomic
def unmatch_user(request, match_id):
    """
    Delete a match (unmatch).
    
    DELETE /api/v1/matches/{match_id}
    """
    match = (
        Match.objects.select_for_update()
        .filter(
            Q(user1=request.user) | Q(user2=request.user),
            id=match_id,
        )
        .select_related('user1', 'user2')
        .first()
    )
    if match is None:
        return Response({
            'error': True,
            'message': _('Match not found.')
        }, status=status.HTTP_404_NOT_FOUND)

    # A retry after a successful unmatch is deliberately a no-op. Membership
    # is still verified above, so this never reveals another user's match.
    if match.status == Match.ACTIVE:
        match.status = Match.DELETED
        match.save(update_fields=['status', 'updated_at'])
        for participant in (match.user1, match.user2):
            dispatch_group_event(
                f"user_{participant.id}",
                {'type': 'match_removed', 'match_id': str(match.id)},
            )
        logger.info("Match removed by a participant; match_id=%s", match.id)

    return Response(status=status.HTTP_204_NO_CONTENT)
