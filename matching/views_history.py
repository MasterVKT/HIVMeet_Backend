"""Privacy-safe, paginated interaction history endpoints."""

from __future__ import annotations

import unicodedata

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .daily_likes_service import DailyLikesService
from .models import InteractionHistory, Match
from .serializers import (
    BulkRevokeInteractionsSerializer,
    InteractionHistorySerializer,
    InteractionStatsSerializer,
)


class InteractionHistoryPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def _normalise_search(value: str) -> str:
    """Case- and accent-insensitive text normalization without a DB extension."""
    decomposed = unicodedata.normalize('NFKD', value.casefold())
    return ''.join(char for char in decomposed if not unicodedata.combining(char))


def _query_param_match_state(request) -> str:
    """Read the explicit Phase 5 filter while accepting the legacy boolean."""
    value = request.query_params.get('match_state')
    if value is None:
        return (
            BulkRevokeInteractionsSerializer.MATCH_MATCHED
            if request.query_params.get('matched_only', '').lower() == 'true'
            else BulkRevokeInteractionsSerializer.MATCH_ALL
        )
    if value not in {
        BulkRevokeInteractionsSerializer.MATCH_ALL,
        BulkRevokeInteractionsSerializer.MATCH_MATCHED,
        BulkRevokeInteractionsSerializer.MATCH_UNMATCHED,
    }:
        raise ValueError('invalid_match_state')
    return value


def _active_matches_by_target(user, target_ids=None):
    matches = Match.objects.filter(
        Q(user1=user) | Q(user2=user), status=Match.ACTIVE
    )
    if target_ids is not None:
        target_ids = list(target_ids)
        if not target_ids:
            return {}
        matches = matches.filter(
            Q(user1_id__in=target_ids) | Q(user2_id__in=target_ids)
        )
    return {
        (match.user2_id if match.user1_id == user.id else match.user1_id): match.id
        for match in matches.only('id', 'user1_id', 'user2_id')
    }


def _history_queryset(
    *,
    user,
    history_type: str,
    query: str = '',
    match_state: str = 'all',
    include_revoked=False,
    selectable_only=False,
):
    if history_type == BulkRevokeInteractionsSerializer.HISTORY_LIKES:
        queryset = InteractionHistory.get_user_likes(user, include_revoked=include_revoked)
    else:
        queryset = InteractionHistory.get_user_passes(user, include_revoked=include_revoked)

    if match_state != BulkRevokeInteractionsSerializer.MATCH_ALL:
        matched_target_ids = _active_matches_by_target(user).keys()
        if match_state == BulkRevokeInteractionsSerializer.MATCH_MATCHED:
            queryset = queryset.filter(target_user_id__in=matched_target_ids)
        else:
            queryset = queryset.exclude(target_user_id__in=matched_target_ids)

    # A like that produced an active match remains visible in history, but it
    # is not selectable for a revoke. Excluding it here lets "select all"
    # mean every selectable result without turning it into a partial action.
    if selectable_only:
        queryset = queryset.filter(is_revoked=False)
        if history_type == BulkRevokeInteractionsSerializer.HISTORY_LIKES:
            queryset = queryset.exclude(
                target_user_id__in=_active_matches_by_target(user).keys()
            )

    query = query.strip()
    if query:
        # Django's portable icontains does not fold accents on every supported
        # database. This still keeps filtering, sorting and pagination server-side.
        needle = _normalise_search(query)
        # values_list removes the inherited profile join from the history
        # queryset. Combining that inherited select_related with `only` would
        # defer the same relation and crash before the request is paginated.
        candidate_ids = [
            interaction_id
            for interaction_id, display_name in queryset.values_list(
                'id', 'target_user__display_name'
            )
            if needle in _normalise_search(display_name)
        ]
        queryset = queryset.filter(id__in=candidate_ids)

    return queryset.order_by('-created_at', '-id')


