"""
Messaging services.
"""
from __future__ import annotations
from django.contrib.auth import get_user_model
from django.db.models import Q, F, Count
from django.utils import timezone
from django.utils.translation import gettext as _
from django.core.cache import cache
from django.conf import settings
from typing import List, Optional, Tuple, TYPE_CHECKING
from uuid import uuid4
import logging

if TYPE_CHECKING:
    from authentication.models import User as AuthUser

from matching.models import Match
from .models import Message, Call, TypingIndicator
from .tasks import send_call_notification, send_read_notification
from subscriptions.utils import check_feature_availability

logger = logging.getLogger('hivmeet.messaging')
User = get_user_model()


class MessageService:
    """
    Service for handling messages.
    """
    
    @staticmethod
    def get_conversation_messages(user: 'AuthUser', match: Match, limit: int = 50, before_id: Optional[str] = None) -> List[Message]:
        """
        Get messages for a conversation with pagination.
        """
        # Base query
        query = Message.objects.filter(match=match)
        
        # Filter out deleted messages
        query = query.filter(
            Q(sender=user, is_deleted_by_sender=False) |
            Q(sender=match.get_other_user(user), is_deleted_by_recipient=False)
        )
        
        # Apply cursor pagination
        if before_id:
            try:
                before_message = Message.objects.get(id=before_id, match=match)
                query = query.filter(created_at__lt=before_message.created_at)
            except Message.DoesNotExist:
                pass
        
        # Limit history for non-premium users
        if not user.is_premium:
            query = query.order_by('-created_at')[:50]
        else:
            query = query.order_by('-created_at')
        
        # Apply response cap
        messages = list(query[:limit])
        
        # Auto-mark received unread messages as read
        unread_ids = [
            msg.id for msg in messages
            if msg.sender != user and msg.status in [Message.SENT, Message.DELIVERED]
        ]
        if unread_ids:
            read_at = timezone.now()
            latest_read_message_id = unread_ids[0]
            Message.objects.filter(id__in=unread_ids).update(
                status=Message.READ,
                read_at=read_at,
            )
            match.reset_unread(user)
            for msg in messages:
                if msg.id in unread_ids:
                    msg.status = Message.READ
                    msg.read_at = read_at
            try:
                send_read_notification.delay(
                    recipient_id=match.get_other_user(user).id,
                    reader_id=user.id,
                    match_id=str(match.id),
                    message_id=str(latest_read_message_id),
                )
            except Exception as exc:
                logger.warning(f"Failed to queue read notification: {exc}")

        return messages
    
    @staticmethod
    def send_message(
        sender: 'AuthUser',
        match: Match,
        content: str,
        message_type: str = Message.TEXT,
        media_file_path: Optional[str] = None,
        client_message_id: Optional[str] = None
    ) -> Tuple[Optional[Message], Optional[str]]:
        """
        Send a message in a conversation.
        Returns (message, error_message).
        """
        # Verify sender is part of the match
        if sender not in [match.user1, match.user2]:
            return None, _("You are not part of this conversation.")
        
        # Check if match is active
        if match.status != Match.ACTIVE:
            return None, _("This conversation is no longer active.")
        
        # Check for duplicate client message ID
        if client_message_id:
            existing = Message.objects.filter(
                match=match,
                client_message_id=client_message_id
            ).first()
            if existing:
                return existing, None
        
        # Validate media messages for premium users only
        if message_type in [Message.IMAGE, Message.VIDEO, Message.AUDIO]:
            feature_check = check_feature_availability(sender, 'media_messaging')
            if not feature_check['available']:
                return None, _("Sending media messages is a premium feature.")
            
            if not media_file_path:
                return None, _("Media file path is required for media messages.")
        
        # Create message
        try:
            normalized_content = content or ''
            normalized_media_file_path = media_file_path or ''

            message = Message.objects.create(
                match=match,
                sender=sender,
                content=normalized_content,
                message_type=message_type,
                media_file_path=normalized_media_file_path,
                client_message_id=client_message_id,
                status=Message.SENT
            )
            
            # Update match last message info
            match.last_message_at = message.created_at
            match.last_message_preview = normalized_content[:100] if normalized_content else _("[Media]")
            match.save(update_fields=['last_message_at', 'last_message_preview'])

            # Update unread count for recipient
            recipient = match.get_other_user(sender)
            match.increment_unread(recipient)
            
            # TODO: Send push notification to recipient
            
            return message, None
            
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            return None, _("Failed to send message. Please try again.")
    
    @staticmethod
    def delete_message(user: 'AuthUser', message: Message) -> bool:
        """
        Delete a message for a user (soft delete).
        """
        if user == message.sender:
            message.is_deleted_by_sender = True
        elif user == message.get_recipient():
            message.is_deleted_by_recipient = True
        else:
            return False
        
        message.save(update_fields=['is_deleted_by_sender', 'is_deleted_by_recipient'])
        return True
    
    @staticmethod
    def update_typing_indicator(user: 'AuthUser', match: Match, is_typing: bool):
        """
        Update typing indicator for a user in a conversation.
        """
        if is_typing:
            TypingIndicator.objects.update_or_create(
                match=match,
                user=user,
                defaults={'is_typing': True}
            )
        else:
            TypingIndicator.objects.filter(
                match=match,
                user=user
            ).delete()

        # Cache typing status for real-time updates
        cache_key = f"typing_{match.id}_{user.id}"
        if is_typing:
            cache.set(cache_key, True, timeout=10)  # Expire after 10 seconds
        else:
            cache.delete(cache_key)

    @staticmethod
    def mark_messages_as_read(user: 'AuthUser', match: Match, last_read_message_id: Optional[str] = None) -> int:
        """
        Mark received messages as read up to an optional message.
        """
        other_user = match.get_other_user(user)
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

            latest_message = query.order_by('-created_at').first()
            updated_count = query.update(status=Message.READ, read_at=timezone.now())
        if updated_count:
            match.reset_unread(user)
            if latest_message:
                try:
                    send_read_notification.delay(
                        recipient_id=other_user.id,
                        reader_id=user.id,
                        match_id=str(match.id),
                        message_id=str(latest_message.id),
                    )
                except Exception as exc:
                    logger.warning(f"Failed to queue read notification: {exc}")
        return updated_count

    @staticmethod
    def mark_single_message_as_read(user: 'AuthUser', message: Message) -> bool:
        """
        Mark a single message as read if the user is the recipient.
        """
        if user == message.sender:
            return False
        if user not in [message.match.user1, message.match.user2]:
            return False

        if message.status in [Message.SENT, Message.DELIVERED]:
            message.status = Message.READ
            message.read_at = timezone.now()
            message.save(update_fields=['status', 'read_at'])
            message.match.reset_unread(user)
            try:
                send_read_notification.delay(
                    recipient_id=message.sender_id,
                    reader_id=user.id,
                    match_id=str(message.match.id),
                    message_id=str(message.id),
                )
            except Exception as exc:
                logger.warning(f"Failed to queue read notification: {exc}")
        return True

    @staticmethod
    def create_media_message(
        sender: 'AuthUser',
        match: Match,
        media_file,
        media_type: str,
        text: str = '',
        client_message_id: Optional[str] = None,
    ) -> Message:
        """
        Persist a media message from uploaded file metadata.
        """
        media_file_path = f"messages/{match.id}/{uuid4()}_{media_file.name}"
        media_url = f"{getattr(settings, 'MEDIA_URL', '/media/')}{media_file_path}"

        message, error = MessageService.send_message(
            sender=sender,
            match=match,
            content=text,
            message_type=media_type,
            media_file_path=media_file_path,
            client_message_id=client_message_id,
        )
        if not message:
            raise ValueError(error or "Unable to create media message")

        message.media_url = media_url
        message.save(update_fields=['media_url'])
        return message
    
    @staticmethod
    def get_typing_users(match: Match, exclude_user: Optional['AuthUser'] = None) -> List['AuthUser']:
        """
        Get users currently typing in a conversation.
        """
        # Check cache first
        users_typing = []
        
        for user in [match.user1, match.user2]:
            if exclude_user and user == exclude_user:
                continue
                
            cache_key = f"typing_{match.id}_{user.id}"
            if cache.get(cache_key):
                users_typing.append(user)
        
        return users_typing


