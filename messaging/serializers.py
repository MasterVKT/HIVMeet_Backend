"""Serializers for messaging app."""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.urls import reverse
from .models import Message, Call
from .presence import PresenceService
from .services import MessageContentRejected, sanitize_message_content
from matching.models import Match

User = get_user_model()

class MessageSerializer(serializers.ModelSerializer):
    """
    Serializer for messages.
    """
    message_id = serializers.UUIDField(source='id', read_only=True)
    conversation_id = serializers.UUIDField(source='match.id', read_only=True)
    sender_id = serializers.UUIDField(source='sender.id', read_only=True)
    sent_at = serializers.DateTimeField(source='created_at', read_only=True)
    read_at_by_recipient = serializers.DateTimeField(source='read_at', read_only=True)
    is_sending = serializers.SerializerMethodField()
    media_type = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()
    media_url = serializers.SerializerMethodField()
    media_thumbnail_url = serializers.SerializerMethodField()
    media_download_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'message_id', 'id', 'client_message_id', 'conversation_id', 'sender_id', 'is_mine',
            'content', 'message_type', 'media_url', 'media_type', 'media_thumbnail_url',
            'media_download_url', 'media_mime_type', 'media_size_bytes',
            'media_file_name', 'media_duration_ms',
            'status', 'sent_at', 'created_at', 'delivered_at', 'read_at', 'read_at_by_recipient',
            'edited_at', 'is_deleted_for_everyone',
            'is_sending'
        ]
        read_only_fields = [
            'id', 'sender_id', 'status', 'created_at',
            'delivered_at', 'read_at', 'edited_at'
        ]

    def get_is_sending(self, obj):
        return obj.status == Message.SENDING

    def get_media_type(self, obj):
        if obj.is_deleted_for_everyone:
            return None
        if obj.message_type in [Message.IMAGE, Message.VIDEO, Message.AUDIO]:
            return obj.message_type
        return None

    def _protected_media_url(self, obj):
        """Return the authorised proxy route, never a storage/media URL."""
        if obj.is_deleted_for_everyone or not obj.media_file_path:
            return None
        path = reverse(
            'api:messaging:download-message-media',
            kwargs={'conversation_id': obj.match_id, 'message_id': obj.id},
        )
        request = self.context.get('request')
        return request.build_absolute_uri(path) if request else path

    def get_media_url(self, obj):
        return self._protected_media_url(obj)

    def get_media_thumbnail_url(self, obj):
        # Historic thumbnails were storage URLs. Do not expose them while a
        # separate authorised thumbnail rendition does not yet exist.
        return None

    def get_media_download_url(self, obj):
        """Authenticated URL used only when a user asks to save an attachment."""
        return self._protected_media_url(obj)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.is_deleted_for_everyone:
            representation['content'] = ''
            representation['media_mime_type'] = None
            representation['media_size_bytes'] = None
            representation['media_file_name'] = None
            representation['media_duration_ms'] = None
        return representation
    
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
    conversation_id = serializers.UUIDField(source='id', read_only=True)
    other_user = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count_for_me = serializers.SerializerMethodField()
    last_activity_at = serializers.DateTimeField(source='last_message_at', read_only=True)
    
    class Meta:
        model = Match
        fields = [
            'conversation_id', 'id', 'other_user', 'last_message', 'unread_count_for_me',
            'created_at', 'last_message_at', 'last_activity_at'
        ]
        read_only_fields = ['id', 'created_at', 'last_message_at']
    
    def get_other_user(self, obj):
        """Get the other user in the conversation."""
        request = self.context.get('request')
        if request and request.user:
            other_user = obj.get_other_user(request.user)
            profile = getattr(other_user, 'profile', None)
            main_photos = getattr(profile, 'main_photo_list', None) if profile else None
            if main_photos is None:
                photo = profile.photos.filter(is_main=True).first() if profile else None
            else:
                photo = main_photos[0] if main_photos else None

            snapshot = self._presence_snapshot(obj, other_user)
            return {
                'user_id': str(other_user.id),
                'display_name': other_user.display_name,
                'main_photo_url': self._normalize_photo(photo, request),
                'presence_visible': snapshot['visibility'],
                'is_online': snapshot['is_online'],
                'last_active': snapshot['last_active'],
                'presence_server_timestamp': snapshot['server_timestamp'],
            }
        return None

    def _presence_snapshot(self, match, other_user):
        """Read view annotations when available, with a safe generic fallback.

        The conversation list annotates both participants' presence facts so
        serializing a page never grows linearly with its item count.  Other
        callers may still instantiate this serializer directly, therefore the
        authoritative service remains the fallback.
        """
        profile = getattr(other_user, 'profile', None)
        now = timezone.now()
        if not profile or not profile.show_online_status:
            return {
                'visibility': False,
                'is_online': False,
                'last_active': None,
                'server_timestamp': now,
            }

        prefix = 'user1_id' if other_user.pk == match.user1_id else 'user2_id'
        online_field = f'{prefix}_presence_is_online'
        last_active_field = f'{prefix}_presence_last_active'
        if hasattr(match, online_field) and hasattr(match, last_active_field):
            return {
                'visibility': True,
                'is_online': bool(getattr(match, online_field)),
                'last_active': getattr(match, last_active_field),
                'server_timestamp': now,
            }
        return PresenceService.snapshot_for(other_user)

    def _normalize_photo(self, photo, request):
        """Normalize photo URL via normalize_media_url (LOG-05)."""
        if not photo:
            return None
        from profiles.photo_storage import profile_photo_delivery_url
        return profile_photo_delivery_url(photo, request, thumbnail=True)
    
    def get_last_message(self, obj):
        """Get the last message in the conversation."""
        request = self.context.get('request')
        if not request:
            return None

        prefetched_messages = getattr(obj, 'prefetched_last_messages', None)
        if prefetched_messages is None:
            message = Message.objects.filter(
                match=obj, is_deleted_for_everyone=False
            ).order_by('-created_at', '-id').first()
        else:
            # ``prefetched_last_messages`` deliberately keeps the query cheap
            # for the conversation list.  It can however have been populated
            # just before a global deletion, so it still needs the same
            # visibility rule as the direct-query branch above.
            message = next(
                (
                    candidate
                    for candidate in prefetched_messages
                    if not candidate.is_deleted_for_everyone
                ),
                None,
            )
        if not message:
            return None

        return {
            'message_id': str(message.id),
            'content_preview': message.content[:100] if message.content else _('Media'),
            'sender_id': str(message.sender_id),
            'sent_at': message.created_at,
            'is_read_by_me': message.sender_id == request.user.id or message.status == Message.READ,
        }
    
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

    def validate_content(self, value):
        """Apply the shared REST/WebSocket message-content policy."""
        try:
            return sanitize_message_content(value)
        except MessageContentRejected as exc:
            raise serializers.ValidationError(_(str(exc)))
    
    def validate(self, attrs):
        """Validate message data."""
        message_type = attrs.get('type', 'text')
        content = attrs.get('content', '')
        attrs['content'] = self.validate_content(content)
        content = attrs.get('content', '')

        if 'media_file_path_on_storage' in self.initial_data:
            raise serializers.ValidationError({
                'media_file_path_on_storage': _(
                    'Direct storage media uploads are no longer supported. '
                    'Use the multipart media endpoint.'
                )
            })

        if message_type != 'text':
            raise serializers.ValidationError({
                'type': _(
                    'Media messages must be sent through the multipart media endpoint.'
                )
            })
        
        if message_type == 'text' and not content:
            raise serializers.ValidationError({
                'content': _('Content is required for text messages.')
            })
        
        return attrs


