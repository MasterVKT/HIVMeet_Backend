"""
Signals for messaging app.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging
from django.utils.translation import gettext as _

from .models import Message, Call
from .tasks import send_message_notification

logger = logging.getLogger('hivmeet.messaging')
channel_layer = get_channel_layer()


@receiver(post_save, sender=Message)
def handle_new_message(sender, instance, created, **kwargs):
    """
    Handle new message creation.
    """
    if created and instance.message_type != Message.CALL_LOG:
        # Send push notification
        try:
            recipient = instance.get_recipient()
            send_message_notification.delay(
                recipient.id,
                instance.sender.id,
                instance.content[:100] if instance.content else _("[Media]"),
                str(instance.match.id)
            )
        except Exception as e:
            logger.error(f"Error sending message notification: {str(e)}")
        
        # Send real-time update via WebSocket
        if channel_layer:
            try:
                recipient = instance.get_recipient()
                
                # Serialize message data
                message_data = {
                    'id': str(instance.id),
                    'client_message_id': instance.client_message_id,
                    'sender_id': str(instance.sender.id),
                    'content': instance.content,
                    'message_type': instance.message_type,
                    'media_url': instance.media_url,
                    'created_at': instance.created_at.isoformat(),
                    'conversation_id': str(instance.match.id)
                }
                
                # Send to recipient
                async_to_sync(channel_layer.group_send)(
                    f"user_{recipient.id}",
                    {
                        "type": "new_message",
                        "message": message_data
                    }
                )
            except Exception as e:
                logger.error(f"Error sending WebSocket message: {str(e)}")


@receiver(post_save, sender=Call)
def handle_call_update(sender, instance, created, **kwargs):
    """
    Handle call updates.
    """
    if channel_layer:
        try:
            # Determine who to notify
            if instance.status == Call.RINGING:
                # Notify callee of incoming call
                target_user = instance.callee
                event_type = "incoming_call"
            elif instance.status in [Call.ANSWERED, Call.ENDED, Call.DECLINED]:
                # Notify both parties
                for user in [instance.caller, instance.callee]:
                    async_to_sync(channel_layer.group_send)(
                        f"user_{user.id}",
                        {
                            "type": "call_update",
                            "call": {
                                "id": str(instance.id),
                                "status": instance.status,
                                "end_reason": instance.end_reason if instance.status == Call.ENDED else None
                            }
                        }
                    )
                return
            else:
                return
            
            # Send notification
            async_to_sync(channel_layer.group_send)(
                f"user_{target_user.id}",
                {
                    "type": event_type,
                    "call": {
                        "id": str(instance.id),
                        "caller_id": str(instance.caller.id),
                        "caller_name": instance.caller.display_name,
                        "call_type": instance.call_type,
                        "match_id": str(instance.match.id)
                    }
                }
            )
        except Exception as e:
            logger.error(f"Error sending call update: {str(e)}")