class CallService:
    """
    Service for handling audio/video calls.
    """
    
    @staticmethod
    def initiate_call(
        caller: 'AuthUser',
        match: Match,
        call_type: str,
        offer_sdp: str
    ) -> Tuple[Optional[Call], Optional[str]]:
        """
        Initiate a call.
        Returns (call, error_message).
        """
        # Check if caller is premium
        can_call, error_msg = Call.check_call_limit(caller)
        if not can_call:
            return None, error_msg
        
        # Verify caller is part of the match
        if caller not in [match.user1, match.user2]:
            return None, _("You are not part of this conversation.")
        
        # Check if match is active
        if match.status != Match.ACTIVE:
            return None, _("This conversation is no longer active.")
        
        # Check for ongoing calls
        ongoing_call = Call.objects.filter(
            match=match,
            status__in=[Call.INITIATED, Call.RINGING, Call.ANSWERED]
        ).first()
        
        if ongoing_call:
            return None, _("There is already an ongoing call in this conversation.")
        
        # Get callee
        callee = match.get_other_user(caller)
        
        # Create call
        try:
            call = Call.objects.create(
                match=match,
                caller=caller,
                callee=callee,
                call_type=call_type,
                offer_sdp=offer_sdp,
                status=Call.RINGING
            )

            try:
                send_call_notification.delay(
                    callee_id=callee.id,
                    caller_id=caller.id,
                    call_type=call_type,
                    match_id=str(match.id),
                )
            except Exception as exc:
                logger.warning(f"Failed to queue call notification: {exc}")
            
            return call, None
            
        except Exception as e:
            logger.error(f"Error initiating call: {str(e)}")
            return None, _("Failed to initiate call. Please try again.")
    
    @staticmethod
    def answer_call(call: Call, answer_sdp: str) -> bool:
        """
        Answer a call.
        """
        if call.status != Call.RINGING:
            return False
        
        call.status = Call.ANSWERED
        call.answered_at = timezone.now()
        call.answer_sdp = answer_sdp
        call.save(update_fields=['status', 'answered_at', 'answer_sdp'])
        
        return True
    
    @staticmethod
    def add_ice_candidate(call: Call, candidate: dict, from_user: 'AuthUser') -> bool:
        """
        Add ICE candidate for WebRTC negotiation.
        """
        if call.status not in [Call.RINGING, Call.ANSWERED]:
            return False
        
        # Verify user is part of the call
        if from_user not in [call.caller, call.callee]:
            return False
        
        # Add candidate
        call.ice_candidates.append({
            'from_user_id': str(from_user.id),
            'candidate': candidate,
            'timestamp': timezone.now().isoformat()
        })
        call.save(update_fields=['ice_candidates'])
        
        return True
    
    @staticmethod
    def end_call(call: Call, reason: str, ended_by: Optional['AuthUser'] = None) -> bool:
        """
        End a call.
        """
        if call.status in [Call.ENDED, Call.DECLINED, Call.MISSED, Call.FAILED]:
            return False
        
        # Determine final status based on reason
        if reason == 'declined':
            call.status = Call.DECLINED
        elif reason == 'no_answer' and call.status == Call.RINGING:
            call.status = Call.MISSED
        elif reason in ['connection_failed', 'duration_limit_reached']:
            call.status = Call.FAILED
        else:
            call.status = Call.ENDED
        
        call.ended_at = timezone.now()
        call.end_reason = reason
        
        # Calculate duration if call was answered
        if call.answered_at and call.status == Call.ENDED:
            duration = (call.ended_at - call.answered_at).total_seconds()
            call.duration_seconds = int(duration)
        
        call.save()
        
        # Create call log message
        Message.objects.create(
            match=call.match,
            sender=call.caller,
            message_type=Message.CALL_LOG,
            content=call._get_call_log_message()
        )
        
        return True