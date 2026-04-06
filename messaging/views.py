"""
Views for messaging app.
"""
import logging
import uuid

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from matching.models import Match
from subscriptions.utils import check_feature_availability, premium_required_response

from .models import Call, Message
from .serializers import (
    AnswerCallSerializer,
    CallSerializer,
    ConversationSerializer,
    EndCallSerializer,
    IceCandidateSerializer,
    InitiateCallSerializer,
    MarkAsReadSerializer,
    MessageSerializer,
    SendMessageSerializer,
)
from .services import CallService, MessageService

logger = logging.getLogger('hivmeet.messaging')
User = get_user_model()


def _get_active_match_for_user(user, conversation_id):
    return Match.objects.filter(
        Q(user1=user) | Q(user2=user),
        id=conversation_id,
        status=Match.ACTIVE,
    ).first()


class ConversationListView(generics.ListAPIView):
    """
    Get list of conversations.

    GET /api/v1/conversations/
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConversationSerializer

    def get_queryset(self):
        user = self.request.user

        queryset = Match.objects.filter(
            Q(user1=user) | Q(user2=user),
            status=Match.ACTIVE,
        ).exclude(
            last_message_at__isnull=True,
        ).select_related(
            'user1__profile',
            'user2__profile',
        ).order_by('-last_message_at')

        status_filter = self.request.query_params.get('status')
        if status_filter == 'archived':
            return queryset.none()
        return queryset


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

    if request.method == 'GET':
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 50))
        limit = int(request.query_params.get('limit', page_size))
        before_message_id = request.query_params.get('before_message_id')

        messages = MessageService.get_conversation_messages(
            user=request.user,
            match=match,
            limit=limit,
            before_id=before_message_id,
        )

        visible_query = Message.objects.filter(match=match).filter(
            Q(sender=request.user, is_deleted_by_sender=False)
            | Q(sender=match.get_other_user(request.user), is_deleted_by_recipient=False)
        )
        visible_count = visible_query.count()
        has_more = visible_count > len(messages)
        show_premium_prompt = has_more and not request.user.is_premium

        next_link = None
        if messages:
            next_link = f"?before_message_id={messages[-1].id}&page_size={limit}"
        previous_link = f"?page={page - 1}&page_size={limit}" if page > 1 else None

        serializer = MessageSerializer(messages, many=True, context={'request': request})
        return Response(
            {
                'count': visible_count,
                'next': next_link,
                'previous': previous_link,
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
        media_file_path=serializer.validated_data.get('media_file_path_on_storage'),
        client_message_id=serializer.validated_data['client_message_id'],
    )

    if not message:
        error_text = str(error_msg or '').lower()
        response_status = status.HTTP_403_FORBIDDEN if 'premium' in error_text else status.HTTP_400_BAD_REQUEST
        return Response({'error': error_msg or _('Unable to send message.')}, status=response_status)

    response_serializer = MessageSerializer(message, context={'request': request})
    return Response(response_serializer.data, status=status.HTTP_201_CREATED)


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
    updated_count = MessageService.mark_messages_as_read(
        user=request.user,
        match=match,
        last_read_message_id=str(last_read_message_id) if last_read_message_id else None,
    )

    return Response({'messages_marked': updated_count}, status=status.HTTP_200_OK)


@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def mark_single_message_as_read(request, conversation_id, message_id):
    """
    PUT /api/v1/conversations/{conversation_id}/messages/{message_id}/read/
    """

    match = _get_active_match_for_user(request.user, conversation_id)
    if not match:
        return Response({'error': _('Conversation not found.')}, status=status.HTTP_404_NOT_FOUND)

    message = Message.objects.filter(id=message_id, match=match).first()
    if not message:
        return Response({'error': _('Message not found.')}, status=status.HTTP_404_NOT_FOUND)

    if not MessageService.mark_single_message_as_read(request.user, message):
        return Response({'error': _('Cannot mark this message as read.')}, status=status.HTTP_403_FORBIDDEN)

    return Response({'message': _('Message marked as read'), 'read_at': message.read_at}, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def delete_message(request, conversation_id, message_id):
    """
    DELETE /api/v1/conversations/{conversation_id}/messages/{message_id}/
    """

    message = Message.objects.filter(id=message_id, match_id=conversation_id).first()
    if not message:
        return Response({'error': _('Message not found.')}, status=status.HTTP_404_NOT_FOUND)

    if request.user not in [message.match.user1, message.match.user2]:
        return Response({'error': _('You do not have permission to delete this message.')}, status=status.HTTP_403_FORBIDDEN)

    if not MessageService.delete_message(request.user, message):
        return Response({'error': _('Failed to delete message.')}, status=status.HTTP_400_BAD_REQUEST)

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
    is_online = (timezone.now() - other_user.last_active).total_seconds() < 300
    is_typing = len(MessageService.get_typing_users(match, exclude_user=request.user)) > 0

    return Response(
        {
            'participant': {
                'user_id': str(other_user.id),
                'is_online': is_online,
                'last_active': other_user.last_active,
                'is_typing': is_typing,
            }
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_media_upload_url(request):
    """
    POST /api/v1/conversations/generate-media-upload-url/
    """

    file_name = request.data.get('file_name') or 'upload.bin'
    content_type = request.data.get('content_type') or 'application/octet-stream'
    file_path_on_storage = f"messages/{request.user.id}/{uuid.uuid4()}_{file_name}"
    upload_url = f"https://storage.googleapis.com/hivmeet-media/{file_path_on_storage}"

    return Response(
        {
            'upload_url': upload_url,
            'file_path_on_storage': file_path_on_storage,
            'content_type': content_type,
            'expires_in_seconds': 900,
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

        if 'media_file' not in request.FILES:
            return Response({'error': _('Media file is required')}, status=status.HTTP_400_BAD_REQUEST)

        media_file = request.FILES['media_file']
        if media_file.size > 10 * 1024 * 1024:
            return Response({'error': _('File size must be less than 10MB')}, status=status.HTTP_400_BAD_REQUEST)

        media_type = request.data.get('media_type', Message.IMAGE)
        client_message_id = request.data.get('client_message_id')

        try:
            message = MessageService.create_media_message(
                sender=request.user,
                match=match,
                media_file=media_file,
                media_type=media_type,
                text=request.data.get('text', ''),
                client_message_id=client_message_id,
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