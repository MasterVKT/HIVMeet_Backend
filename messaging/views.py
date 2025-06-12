"""
Views for messaging app.
"""
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.db.models import Q, F
from django.shortcuts import get_object_or_404
import logging
from django.utils import timezone
from matching.models import Match
from .models import Message, Call
from .services import MessageService, CallService
from .serializers import (
    MessageSerializer,
    ConversationSerializer,
    SendMessageSerializer,
    MarkAsReadSerializer,
    CallSerializer,
    InitiateCallSerializer,
    AnswerCallSerializer,
    IceCandidateSerializer,
    EndCallSerializer
)

logger = logging.getLogger('hivmeet.messaging')
User = get_user_model()


class ConversationListView(generics.ListAPIView):
    """
    Get list of conversations.
    
    GET /api/v1/conversations
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConversationSerializer
    
    def get_queryset(self):
        """Get conversations for current user."""
        user = self.request.user
        
        # Get all active matches with messages
        queryset = Match.objects.filter(
            Q(user1=user) | Q(user2=user),
            status=Match.ACTIVE
        ).exclude(
            last_message_at__isnull=True
        ).select_related(
            'user1__profile',
            'user2__profile'
        ).order_by('-last_message_at')
        
        # Apply status filter
        status_filter = self.request.query_params.get('status')
        if status_filter == 'archived':
            # This would need an archived field on Match model
            pass
        
        return queryset


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_conversation_messages(request, conversation_id):
    """
    Get messages for a conversation.
    
    GET /api/v1/conversations/{conversation_id}/messages
    """
    try:
        # Get match and verify user is part of it
        match = Match.objects.get(
            Q(user1=request.user) | Q(user2=request.user),
            id=conversation_id,
            status=Match.ACTIVE
        )
    except Match.DoesNotExist:
        return Response({
            'error': True,
            'message': _('Conversation not found.')
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Get query parameters
    limit = int(request.query_params.get('limit', 50))
    before_message_id = request.query_params.get('before_message_id')
    
    # Get messages
    messages = MessageService.get_conversation_messages(
        user=request.user,
        match=match,
        limit=limit,
        before_id=before_message_id
    )
    
    # Check if there are more messages (for non-premium users)
    total_count = Message.objects.filter(match=match).count()
    has_more = len(messages) < total_count
    show_premium_prompt = has_more and not request.user.is_premium
    
    # Serialize messages
    serializer = MessageSerializer(messages, many=True, context={'request': request})
    
    return Response({
        'count': len(messages),
        'has_more': has_more,
        'show_premium_prompt': show_premium_prompt,
        'results': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def send_message(request, conversation_id):
    """
    Send a message in a conversation.
    
    POST /api/v1/conversations/{conversation_id}/messages
    """
    try:
        # Get match and verify user is part of it
        match = Match.objects.get(
            Q(user1=request.user) | Q(user2=request.user),
            id=conversation_id,
            status=Match.ACTIVE
        )
    except Match.DoesNotExist:
        return Response({
            'error': True,
            'message': _('Conversation not found.')
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Validate input
    serializer = SendMessageSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Send message
    message, error_msg = MessageService.send_message(
        sender=request.user,
        match=match,
        content=serializer.validated_data.get('content', ''),
        message_type=serializer.validated_data['type'],
        media_file_path=serializer.validated_data.get('media_file_path_on_storage'),
        client_message_id=serializer.validated_data['client_message_id']
    )
    
    if not message:
        return Response({
            'error': True,
            'message': error_msg
        }, status=status.HTTP_400_BAD_REQUEST if 'premium' not in error_msg else status.HTTP_403_FORBIDDEN)
    
    # Serialize and return
    response_serializer = MessageSerializer(message, context={'request': request})
    
    return Response(response_serializer.data, status=status.HTTP_201_CREATED)


@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def mark_messages_as_read(request, conversation_id):
    """
    Mark messages as read in a conversation.
    
    PUT /api/v1/conversations/{conversation_id}/messages/mark-as-read
    """
    try:
        # Get match and verify user is part of it
        match = Match.objects.get(
            Q(user1=request.user) | Q(user2=request.user),
            id=conversation_id,
            status=Match.ACTIVE
        )
    except Match.DoesNotExist:
        return Response({
            'error': True,
            'message': _('Conversation not found.')
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Get last read message ID
    serializer = MarkAsReadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    last_read_message_id = serializer.validated_data.get('last_read_message_id')
    
    # Mark messages as read
    other_user = match.get_other_user(request.user)
    query = Message.objects.filter(
        match=match,
        sender=other_user,
        status__in=[Message.SENT, Message.DELIVERED]
    )
    
    if last_read_message_id:
        try:
            last_message = Message.objects.get(id=last_read_message_id, match=match)
            query = query.filter(created_at__lte=last_message.created_at)
        except Message.DoesNotExist:
            pass
    
    # Update messages
    updated_count = query.update(status=Message.READ, read_at=timezone.now())
    
    # Reset unread count
    match.reset_unread(request.user)
    
    return Response({
        'messages_marked': updated_count
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def delete_message(request, conversation_id, message_id):
    """
    Delete a message.
    
    DELETE /api/v1/conversations/{conversation_id}/messages/{message_id}
    """
    try:
        # Get message and verify permissions
        message = Message.objects.get(
            id=message_id,
            match_id=conversation_id
        )
        
        # Verify user is part of the conversation
        if request.user not in [message.match.user1, message.match.user2]:
            return Response({
                'error': True,
                'message': _('You do not have permission to delete this message.')
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Delete message
        success = MessageService.delete_message(request.user, message)
        
        if not success:
            return Response({
                'error': True,
                'message': _('Failed to delete message.')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(status=status.HTTP_204_NO_CONTENT)
        
    except Message.DoesNotExist:
        return Response({
            'error': True,
            'message': _('Message not found.')
        }, status=status.HTTP_404_NOT_FOUND)


# Call endpoints

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def initiate_call(request):
    """
    Initiate a call.
    
    POST /api/v1/calls/initiate
    """
    serializer = InitiateCallSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get target user and match
    try:
        target_user = User.objects.get(id=serializer.validated_data['target_user_id'])
        
        # Find match between users
        match = Match.objects.filter(
            Q(user1=request.user, user2=target_user) |
            Q(user1=target_user, user2=request.user),
            status=Match.ACTIVE
        ).first()
        
        if not match:
            return Response({
                'error': True,
                'message': _('No active match with this user.')
            }, status=status.HTTP_404_NOT_FOUND)
            
    except User.DoesNotExist:
        return Response({
            'error': True,
            'message': _('User not found.')
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Initiate call
    call, error_msg = CallService.initiate_call(
        caller=request.user,
        match=match,
        call_type=serializer.validated_data['call_type'],
        offer_sdp=serializer.validated_data['offer_sdp']
    )
    
    if not call:
        return Response({
            'error': True,
            'message': error_msg
        }, status=status.HTTP_400_BAD_REQUEST if 'premium' not in error_msg else status.HTTP_403_FORBIDDEN)
    
    # Serialize and return
    response_serializer = CallSerializer(call)
    
    return Response({
        'call_id': str(call.id),
        'status': call.status,
        'message': _('Call initiated. Waiting for response.')
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def answer_call(request, call_id):
    """
    Answer a call.
    
    POST /api/v1/calls/{call_id}/answer
    """
    try:
        call = Call.objects.get(id=call_id, callee=request.user)
    except Call.DoesNotExist:
        return Response({
            'error': True,
            'message': _('Call not found.')
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = AnswerCallSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Answer call
    success = CallService.answer_call(
        call=call,
        answer_sdp=serializer.validated_data['answer_sdp']
    )
    
    if not success:
        return Response({
            'error': True,
            'message': _('Failed to answer call. Call may have ended.')
        }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({
        'call_id': str(call.id),
        'status': call.status,
        'message': _('Call connected.')
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def add_ice_candidate(request, call_id):
    """
    Add ICE candidate for WebRTC.
    
    POST /api/v1/calls/{call_id}/ice-candidate
    """
    try:
        call = Call.objects.get(
            Q(caller=request.user) | Q(callee=request.user),
            id=call_id
        )
    except Call.DoesNotExist:
        return Response({
            'error': True,
            'message': _('Call not found.')
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = IceCandidateSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Add ICE candidate
    success = CallService.add_ice_candidate(
        call=call,
        candidate=serializer.validated_data['candidate'],
        from_user=request.user
    )
    
    if not success:
        return Response({
            'error': True,
            'message': _('Failed to add ICE candidate.')
        }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def end_call(request, call_id):
    """
    End a call.
    
    POST /api/v1/calls/{call_id}/terminate
    """
    try:
        call = Call.objects.get(
            Q(caller=request.user) | Q(callee=request.user),
            id=call_id
        )
    except Call.DoesNotExist:
        return Response({
            'error': True,
            'message': _('Call not found.')
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = EndCallSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # End call
    success = CallService.end_call(
        call=call,
        reason=serializer.validated_data['reason'],
        ended_by=request.user
    )
    
    if not success:
        return Response({
            'error': True,
            'message': _('Call already ended.')
        }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({
        'call_id': str(call.id),
        'status': call.status,
        'duration_seconds': call.duration_seconds,
        'message': _('Call ended.')
    }, status=status.HTTP_200_OK)