"""
Views for messaging app.
"""
import logging
import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.db.models import (
    Case,
    DateTimeField,
    Exists,
    F,
    IntegerField,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from matching.models import Match
from matching.free_access import FreeMatchAccessError, FreeMatchAccessService
from profiles.models import ProfilePhoto
from subscriptions.utils import (
    check_feature_availability,
    is_premium_user,
    premium_required_response,
)

from .models import Call, ConversationHiddenState, DevicePresenceSession, Message
from .presence import PresenceService
from .serializers import (
    AnswerCallSerializer,
    CallSerializer,
    ConversationListQuerySerializer,
    ConversationMessagesQuerySerializer,
    ConversationSerializer,
    DeleteMessagesSerializer,
    EditMessageSerializer,
    EndCallSerializer,
    IceCandidateSerializer,
    InitiateCallSerializer,
    MarkAsReadSerializer,
    MessageSerializer,
    SendMediaMessageSerializer,
    SendMessageSerializer,
)
from .services import (
    CallService,
    InvalidReadCursor,
    MessageDeletionRejected,
    MessageEditRejected,
    MessageService,
)

logger = logging.getLogger('hivmeet.messaging')
User = get_user_model()


class ConversationPagination(PageNumberPagination):
    """Stable, bounded pagination for the conversation list."""

    page_size = 20
    page_size_query_param = None
    max_page_size = 50

    def get_page_size(self, request):
        return getattr(request, '_conversation_page_size', self.page_size)


def _get_active_match_for_user(user, conversation_id):
    return Match.objects.filter(
        Q(user1=user) | Q(user2=user),
        id=conversation_id,
        status=Match.ACTIVE,
    ).first()


def _free_match_locked_response(match, user):
    """Uniform and privacy-safe denial for a locked Free-Free match."""
    try:
        FreeMatchAccessService.ensure_conversation_access(match, user)
    except FreeMatchAccessError as exc:
        return Response(
            {'error': exc.code, 'message': str(exc)},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


def _parse_single_byte_range(header_value, total_size):
    """Return an inclusive byte range or ``None`` for a full download."""
    if not header_value:
        return None
    match = re.fullmatch(r'bytes=(\d*)-(\d*)', header_value.strip())
    if not match:
        raise ValueError('invalid_range')
    raw_start, raw_end = match.groups()
    if not raw_start and not raw_end:
        raise ValueError('invalid_range')
    if raw_start:
        start = int(raw_start)
        end = int(raw_end) if raw_end else total_size - 1
    else:
        suffix_length = int(raw_end)
        if suffix_length <= 0:
            raise ValueError('invalid_range')
        start = max(total_size - suffix_length, 0)
        end = total_size - 1
    if start < 0 or end < start or start >= total_size:
        raise ValueError('invalid_range')
    return start, min(end, total_size - 1)


def _iter_media_file(file_handle, start, length, chunk_size=64 * 1024):
    """Yield a bounded storage stream without putting the media in memory."""
    try:
        file_handle.seek(start)
        remaining = length
        while remaining > 0:
            chunk = file_handle.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
    finally:
        file_handle.close()


class ConversationListView(generics.ListAPIView):
    """
    Get list of conversations.

    GET /api/v1/conversations/
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConversationSerializer
    pagination_class = ConversationPagination

    def get(self, request, *args, **kwargs):
        query_serializer = ConversationListQuerySerializer(data=request.query_params)
        if not query_serializer.is_valid():
            return Response(
                {'error': _('Validation error'), 'details': query_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request._conversation_list_query = query_serializer.validated_data
        request._conversation_page_size = query_serializer.validated_data['page_size']
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user

        # Keep the conversation list query count independent of page size.
        # ``to_attr`` differentiates an empty, prefetched result from an
        # unprefetched relation, which lets the serializer retain its safe
        # fallback for any future caller that does not use this queryset.
        main_photos = ProfilePhoto.objects.filter(is_main=True).order_by('id')
        # A globally retracted message stays in its conversation chronology,
        # but must never become the list preview. Filtering before slicing
        # lets the prefetch select the immediately preceding visible message.
        latest_message = Message.objects.filter(
            is_deleted_for_everyone=False,
        ).order_by('-created_at', '-id')[:1]
        presence_cutoff = timezone.now() - timedelta(
            seconds=PresenceService.EXPIRY_SECONDS,
        )

        # Presence must use the same server-side source as WebSocket events,
        # without executing one DevicePresenceSession query per conversation.
        # These annotations remain part of the main list query and are read by
        # ConversationSerializer only when present; its direct-use fallback is
        # deliberately retained for endpoints that do not use this queryset.
        def presence_annotations(user_field):
            sessions = DevicePresenceSession.objects.filter(
                user_id=OuterRef(user_field),
            )
            active_sessions = sessions.filter(
                disconnected_at__isnull=True,
                last_heartbeat_at__gte=presence_cutoff,
            )
            return {
                f'{user_field}_presence_is_online': Exists(active_sessions),
                f'{user_field}_presence_last_active': Subquery(
                    sessions.order_by('-last_heartbeat_at').values(
                        'last_heartbeat_at'
                    )[:1],
                    output_field=DateTimeField(),
                ),
            }

        queryset = Match.objects.filter(
            Q(user1=user) | Q(user2=user),
            status=Match.ACTIVE,
        ).exclude(
            last_message_at__isnull=True,
        ).exclude(
            hidden_states__user=user,
        ).select_related(
            'user1__profile',
            'user2__profile',
        ).prefetch_related(
            Prefetch(
                'user1__profile__photos',
                queryset=main_photos,
                to_attr='main_photo_list',
            ),
            Prefetch(
                'user2__profile__photos',
                queryset=main_photos,
                to_attr='main_photo_list',
            ),
            Prefetch(
                'messages',
                queryset=latest_message,
                to_attr='prefetched_last_messages',
            ),
        ).annotate(
            **presence_annotations('user1_id'),
            **presence_annotations('user2_id'),
        ).order_by('-last_message_at', '-id')

        status_filter = self.request._conversation_list_query['status']
        if status_filter == 'archived':
            return queryset.none()
        if status_filter == 'unread':
            # The unread counters are denormalized per match participant.
            # Annotating the requesting participant's counter keeps filtering,
            # ordering and pagination in the database rather than requiring a
            # paginated client to load and filter every conversation locally.
            queryset = queryset.annotate(
                unread_count_for_requesting_user=Case(
                    When(user1=user, then=F('user1_unread_count')),
                    When(user2=user, then=F('user2_unread_count')),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ).filter(unread_count_for_requesting_user__gt=0)
        return queryset


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def conversations_unread_count(request):
    """Total unread messages across every conversation of the requesting user.

    GET /api/v1/conversations/unread-count/

    Summing ``unread_count_for_me`` over the paginated conversation list only
    covers the first page, so a user with unread messages past page 1 sees a
    badge that is too low.  The aggregate below is computed server-side over
    the same set of conversations the list exposes (active, not hidden by this
    participant), which keeps the badge and the list consistent.
    """

    user = request.user
    total = Match.objects.filter(
        Q(user1=user) | Q(user2=user),
        status=Match.ACTIVE,
    ).exclude(
        hidden_states__user=user,
    ).aggregate(
        unread_count=Sum(
            Case(
                When(user1=user, then=F('user1_unread_count')),
                When(user2=user, then=F('user2_unread_count')),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
    )['unread_count']

    return Response({'unread_count': total or 0}, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def delete_conversation(request, conversation_id):
    """Hide a conversation from the requesting participant only.

    The state is idempotent so retried DELETE requests (for example after a
    mobile connection failure) cannot leak whether another client already
    completed the same user action.
    """

    match = _get_active_match_for_user(request.user, conversation_id)
    if not match:
        return Response(
            {'error': _('Conversation not found.')},
            status=status.HTTP_404_NOT_FOUND,
        )

    ConversationHiddenState.objects.get_or_create(match=match, user=request.user)
    logger.info(
        'Conversation hidden by participant: conversation_id=%s',
        match.id,
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def restore_conversation(request, conversation_id):
    """Restore a conversation previously hidden by the current participant."""
    match = _get_active_match_for_user(request.user, conversation_id)
    if not match:
        return Response(
            {'error': _('Conversation not found.')},
            status=status.HTTP_404_NOT_FOUND,
        )
    ConversationHiddenState.objects.filter(match=match, user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def download_message_media(request, conversation_id, message_id):
    """Stream one attachment to an authorised conversation participant.

    Only one byte range is accepted, which permits deterministic resumption
    after a mobile cancellation without exposing the storage URL itself.
    """
    match = _get_active_match_for_user(request.user, conversation_id)
    if not match:
        return Response({'error': _('Conversation not found.')}, status=status.HTTP_404_NOT_FOUND)

    access_denied = _free_match_locked_response(match, request.user)
    if access_denied:
        return access_denied

    message = Message.objects.filter(
        id=message_id,
        match=match,
        is_deleted_for_everyone=False,
    ).first()
    if not message or not message.media_file_path:
        return Response({'error': _('Media not found.')}, status=status.HTTP_404_NOT_FOUND)

    try:
        if not default_storage.exists(message.media_file_path):
            return Response({'error': _('Media not found.')}, status=status.HTTP_404_NOT_FOUND)
        file_size = default_storage.size(message.media_file_path)
        if file_size <= 0:
            return Response({'error': _('Media not found.')}, status=status.HTTP_404_NOT_FOUND)
        byte_range = _parse_single_byte_range(request.headers.get('Range'), file_size)
        file_handle = default_storage.open(message.media_file_path, 'rb')
    except ValueError:
        return Response(
            {'error': _('Requested media range is not available.')},
            status=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
        )
    except Exception:
        logger.warning('Unable to open message media for download: conversation_id=%s', match.id)
        return Response({'error': _('Media not found.')}, status=status.HTTP_404_NOT_FOUND)

    start, end = byte_range if byte_range else (0, file_size - 1)
    response = StreamingHttpResponse(
        _iter_media_file(file_handle, start, end - start + 1),
        status=status.HTTP_206_PARTIAL_CONTENT if byte_range else status.HTTP_200_OK,
        content_type=message.media_mime_type or 'application/octet-stream',
    )
    safe_name = message.media_file_name or 'attachment'
    response['Content-Disposition'] = f'attachment; filename="{safe_name}"'
    response['Accept-Ranges'] = 'bytes'
    response['Content-Length'] = str(end - start + 1)
    response['Cache-Control'] = 'private, no-store, max-age=0'
    response['X-Content-Type-Options'] = 'nosniff'
    if byte_range:
        response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
    return response


@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def conversation_messages(request, conversation_id):
    """
    GET/POST messages in conversation.

    GET  /api/v1/conversations/{conversation_id}/messages/
    POST /api/v1/conversations/{conversation_id}/messages/
    """

    match = _get_active_match_for_user(request.user, conversation_id)
    if not match:
        return Response({'error': _('Conversation not found.')}, status=status.HTTP_404_NOT_FOUND)

    access_denied = _free_match_locked_response(match, request.user)
    if access_denied:
        return access_denied

    if request.method == 'GET':
        query_serializer = ConversationMessagesQuerySerializer(data=request.query_params)
        if not query_serializer.is_valid():
            return Response(
                {'error': _('Validation error'), 'details': query_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        query = query_serializer.validated_data
        limit = query['resolved_limit']
        before_message_id = query.get('before_message_id')
        try:
            message_page = MessageService.get_conversation_messages(
                user=request.user,
                match=match,
                limit=limit,
                before_id=str(before_message_id) if before_message_id else None,
            )
        except InvalidReadCursor as exc:
            return Response(
                {
                    'error': _('Validation error'),
                    'details': {'before_message_id': [str(exc)]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        messages = message_page.messages

        visible_query = Message.objects.filter(match=match).filter(
            Q(is_deleted_for_everyone=True)
            | Q(sender=request.user, is_deleted_by_sender=False)
            | Q(sender=match.get_other_user(request.user), is_deleted_by_recipient=False)
        )
        visible_count = visible_query.count()
        has_more = message_page.has_more
        show_premium_prompt = visible_count > len(messages) and not is_premium_user(request.user)

        next_link = None
        if messages and has_more:
            next_link = f"?before_message_id={messages[-1].id}&limit={limit}"

        serializer = MessageSerializer(messages, many=True, context={'request': request})
        return Response(
            {
                'count': visible_count,
                'next': next_link,
                'previous': None,
                'results': serializer.data,
                'has_more': has_more,
                'show_premium_prompt': show_premium_prompt,
            },
            status=status.HTTP_200_OK,
        )

    serializer = SendMessageSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'error': _('Validation error'), 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    message, error_msg = MessageService.send_message(
        sender=request.user,
        match=match,
        content=serializer.validated_data.get('content', ''),
        message_type=serializer.validated_data['type'],
        client_message_id=serializer.validated_data['client_message_id'],
    )

    if not message:
        error_code = getattr(error_msg, 'code', None)
        error_text = str(error_msg or '').lower()
        response_status = (
            status.HTTP_403_FORBIDDEN
            if error_code in {'free_match_locked', 'free_message_limit_reached'}
            or 'premium' in error_text
            else status.HTTP_400_BAD_REQUEST
        )
        return Response(
            {
                'error': error_code or str(error_msg or _('Unable to send message.')),
                'message': str(error_msg or _('Unable to send message.')),
            },
            status=response_status,
        )

    response_serializer = MessageSerializer(message, context={'request': request})
    return Response(response_serializer.data, status=status.HTTP_201_CREATED)


@api_view(['PATCH', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def edit_message(request, conversation_id, message_id):
    """Edit one eligible Premium text message or locally delete one message."""
    match = _get_active_match_for_user(request.user, conversation_id)
    if not match:
        return Response({'error': 'conversation_unavailable'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'DELETE':
        message = Message.objects.filter(id=message_id, match=match).first()
        if not message:
            return Response({'error': 'message_not_found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            MessageService.delete_messages(
                request.user, match, [message.id], scope='for_me'
            )
        except MessageDeletionRejected as exc:
            return Response(
                {'error': exc.code, 'message': str(exc)}, status=exc.status_code
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = EditMessageSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'error': 'validation_error', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        message = MessageService.edit_message(
            request.user,
            match,
            message_id,
            serializer.validated_data['content'],
        )
    except MessageEditRejected as exc:
        return Response(
            {'error': exc.code, 'message': str(exc)}, status=exc.status_code
        )
    return Response(
        MessageSerializer(message, context={'request': request}).data,
        status=status.HTTP_200_OK,
    )


@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def mark_messages_as_read(request, conversation_id):
    """
    PUT /api/v1/conversations/{conversation_id}/messages/mark-as-read/
    """

    match = _get_active_match_for_user(request.user, conversation_id)
    if not match:
        return Response({'error': _('Conversation not found.')}, status=status.HTTP_404_NOT_FOUND)

    serializer = MarkAsReadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'error': _('Validation error'), 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    last_read_message_id = serializer.validated_data.get('last_read_message_id')
    try:
        receipt = MessageService.mark_messages_as_read(
            user=request.user,
            match=match,
            last_read_message_id=str(last_read_message_id) if last_read_message_id else None,
        )
    except InvalidReadCursor as exc:
        return Response(
            {
                'error': _('Validation error'),
                'details': {'last_read_message_id': [str(exc)]},
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    response_data = {
        'messages_marked': receipt.messages_marked,
        'unread_count_for_me': receipt.unread_count_for_me,
    }
    if receipt.read_at is not None:
        response_data['read_at'] = receipt.read_at
    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def mark_single_message_as_read(request, conversation_id, message_id):
    """
    PUT /api/v1/conversations/{conversation_id}/messages/{message_id}/read/
    """

    match = _get_active_match_for_user(request.user, conversation_id)
    if not match:
        return Response({'error': _('Conversation not found.')}, status=status.HTTP_404_NOT_FOUND)

    if not Message.objects.filter(id=message_id, match=match).exists():
        return Response({'error': _('Message not found.')}, status=status.HTTP_404_NOT_FOUND)

    try:
        receipt = MessageService.mark_single_message_as_read(
            request.user,
            match,
            str(message_id),
        )
    except InvalidReadCursor as exc:
        return Response(
            {
                'error': _('Validation error'),
                'details': {'message_id': [str(exc)]},
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    response_data = {
        'message': _('Message marked as read'),
        'messages_marked': receipt.messages_marked,
        'unread_count_for_me': receipt.unread_count_for_me,
    }
    if receipt.read_at is not None:
        response_data['read_at'] = receipt.read_at
    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def delete_message(request, conversation_id, message_id):
    """
    DELETE /api/v1/conversations/{conversation_id}/messages/{message_id}/
    """

    match = _get_active_match_for_user(request.user, conversation_id)
    if not match:
        return Response({'error': _('Conversation not found.')}, status=status.HTTP_404_NOT_FOUND)

    message = Message.objects.filter(id=message_id, match=match).first()
    if not message:
        return Response({'error': _('Message not found.')}, status=status.HTTP_404_NOT_FOUND)

    try:
        MessageService.delete_messages(
            request.user, match, [message.id], scope='for_me'
        )
    except MessageDeletionRejected as exc:
        return Response({'error': exc.code, 'message': str(exc)}, status=exc.status_code)

    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def delete_messages(request, conversation_id):
    """Delete selected messages locally or, for Premium authors, globally.

    POST /api/v1/conversations/{conversation_id}/messages/delete/
    {"message_ids": [UUID, ...], "scope": "for_me"|"for_everyone"}
    """
    match = _get_active_match_for_user(request.user, conversation_id)
    if not match:
        return Response({'error': 'conversation_unavailable'}, status=status.HTTP_404_NOT_FOUND)

    serializer = DeleteMessagesSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'error': 'validation_error', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        MessageService.delete_messages(
            request.user,
            match,
            serializer.validated_data['message_ids'],
            serializer.validated_data['scope'],
        )
    except MessageDeletionRejected as exc:
        return Response(
            {'error': exc.code, 'message': str(exc)}, status=exc.status_code
        )
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def typing_indicator(request, conversation_id):
    """
    POST /api/v1/conversations/{conversation_id}/typing/
    """

    match = _get_active_match_for_user(request.user, conversation_id)
    if not match:
        return Response({'error': _('Conversation not found.')}, status=status.HTTP_404_NOT_FOUND)

    is_typing = bool(request.data.get('is_typing', True))
    MessageService.update_typing_indicator(request.user, match, is_typing)
    return Response({'is_typing': is_typing}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def conversation_presence(request, conversation_id):
    """
    GET /api/v1/conversations/{conversation_id}/presence/
    """

    match = _get_active_match_for_user(request.user, conversation_id)
    if not match:
        return Response({'error': _('Conversation not found.')}, status=status.HTTP_404_NOT_FOUND)

    other_user = match.get_other_user(request.user)
    snapshot = PresenceService.snapshot_for(other_user)
    is_typing = len(MessageService.get_typing_users(match, exclude_user=request.user)) > 0

    return Response(
        {
            'participant': {
                'user_id': str(other_user.id),
                'visibility': snapshot['visibility'],
                'is_online': snapshot['is_online'],
                'last_active': snapshot['last_active'],
                'is_typing': is_typing,
            },
            'server_timestamp': snapshot['server_timestamp'],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def initiate_call(request):
    """
    POST /api/v1/calls/initiate
    """

    serializer = InitiateCallSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': _('Validation error'), 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    target_user = User.objects.filter(id=serializer.validated_data['target_user_id']).first()
    if not target_user:
        return Response({'error': _('User not found.')}, status=status.HTTP_404_NOT_FOUND)

    match = Match.get_match_between(request.user, target_user)
    if not match:
        return Response({'error': _('No active match with this user.')}, status=status.HTTP_404_NOT_FOUND)

    call, error_msg = CallService.initiate_call(
        caller=request.user,
        match=match,
        call_type=serializer.validated_data['call_type'],
        offer_sdp=serializer.validated_data['offer_sdp'],
    )
    if not call:
        error_text = str(error_msg or '').lower()
        response_status = status.HTTP_403_FORBIDDEN if 'premium' in error_text else status.HTTP_400_BAD_REQUEST
        return Response({'error': error_msg}, status=response_status)

    return Response({'call_id': str(call.id), 'status': call.status, 'message': _('Call initiated. Waiting for response.')}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def answer_call(request, call_id):
    """
    POST /api/v1/calls/{call_id}/answer
    """

    call = Call.objects.filter(id=call_id, callee=request.user).first()
    if not call:
        return Response({'error': _('Call not found.')}, status=status.HTTP_404_NOT_FOUND)

    serializer = AnswerCallSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': _('Validation error'), 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    if not CallService.answer_call(call=call, answer_sdp=serializer.validated_data['answer_sdp']):
        return Response({'error': _('Failed to answer call. Call may have ended.')}, status=status.HTTP_400_BAD_REQUEST)

    return Response({'call_id': str(call.id), 'status': call.status, 'message': _('Call connected.')}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def add_ice_candidate(request, call_id):
    """
    POST /api/v1/calls/{call_id}/ice-candidate
    """

    call = Call.objects.filter(Q(caller=request.user) | Q(callee=request.user), id=call_id).first()
    if not call:
        return Response({'error': _('Call not found.')}, status=status.HTTP_404_NOT_FOUND)

    serializer = IceCandidateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': _('Validation error'), 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    if not CallService.add_ice_candidate(call=call, candidate=serializer.validated_data['candidate'], from_user=request.user):
        return Response({'error': _('Failed to add ICE candidate.')}, status=status.HTTP_400_BAD_REQUEST)

    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def end_call(request, call_id):
    """
    POST /api/v1/calls/{call_id}/terminate
    """

    call = Call.objects.filter(Q(caller=request.user) | Q(callee=request.user), id=call_id).first()
    if not call:
        return Response({'error': _('Call not found.')}, status=status.HTTP_404_NOT_FOUND)

    serializer = EndCallSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': _('Validation error'), 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    if not CallService.end_call(call=call, reason=serializer.validated_data['reason'], ended_by=request.user):
        return Response({'error': _('Call already ended.')}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            'call_id': str(call.id),
            'status': call.status,
            'duration_seconds': call.duration_seconds,
            'message': _('Call ended.'),
        },
        status=status.HTTP_200_OK,
    )


class SendMediaMessageView(APIView):
    """
    Send media message (Premium only).
    POST /api/v1/conversations/{conversation_id}/messages/media/
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, conversation_id):
        feature_check = check_feature_availability(request.user, 'media_messaging')
        if not feature_check['available']:
            return premium_required_response()

        match = _get_active_match_for_user(request.user, conversation_id)
        if not match:
            return Response({'error': _('Conversation not found.')}, status=status.HTTP_404_NOT_FOUND)

        serializer = SendMediaMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': _('Validation error'), 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            message = MessageService.create_media_message(
                sender=request.user,
                match=match,
                media_file=serializer.validated_data['media_file'],
                media_type=serializer.validated_data['media_type'],
                text=serializer.validated_data.get('text', ''),
                client_message_id=serializer.validated_data.get('client_message_id'),
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = MessageSerializer(message, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class InitiatePremiumCallView(APIView):
    """
    Initiate audio/video call (Premium only).
    POST /api/v1/calls/initiate-premium/
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        feature_check = check_feature_availability(request.user, 'calls')
        if not feature_check['available']:
            return premium_required_response()

        serializer = InitiateCallSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response({'error': _('Validation error'), 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        target_user = get_object_or_404(User, id=serializer.validated_data['target_user_id'])
        match = Match.get_match_between(request.user, target_user)
        if not match:
            return Response({'error': _('No active match with this user.')}, status=status.HTTP_404_NOT_FOUND)

        call, error_msg = CallService.initiate_call(
            caller=request.user,
            match=match,
            call_type=serializer.validated_data['call_type'],
            offer_sdp=serializer.validated_data['offer_sdp'],
        )
        if not call:
            return Response({'error': error_msg or _('Cannot initiate call at this time')}, status=status.HTTP_400_BAD_REQUEST)

        call_serializer = CallSerializer(call, context={'request': request})
        return Response(call_serializer.data, status=status.HTTP_201_CREATED)