class SendMediaMessageSerializer(serializers.Serializer):
    """
    Serializer for sending media messages (Premium feature).
    """
    media_file = serializers.FileField(required=True)
    media_type = serializers.ChoiceField(
        choices=['image', 'video', 'audio'],
        default='image'
    )
    text = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500
    )
    client_message_id = serializers.CharField(required=False, max_length=100)
    
    _allowed_media = {
        'image': {
            'extensions': {'.jpg', '.jpeg', '.png'},
            'mimes': {'image/jpeg', 'image/png'},
        },
        'video': {
            'extensions': {'.mp4', '.m4v'},
            'mimes': {'video/mp4', 'video/x-m4v'},
        },
        'audio': {
            'extensions': {'.mp3', '.m4a', '.aac', '.ogg', '.wav'},
            'mimes': {
                'audio/mpeg', 'audio/mp4', 'audio/aac', 'audio/ogg',
                'audio/wav', 'audio/x-wav',
            },
        },
    }

    def validate(self, attrs):
        attrs = super().validate(attrs)
        value = attrs['media_file']
        media_type = attrs['media_type']
        policy = self._allowed_media[media_type]
        import os

        extension = os.path.splitext(value.name or '')[1].lower()
        mime_type = (getattr(value, 'content_type', '') or '').lower().split(';')[0]
        if extension not in policy['extensions'] or mime_type not in policy['mimes']:
            raise serializers.ValidationError({
                'media_file': _('File extension or MIME type is not allowed for this media type.')
            })

        # UploadedFile supports seek; read only a small signature and restore
        # the cursor before Django stores it.  This rejects renamed text files
        # while avoiding a heavyweight decoder on the request path.
        header = value.read(16)
        value.seek(0)
        valid_content = {
            'image': header.startswith(b'\xff\xd8\xff') or header.startswith(b'\x89PNG\r\n\x1a\n'),
            'video': len(header) >= 8 and header[4:8] == b'ftyp',
            'audio': (
                header.startswith(b'ID3') or header.startswith(b'\xff\xfb')
                or header.startswith(b'\xff\xf3') or header.startswith(b'\xff\xf1')
                or header.startswith(b'OggS') or header.startswith(b'RIFF')
            ),
        }[media_type]
        if not valid_content:
            raise serializers.ValidationError({
                'media_file': _('File contents do not match the declared media type.')
            })
        return attrs

    def validate_media_file(self, value):
        """Validate media file size before its content is inspected."""
        # Max file size: 10MB
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError(
                _('File size must be less than 10MB.')
            )
        
        return value

    def validate_text(self, value):
        try:
            return sanitize_message_content(value)
        except MessageContentRejected as exc:
            raise serializers.ValidationError(_(str(exc)))


