"""
Asynchronous tasks for messaging app.
"""
from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _
from firebase_admin import messaging
import logging

logger = logging.getLogger('hivmeet.messaging')
User = get_user_model()


@shared_task
def send_message_notification(recipient_id, sender_id, message_preview, match_id):
    """
    Send push notification for new message.
    """
    try:
        recipient = User.objects.get(id=recipient_id)
        sender = User.objects.get(id=sender_id)
        
        # Check notification settings
        notification_settings = recipient.notification_settings or {}
        if not notification_settings.get('new_message_notifications', True):
            return
        
        # Get FCM tokens
        tokens = [token['token'] for token in recipient.fcm_tokens if token.get('token')]
        
        if not tokens:
            logger.warning(f"No FCM tokens found for user {recipient.email}")
            return
        
        # Create notification
        notification = messaging.Notification(
            title=sender.display_name,
            body=message_preview
        )
        
        # Create message
        message = messaging.MulticastMessage(
            notification=notification,
            data={
                'notification_type': 'NEW_MESSAGE',
                'conversation_id': match_id,
                'sender_id': str(sender_id),
                'sender_name': sender.display_name,
                'message_preview': message_preview,
                'click_action': 'FLUTTER_NOTIFICATION_CLICK'
            },
            tokens=tokens
        )
        
        # Send notification
        response = messaging.send_multicast(message)
        
        logger.info(
            f"Message notification sent to {recipient.email}: "
            f"{response.success_count} successful, {response.failure_count} failed"
        )
        
    except User.DoesNotExist:
        logger.error(f"User not found: {recipient_id} or {sender_id}")
    except Exception as e:
        logger.error(f"Error sending message notification: {str(e)}")


@shared_task
def send_call_notification(callee_id, caller_id, call_type, match_id):
    """
    Send push notification for incoming call.
    """
    try:
        callee = User.objects.get(id=callee_id)
        caller = User.objects.get(id=caller_id)
        
        # Get FCM tokens
        tokens = [token['token'] for token in callee.fcm_tokens if token.get('token')]
        
        if not tokens:
            logger.warning(f"No FCM tokens found for user {callee.email}")
            return
        
        # Create notification
        call_type_text = _("Audio call") if call_type == 'audio' else _("Video call")
        notification = messaging.Notification(
            title=f"{call_type_text} from {caller.display_name}",
            body=_("Tap to answer")
        )
        
        # Create message with high priority
        message = messaging.MulticastMessage(
            notification=notification,
            data={
                'notification_type': 'INCOMING_CALL',
                'call_type': call_type,
                'caller_id': str(caller_id),
                'caller_name': caller.display_name,
                'match_id': match_id,
                'click_action': 'FLUTTER_NOTIFICATION_CLICK'
            },
            android=messaging.AndroidConfig(
                priority='high',
                ttl=30  # 30 seconds TTL for call notifications
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        content_available=True,
                        sound='ringtone.caf'
                    )
                )
            ),
            tokens=tokens
        )
        
        # Send notification
        response = messaging.send_multicast(message)
        
        logger.info(
            f"Call notification sent to {callee.email}: "
            f"{response.success_count} successful"
        )
        
    except User.DoesNotExist:
        logger.error(f"User not found: {callee_id} or {caller_id}")
    except Exception as e:
        logger.error(f"Error sending call notification: {str(e)}")


# Note: send_match_notification is now handled in matching/tasks.py to avoid duplication