"""
Serializers for messaging app.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import Message, Call
from matching.models import Match

User = get_user_model()


class MessageSerializer(serializers.ModelSerializer):
    """
    Serializer for messages.
    """
    sender_id = serializers.UUIDField(source='sender.id', read_only=True)
    is_mine = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'client_message_id', 'sender_id', 'is_mine',
            'message_type', 'content', 'media_url', 'media_thumbnail_url',
            'status', 'created_at', 'delivered_at', 'read_at'
        ]
        read_only_fields = [
            'id', 'sender_id', 'status', 'created_at',
            'delivered_at', 'read_at'
        ]
    
    def get_is_mine(self, obj):
        """Check if message is from current user."""
        request = self.context.get('request')
        if request and request.user:
            return obj.sender == request.user
        return False


class ConversationSerializer(serializers.ModelSerializer):
    """
    Serializer for conversations (matches with messages).
    """
    other_user = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count_for_me = serializers.SerializerMethodField()
    
    class Meta:
        model = Match
        fields = [
            'id', 'other_user', 'last_message', 'unread_count_for_me',
            'created_at', 'last_message_at'
        ]
        read_only_fields = ['id', 'created_at', 'last_message_at']
    
    def get_other_user(self, obj):
        """Get the other user in the conversation."""
        request = self.context.get('request')
        if request and request.user:
            other_user = obj.get_other_user(request.user)
            photo = other_user.profile.photos.filter(is_main=True).first() if hasattr(other_user, 'profile') else None
            
            return {
                'user_id': str(other_user.id),
                'display_name': other_user.display_name,
                'main_photo_url': photo.photo_url if photo else None,
                'is_online': (timezone.now() - other_user.last_active).total_seconds() < 300
            }
        return None
    
    def get_last_message(self, obj):
        """Get the last message in the conversation."""
        if obj.last_message_at:
            # Get from match object for performance
            return {
                'content_preview': obj.last_message_preview,
                'sent_at': obj.last_message_at,
                'is_read_by_me': True  # This would need proper implementation
            }
        return None
    
    def get_unread_count_for_me(self, obj):
        """Get unread count for current user."""
        request = self.context.get('request')
        if request and request.user:
            return obj.get_unread_count(request.user)
        return 0


class SendMessageSerializer(serializers.Serializer):
    """
    Serializer for sending messages.
    """
    client_message_id = serializers.CharField(required=True, max_length=100)
    content = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    type = serializers.ChoiceField(
        choices=['text', 'image', 'video', 'audio'],
        default='text'
    )
    media_file_path_on_storage = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500
    )
    
    def validate(self, attrs):
        """Validate message data."""
        message_type = attrs.get('type', 'text')
        content = attrs.get('content', '')
        media_path = attrs.get('media_file_path_on_storage', '')
        
        if message_type == 'text' and not content:
            raise serializers.ValidationError({
                'content': _('Content is required for text messages.')
            })
        
        if message_type in ['image', 'video', 'audio'] and not media_path:
            raise serializers.ValidationError({
                'media_file_path_on_storage': _('Media file path is required for media messages.')
            })
        
        return attrs


class MarkAsReadSerializer(serializers.Serializer):
    """
    Serializer for marking messages as read.
    """
    last_read_message_id = serializers.UUIDField(required=False)


class CallSerializer(serializers.ModelSerializer):
    """
    Serializer for calls.
    """
    caller_info = serializers.SerializerMethodField()
    callee_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Call
        fields = [
            'id', 'call_type', 'status', 'caller_info', 'callee_info',
            'initiated_at', 'answered_at', 'ended_at', 'duration_seconds',
            'end_reason'
        ]
        read_only_fields = [
            'id', 'initiated_at', 'answered_at', 'ended_at',
            'duration_seconds', 'end_reason'
        ]
    
    def get_caller_info(self, obj):
        """Get caller information."""
        return {
            'user_id': str(obj.caller.id),
            'display_name': obj.caller.display_name
        }
    
    def get_callee_info(self, obj):
        """Get callee information."""
        return {
            'user_id': str(obj.callee.id),
            'display_name': obj.callee.display_name
        }


class InitiateCallSerializer(serializers.Serializer):
    """
    Serializer for initiating calls.
    """
    target_user_id = serializers.UUIDField()
    call_type = serializers.ChoiceField(choices=['audio', 'video'])
    offer_sdp = serializers.CharField()


class AnswerCallSerializer(serializers.Serializer):
    """
    Serializer for answering calls.
    """
    answer_sdp = serializers.CharField()


class IceCandidateSerializer(serializers.Serializer):
    """
    Serializer for ICE candidates.
    """
    candidate = serializers.DictField()


class EndCallSerializer(serializers.Serializer):
    """
    Serializer for ending calls.
    """
    reason = serializers.ChoiceField(
        choices=[
            'declined', 'ended_by_caller', 'ended_by_callee',
            'no_answer', 'connection_failed', 'duration_limit_reached'
        ]
    )