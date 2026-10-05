"""
Signals for messaging app.
"""
from django.db.models.signals import post_save
from django.db import transaction
from django.urls import reverse
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging
from contextlib import contextmanager
from django.utils.translation import gettext as _

from .models import Message, Call
from .tasks import send_message_notification

logger = logging.getLogger('hivmeet.messaging')


@contextmanager
def channel_layer_context():
    """
    Context manager for safely using channel layer.
    Yields None if Redis is not available.
    """
    layer = None
    try:
        layer = get_channel_layer()
    except Exception:
        logger.warning('Channel layer unavailable')
    yield layer


@receiver(post_save, sender=Message)
def handle_new_message(sender, instance, created, **kwargs):
    """Schedule message side effects only after the surrounding commit."""
    if not created or instance.message_type == Message.CALL_LOG:
        return

    transaction.on_commit(
        lambda message_id=instance.pk: dispatch_new_message_after_commit(message_id)
    )


def dispatch_new_message_after_commit(message_id):
    """Dispatch a committed message without exposing its content in logs."""
    try:
        instance = Message.objects.select_related(
            'match', 'sender', 'match__user1', 'match__user2'
        ).get(pk=message_id)
    except Message.DoesNotExist:
        return
    except Exception:
        logger.warning('Unable to load committed message for dispatch: message_id=%s', message_id)
        return

    recipient = None
    preview = ''
    notification = None
    preview_enabled = True
    try:
        recipient = instance.get_recipient()
        preview = instance.content[:100] if instance.content else _("[Media]")
        settings = recipient.notification_settings or {}
        preview_enabled = settings.get('message_preview_notifications', True)
        displayed_sender = instance.sender.display_name if preview_enabled else ''
        displayed_preview = preview if preview_enabled else ''

        # Persist first.  The UUID is then the exact same identifier in the
        # REST list, FCM payload and personal WebSocket event.
        from notifications.models import Notification
        notification = Notification.objects.create(
            user=recipient,
            type='new_message',
            title=displayed_sender or _("New message"),
            body=displayed_preview[:255],
            data={
                'type': 'new_message',
                'message_id': str(instance.id),
                'conversation_id': str(instance.match_id),
                'from_user_id': str(instance.sender_id),
                'sender_name': displayed_sender,
                'preview_enabled': preview_enabled,
            },
        )
        notification.data['notification_id'] = str(notification.id)
        notification.save(update_fields=['data'])
    except Exception:
        logger.warning('Message notification persistence failed: message_id=%s', instance.id)

    if notification is not None:
        try:
            send_message_notification.delay(
                recipient.id,
                instance.sender.id,
                preview,
                str(instance.match.id),
                message_id=str(instance.id),
                notification_id=str(notification.id),
                preview_enabled=preview_enabled,
            )
        except Exception:
            logger.warning('Message push dispatch failed: message_id=%s', instance.id)

    with channel_layer_context() as channel_layer:
        if channel_layer:
            try:
                protected_media_url = (
                    reverse(
                        'api:messaging:download-message-media',
                        kwargs={
                            'conversation_id': instance.match_id,
                            'message_id': instance.id,
                        },
                    )
                    if instance.media_file_path and not instance.is_deleted_for_everyone
                    else None
                )
                async_to_sync(channel_layer.group_send)(
                    f"conversation_{instance.match_id}",
                    {
                        "type": "message_created",
                        "message_id": str(instance.id),
                        "conversation_id": str(instance.match_id),
                        "sender_id": str(instance.sender_id),
                        "content": instance.content,
                        "message_type": instance.message_type,
                        "media_url": protected_media_url,
                        "media_type": (
                            instance.message_type
                            if instance.message_type in [Message.IMAGE, Message.VIDEO, Message.AUDIO]
                            else None
                        ),
                        "media_thumbnail_url": None,
                        "media_download_url": protected_media_url,
                        "media_mime_type": instance.media_mime_type or None,
                        "media_size_bytes": instance.media_size_bytes,
                        "media_file_name": instance.media_file_name or None,
                        "media_duration_ms": instance.media_duration_ms,
                        "sent_at": instance.created_at.isoformat(),
                        "client_message_id": instance.client_message_id or None,
                    }
                )
            except Exception:
                logger.warning('Message websocket dispatch failed: message_id=%s', instance.id)

            # The conversation group only reaches clients that already have this
            # chat open.  The recipient's personal group is what lets the
            # conversation list and the global unread badge update in real time
            # from any screen, without depending on a registered FCM token.
            if recipient is not None:
                try:
                    async_to_sync(channel_layer.group_send)(
                        f"user_{recipient.id}",
                        {
                            "type": "new_message",
                            "conversation_id": str(instance.match_id),
                            "message_id": str(instance.id),
                            "from_user_id": str(instance.sender_id),
                            "sender_name": (instance.sender.display_name if preview_enabled else ''),
                            "preview": preview if preview_enabled else '',
                            "notification_id": str(notification.id) if notification else None,
                            "unread_count": instance.match.get_unread_count(recipient),
                        }
                    )
                except Exception:
                    logger.warning(
                        'User-notification websocket dispatch failed: message_id=%s',
                        instance.id,
                    )


@receiver(post_save, sender=Call)
def handle_call_update(sender, instance, created, **kwargs):
    """
    Handle call updates.
    Broadcasts call events to the conversation group and to each participant's
    personal group, so a callee who is not currently viewing the chat still
    receives the ring over WebSocket.
    """
    # ``add_ice_candidate`` saves the same row repeatedly while a call is
    # ringing or answered.  Without this guard every ICE candidate would
    # re-broadcast ``incoming_call``/``call_update`` and make the callee ring
    # again.  A save that explicitly excludes ``status`` cannot be a state
    # transition, so it carries no call event.
    update_fields = kwargs.get('update_fields')
    if not created and update_fields is not None and 'status' not in update_fields:
        return

    with channel_layer_context() as channel_layer:
        if not channel_layer:
            return

        try:
            match_id = str(instance.match_id)

            if instance.status == Call.RINGING:
                payload = {
                    "type": "incoming_call",
                    "call": {
                        "id": str(instance.id),
                        "caller_id": str(instance.caller_id),
                        "caller_name": instance.caller.display_name,
                        "call_type": instance.call_type,
                        "match_id": match_id,
                    }
                }
                async_to_sync(channel_layer.group_send)(
                    f"conversation_{match_id}", payload
                )
                # Only the callee needs a ring on their personal channel.
                async_to_sync(channel_layer.group_send)(
                    f"user_{instance.callee_id}", payload
                )

            elif instance.status in [Call.ANSWERED, Call.ENDED, Call.DECLINED]:
                payload = {
                    "type": "call_update",
                    "call": {
                        "id": str(instance.id),
                        "status": instance.status,
                        "end_reason": instance.end_reason if instance.status == Call.ENDED else None,
                        "match_id": match_id,
                    }
                }
                async_to_sync(channel_layer.group_send)(
                    f"conversation_{match_id}", payload
                )
                # Both participants must be able to dismiss a stale call UI
                # even when neither has the conversation socket open.
                async_to_sync(channel_layer.group_send)(
                    f"user_{instance.caller_id}", payload
                )
                async_to_sync(channel_layer.group_send)(
                    f"user_{instance.callee_id}", payload
                )

        except Exception:
            logger.warning('Call websocket dispatch failed')