class ConversationListQuerySerializer(serializers.Serializer):
    """Strictly validate the public conversation-list query contract."""

    status = serializers.ChoiceField(
        choices=('all', 'unread', 'archived'),
        required=False,
        default='all',
    )
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=50,
        default=20,
    )


class ConversationMessagesQuerySerializer(serializers.Serializer):
    """Validate message-history cursors before they reach ORM pagination."""

    limit = serializers.IntegerField(required=False, min_value=1, max_value=50)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=50)
    before_message_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        attrs['resolved_limit'] = attrs.get('limit', attrs.get('page_size', 50))
        return attrs


class MarkAsReadSerializer(serializers.Serializer):
    """
    Serializer for marking messages as read.
    """
    last_read_message_id = serializers.UUIDField(required=False, allow_null=True)


class EditMessageSerializer(serializers.Serializer):
    """Validated payload for a Premium text-message edit."""

    content = serializers.CharField(required=True, allow_blank=False, max_length=1000)

    def validate_content(self, value):
        try:
            cleaned = sanitize_message_content(value)
        except MessageContentRejected as exc:
            raise serializers.ValidationError(_(str(exc)))
        if not cleaned:
            raise serializers.ValidationError(_('Content is required for text messages.'))
        return cleaned


class DeleteMessagesSerializer(serializers.Serializer):
    """Atomic local/global deletion request for one conversation."""

    message_ids = serializers.ListField(
        child=serializers.UUIDField(), min_length=1, max_length=100,
    )
    scope = serializers.ChoiceField(choices=('for_me', 'for_everyone'))

    def validate_message_ids(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError(_('Each message may be selected only once.'))
        return value


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
