"""
Match management views for matching app.
"""
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
import logging

from .models import Match
from .serializers import MatchSerializer

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


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def unmatch_user(request, match_id):
    """
    Delete a match (unmatch).
    
    DELETE /api/v1/matches/{match_id}
    """
    try:
        # Get match and verify user is part of it
        match = Match.objects.get(
            Q(user1=request.user) | Q(user2=request.user),
            id=match_id,
            status=Match.ACTIVE
        )
        
        # Mark as deleted rather than actually deleting
        match.status = Match.DELETED
        match.save()
        
        logger.info(f"User {request.user.email} unmatched from match {match_id}")
        
        return Response(status=status.HTTP_204_NO_CONTENT)
        
    except Match.DoesNotExist:
        return Response({
            'error': True,
            'message': _('Match not found.')
        }, status=status.HTTP_404_NOT_FOUND)