def _serialize_history(entries, user, request):
    entries = list(entries)
    match_ids_by_target = _active_matches_by_target(
        user, {entry.target_user_id for entry in entries}
    )
    return InteractionHistorySerializer(
        entries,
        many=True,
        context={
            'request': request,
            'active_match_ids_by_target': match_ids_by_target,
        },
    ).data


def _history_response(request, history_type: str):
    try:
        match_state = _query_param_match_state(request)
    except ValueError:
        return Response(
            {'error': 'invalid_match_state', 'message': _('The match filter is invalid.')},
            status=status.HTTP_400_BAD_REQUEST,
        )

    query = request.query_params.get('q', '')
    if len(query) > 100:
        return Response(
            {'error': 'invalid_query', 'message': _('The search is too long.')},
            status=status.HTTP_400_BAD_REQUEST,
        )
    include_revoked = request.query_params.get('include_revoked', 'false').lower() == 'true'
    queryset = _history_queryset(
        user=request.user,
        history_type=history_type,
        query=query,
        match_state=match_state,
        include_revoked=include_revoked,
    )
    paginator = InteractionHistoryPagination()
    page = paginator.paginate_queryset(queryset, request)
    response = paginator.get_paginated_response(
        _serialize_history(page, request.user, request)
    )
    response.data['selectable_count'] = _history_queryset(
        user=request.user,
        history_type=history_type,
        query=query,
        match_state=match_state,
        include_revoked=include_revoked,
        selectable_only=True,
    ).count()
    return response


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_my_likes(request):
    """GET history with q and match_state=all|matched|unmatched."""
    return _history_response(request, BulkRevokeInteractionsSerializer.HISTORY_LIKES)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_my_passes(request):
    """GET pass history with the same searchable, paginated contract."""
    return _history_response(request, BulkRevokeInteractionsSerializer.HISTORY_PASSES)


def _issue(interaction_id, code, *, profile_user_id=None, match_id=None):
    payload = {'interaction_id': str(interaction_id), 'code': code}
    if profile_user_id is not None:
        payload['profile_user_id'] = str(profile_user_id)
    if match_id is not None:
        payload['match_id'] = str(match_id)
    return payload


