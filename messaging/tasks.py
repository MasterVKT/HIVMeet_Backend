"""
Asynchronous tasks for messaging app.
"""
from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _
from firebase_admin import messaging
import logging

from notifications.fcm import send_fcm_to_user
from notifications.payloads import message_payload

logger = logging.getLogger('hivmeet.messaging')
User = get_user_model()


class FCMTemporaryDeliveryError(RuntimeError):
    """A known temporary FCM failure eligible for a bounded task retry."""


@shared_task(bind=True, max_retries=3)
def send_message_notification(
    self,
    recipient_id,
    sender_id,
    message_preview,
    match_id,
    message_id=None,
    notification_id=None,
    preview_enabled=True,
):
    """
    Send push notification for new message.

    ``message_id`` is optional only so that tasks already queued with the
    previous signature keep working across a deploy; the caller always supplies
    it. Without it the FCM ``notification_id`` would collapse to one value per
    sender, colliding across every message from that sender and disagreeing
    with the persisted ``Notification.data.notification_id``.
    """
    try:
        recipient = User.objects.get(id=recipient_id)
        sender = User.objects.get(id=sender_id)

        # Respect des préférences utilisateur
        notification_settings = recipient.notification_settings or {}
        if not notification_settings.get('new_message_notifications', True):
            return

        # A general online heartbeat says nothing about which screen is open.
        # Always dispatch the push after persisting the notification. Flutter
        # alone suppresses its foreground popup when this exact conversation
        # is visible; every other app state remains eligible for FCM.

        data = message_payload(
            message_id=str(message_id if message_id is not None else sender_id),
            conversation_id=str(match_id),
            sender_display_name=sender.display_name,
            sender_id=str(sender.id),
            preview=message_preview or '',
            notification_id=str(notification_id) if notification_id else None,
            preview_enabled=bool(preview_enabled),
        )

        notif = messaging.Notification(
            title=data['title'],
            body=data['body'],
        )

        delivery = send_fcm_to_user(recipient, notification=notif, data=data)

    except User.DoesNotExist:
        logger.error('Message notification recipient or sender not found')
        return
    except Exception:
        logger.error('Message notification delivery failed')
        return

    # Retrying a multicast after partial success would duplicate the message
    # for devices that already received it. The helper asks for a retry only
    # when every attempted token failed with a known transient FCM code.
    if delivery.get('retryable'):
        retry_number = self.request.retries + 1
        delay_seconds = min(2 ** retry_number, 30)
        logger.warning(
            'FCM temporary delivery failure: message_id=%s retry=%s delay_seconds=%s',
            message_id,
            retry_number,
            delay_seconds,
        )
        raise self.retry(
            exc=FCMTemporaryDeliveryError('temporary FCM delivery failure'),
            countdown=delay_seconds,
        )


@shared_task
def send_call_notification(callee_id, caller_id, call_type, match_id):
    """
    Send push notification for incoming call.
    """
    try:
        callee = User.objects.get(id=callee_id)
        caller = User.objects.get(id=caller_id)

        call_type_text = _("Audio call") if call_type == 'audio' else _("Video call")
        notif = messaging.Notification(
            title=f"{call_type_text} from {caller.display_name}",
            body=_("Tap to answer"),
        )

        data = {
            'type': 'incoming_call',
            'notification_id': f'call_{match_id}_{caller_id}',
            'notification_type': 'INCOMING_CALL',
            'call_type': call_type,
            'caller_id': str(caller_id),
            'caller_name': caller.display_name,
            'match_id': str(match_id),
            'conversation_id': str(match_id),
            'click_action': 'FLUTTER_NOTIFICATION_CLICK',
        }

        android = messaging.AndroidConfig(
            priority='high',
            ttl=30,
        )
        apns = messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    content_available=True,
                    sound='ringtone.caf',
                )
            )
        )

        send_fcm_to_user(callee, notification=notif, data=data, android=android, apns=apns)

    except User.DoesNotExist:
        logger.error('Call notification recipient or caller not found')
    except Exception:
        logger.error('Call notification delivery failed')


@shared_task
def send_read_notification(
    recipient_id,
    reader_id,
    match_id,
    message_id,
    notification_id=None,
):
    """Deliver a persisted Premium read alert through FCM.

    The first four arguments retain the previous task signature, so a task
    queued during a rolling deployment stays valid.  New tasks provide the
    canonical persisted notification UUID; an FCM failure never removes it.
    """
    try:
        recipient = User.objects.get(id=recipient_id)
        reader = User.objects.get(id=reader_id)

        from notifications.read_receipt_alerts import is_read_receipt_alert_enabled

        # A delayed task can run after expiry or an explicit opt-out.  The
        # persistent record remains in the list, while the system delivery is
        # correctly skipped for the current state.
        if not is_read_receipt_alert_enabled(recipient):
            return

        data = {
            'type': 'message_read',
            'notification_id': str(notification_id or f'read_{message_id}'),
            'conversation_id': str(match_id),
            'reader_id': str(reader_id),
            'reader_name': reader.display_name,
            'representative_message_id': str(message_id),
            'message_count': '1',
            'click_action': 'FLUTTER_NOTIFICATION_CLICK',
        }
        if notification_id is not None:
            from notifications.models import Notification

            persisted = Notification.objects.filter(
                id=notification_id,
                user=recipient,
                type='message_read',
            ).only('data').first()
            if persisted is None:
                logger.warning('Persisted read alert unavailable for FCM delivery')
                return
            persisted_data = persisted.data or {}
            # FCM data values must be strings.  The row stays authoritative
            # and contains no message content.
            data.update({
                'notification_id': str(persisted.id),
                'conversation_id': str(persisted_data.get('conversation_id', match_id)),
                'reader_id': str(persisted_data.get('reader_id', reader_id)),
                'reader_name': str(persisted_data.get('reader_name', reader.display_name)),
                'representative_message_id': str(
                    persisted_data.get('representative_message_id', message_id)
                ),
                'message_count': str(persisted_data.get('message_count', 1)),
                'read_at': str(persisted_data.get('read_at', '')),
            })

        notif = messaging.Notification(
            title=_("Message read"),
            body=_("Your message was read"),
        )
        send_fcm_to_user(recipient, notification=notif, data=data)

    except User.DoesNotExist:
        logger.error('Read notification recipient or reader not found')
    except Exception:
        logger.error('Read notification delivery failed')


# Note: send_match_notification is now handled in matching/tasks.py to avoid duplication