def _revoke_locked_interactions(*, user, interaction_ids, history_type=None):
    """Validate every item first, then perform one all-or-nothing update."""
    locked = list(
        InteractionHistory.objects.select_for_update()
        .filter(user=user, id__in=interaction_ids)
        .select_related('target_user')
    )
    by_id = {interaction.id: interaction for interaction in locked}
    issues = [
        _issue(interaction_id, 'not_found')
        for interaction_id in interaction_ids
        if interaction_id not in by_id
    ]

    expected_types = (
        {InteractionHistory.LIKE, InteractionHistory.SUPER_LIKE}
        if history_type == BulkRevokeInteractionsSerializer.HISTORY_LIKES
        else {InteractionHistory.DISLIKE}
        if history_type == BulkRevokeInteractionsSerializer.HISTORY_PASSES
        else None
    )
    active_matches = _active_matches_by_target(
        user, {interaction.target_user_id for interaction in locked}
    )
    for interaction in locked:
        if expected_types is not None and interaction.interaction_type not in expected_types:
            issues.append(
                _issue(
                    interaction.id,
                    'history_type_mismatch',
                    profile_user_id=interaction.target_user_id,
                )
            )
        elif interaction.is_revoked:
            issues.append(
                _issue(
                    interaction.id,
                    'already_revoked',
                    profile_user_id=interaction.target_user_id,
                )
            )
        elif (
            interaction.interaction_type
            in (InteractionHistory.LIKE, InteractionHistory.SUPER_LIKE)
            and interaction.target_user_id in active_matches
        ):
            issues.append(
                _issue(
                    interaction.id,
                    'active_match_requires_unmatch',
                    profile_user_id=interaction.target_user_id,
                    match_id=active_matches[interaction.target_user_id],
                )
            )

    if issues:
        return [], issues

    now = timezone.now()
    InteractionHistory.objects.filter(id__in=interaction_ids).update(
        is_revoked=True,
        revoked_at=now,
    )
    return locked, []


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@transaction.atomic
def revoke_interaction(request, interaction_id):
    """Legacy single revoke implemented through the same atomic policy."""
    revoked, issues = _revoke_locked_interactions(
        user=request.user,
        interaction_ids=[interaction_id],
    )
    if issues:
        issue = issues[0]
        code = issue['code']
        if code == 'active_match_requires_unmatch':
            return Response(
                {
                    'error': 'cannot_revoke_match',
                    'code': 'cannot_revoke_match',
                    'message': _('Cannot cancel a like that resulted in an active match.'),
                },
                status=status.HTTP_409_CONFLICT,
            )
        response_status = (
            status.HTTP_404_NOT_FOUND if code == 'not_found' else status.HTTP_400_BAD_REQUEST
        )
        return Response(
            {'error': code, 'code': code, 'message': _('This interaction cannot be cancelled.')},
            status=response_status,
        )

    return Response(
        {
            'status': 'revoked',
            'interaction_id': str(revoked[0].id),
            'message': _('The interaction has been cancelled. This profile may reappear in discovery.'),
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@transaction.atomic
def revoke_interactions_bulk(request):
    """Atomically revoke selected rows or every result of the active filter."""
    serializer = BulkRevokeInteractionsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    history_type = values['history_type']

    if values['select_all']:
        interaction_ids = list(
            _history_queryset(
                user=request.user,
                history_type=history_type,
                query=values.get('q', ''),
                match_state=values['match_state'],
                include_revoked=values['include_revoked'],
                selectable_only=True,
            )
            .prefetch_related(None)
            .values_list('id', flat=True)
        )
    else:
        interaction_ids = values['interaction_ids']

    if not interaction_ids:
        return Response(
            {
                'revoked_count': 0,
                'revoked_interaction_ids': [],
                'message': _('No interaction matched this selection.'),
            },
            status=status.HTTP_200_OK,
        )

    revoked, issues = _revoke_locked_interactions(
        user=request.user,
        interaction_ids=interaction_ids,
        history_type=history_type,
    )
    if issues:
        return Response(
            {
                'error': 'bulk_revoke_not_possible',
                'message': _('No interaction was cancelled because the selection changed.'),
                'reasons': issues,
            },
            status=status.HTTP_409_CONFLICT,
        )

    return Response(
        {
            'revoked_count': len(revoked),
            'revoked_interaction_ids': [str(interaction.id) for interaction in revoked],
            'message': _('The selected interactions have been cancelled.'),
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_interaction_stats(request):
    """Return aggregate interaction statistics without exposing other users."""
    user = request.user
    likes_count = InteractionHistory.objects.filter(
        user=user, interaction_type=InteractionHistory.LIKE, is_revoked=False
    ).count()
    super_likes_count = InteractionHistory.objects.filter(
        user=user, interaction_type=InteractionHistory.SUPER_LIKE, is_revoked=False
    ).count()
    dislikes_count = InteractionHistory.objects.filter(
        user=user, interaction_type=InteractionHistory.DISLIKE, is_revoked=False
    ).count()
    matches_count = Match.objects.filter(
        Q(user1=user) | Q(user2=user), status=Match.ACTIVE
    ).count()
    interactions_today = InteractionHistory.objects.filter(
        user=user, created_at__date=timezone.localdate()
    ).count()
    total_likes = likes_count + super_likes_count
    daily_limit = DailyLikesService.get_user_daily_limit(user)
    remaining_today = (
        daily_limit
        if daily_limit == DailyLikesService.UNLIMITED
        else max(0, daily_limit - interactions_today)
    )
    return Response(
        InteractionStatsSerializer(
            {
                'total_likes': likes_count,
                'total_super_likes': super_likes_count,
                'total_dislikes': dislikes_count,
                'total_matches': matches_count,
                'like_to_match_ratio': round(matches_count / total_likes, 2)
                if total_likes
                else 0,
                'total_interactions_today': interactions_today,
                'daily_limit': daily_limit,
                'remaining_today': remaining_today,
            }
        ).data
    )
