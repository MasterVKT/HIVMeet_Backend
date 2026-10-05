"""
Messaging services.
"""
from __future__ import annotations
import re
import logging
import os
from datetime import timedelta
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple, TYPE_CHECKING

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.utils.text import get_valid_filename
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils.html import strip_tags
from django.utils import timezone
from django.utils.translation import gettext as _
from uuid import NAMESPACE_URL, uuid4, uuid5

if TYPE_CHECKING:
    from authentication.models import User as AuthUser

from matching.models import Match
from matching.free_access import FreeMatchAccessError, FreeMatchAccessService
from .models import Call, ConversationHiddenState, Message, TypingIndicator
from .presence import PresenceService
from .tasks import send_call_notification, send_read_notification
from notifications.read_receipt_alerts import is_read_receipt_alert_enabled
from subscriptions.utils import check_feature_availability, is_premium_user

logger = logging.getLogger('hivmeet.messaging')
User = get_user_model()


def _read_alert_notification_id(match_id, message_ids: Iterable[str]):
    """Return a deterministic UUID for one committed read batch."""
    batch_key = ','.join(sorted(str(message_id) for message_id in message_ids))
    return uuid5(NAMESPACE_URL, f'hivmeet:message-read:{match_id}:{batch_key}')


def _create_read_alert_notification(*, recipient, reader, match, message_ids, read_at):
    """Persist one Premium read alert in the receipt transaction.

    The notification has no message content.  The deterministic primary key
    protects the notification and its FCM/WebSocket fan-out from duplicate
    creation if the transaction path is retried.
    """
    if not is_read_receipt_alert_enabled(recipient):
        return None

    from notifications.models import Notification

    representative_message_id = str(message_ids[-1])
    notification_id = _read_alert_notification_id(match.id, message_ids)
    data = {
        'type': 'message_read',
        'notification_id': str(notification_id),
        'conversation_id': str(match.id),
        'reader_id': str(reader.id),
        'reader_name': reader.display_name,
        'representative_message_id': representative_message_id,
        'message_count': len(message_ids),
        'read_at': read_at.isoformat(),
    }
    notification, created = Notification.objects.get_or_create(
        id=notification_id,
        defaults={
            'user': recipient,
            'type': 'message_read',
            'title': _('Message read'),
            'body': '',
            'data': data,
        },
    )
    return notification if created else None


def _broadcast_read_alert(*, recipient_id, notification_id, payload):
    """Send the persisted Premium alert on the personal WebSocket only."""
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            f'user_{recipient_id}',
            {
                **payload,
                'type': 'message_read_alert',
                'notification_id': str(notification_id),
            },
        )
    except Exception:
        logger.warning('Read alert websocket dispatch failed')


def _broadcast_read_receipt(
    match: Match,
    reader: 'AuthUser',
    message_ids: Iterable[object],
    read_at,
    sender_id: object | None = None,
) -> None:
    """Broadcast a best-effort read receipt to the conversation WebSocket group.

    Persisting a read receipt is authoritative; real-time delivery is an
    enhancement.  A missing or failing channel layer must therefore never
    cause the REST marking endpoint to fail.

    ``sender_id`` is the author of the messages being acknowledged.  A second
    broadcast to their personal group is what makes their ticks flip while they
    are anywhere other than this conversation; the conversation group alone
    only reaches clients that already have the chat open.
    """
    try:
        serialized_message_ids = [str(message_id) for message_id in message_ids]
        if not serialized_message_ids:
            return

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        serialized_read_at = read_at.isoformat()
    except Exception:
        logger.warning('Failed to prepare message read receipt')
        return

    try:
        async_to_sync(channel_layer.group_send)(
            f'conversation_{match.id}',
            {
                'type': 'message_read',
                'reader_id': str(reader.id),
                'message_ids': serialized_message_ids,
                'read_at': serialized_read_at,
            },
        )
    except Exception:
        logger.warning('Failed to broadcast message read receipt')

    if sender_id is None:
        return

    # Delivered independently of the conversation broadcast: a failure on one
    # group must not suppress the other.
    try:
        async_to_sync(channel_layer.group_send)(
            f'user_{sender_id}',
            {
                'type': 'message_read',
                'conversation_id': str(match.id),
                'reader_id': str(reader.id),
                'message_ids': serialized_message_ids,
                'read_at': serialized_read_at,
            },
        )
    except Exception:
        logger.warning('Failed to broadcast personal read receipt')


def _broadcast_delivery_receipt(
    conversation_id: object,
    sender_id: object,
    message_ids: List[str],
    delivered_at,
) -> None:
    """Announce a delivery receipt on the conversation and the author's group.

    Mirrors :func:`_broadcast_read_receipt`: the conversation group updates a
    chat that is already open, the author's personal group updates their ticks
    from anywhere else. Delivery is best-effort and never blocks persistence.
    """
    if not message_ids:
        return

    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        serialized_delivered_at = delivered_at.isoformat()
    except Exception:
        logger.warning('Failed to prepare message delivery receipt')
        return

    payload = {
        'type': 'message_delivered',
        'conversation_id': str(conversation_id),
        'message_ids': message_ids,
        'delivered_at': serialized_delivered_at,
    }

    for group_name in (f'conversation_{conversation_id}', f'user_{sender_id}'):
        try:
            async_to_sync(channel_layer.group_send)(group_name, payload)
        except Exception:
            logger.warning('Failed to broadcast message delivery receipt')


DISALLOWED_MESSAGE_PATTERNS = (
    r'javascript\s*:',
    r'data:text/html',
    r'<\s*script',
)


class MessageContentRejected(ValueError):
    """Raised when message content contains explicitly unsafe markup."""


class InvalidReadCursor(ValueError):
    """Raised when a read cursor is not an incoming message in this match."""


class MessageDeletionRejected(ValueError):
    """A safe, stable reason why an atomic deletion cannot be applied."""

    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class MessageEditRejected(ValueError):
    """A safe, stable reason why a message edit cannot be applied."""

    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class ReadReceiptResult:
    """Authoritative result of a canonical message-read operation."""

    messages_marked: int
    message_ids: Tuple[str, ...]
    read_at: object | None
    unread_count_for_me: int


@dataclass(frozen=True)
class MessagePage:
    """Cursor page returned by the message history service."""

    messages: Tuple[Message, ...]
    has_more: bool


@dataclass(frozen=True)
class DeliveryReceipt:
    """Messages of a single conversation that just became ``delivered``."""

    conversation_id: str
    sender_id: str
    message_ids: Tuple[str, ...]
    delivered_at: object


def sanitize_message_content(raw_content: str | None) -> str:
    """Return safe plain text shared by every message write path.

    Dangerous URL schemes and script tags are rejected rather than silently
    altered, preserving the REST validation contract. Other HTML is reduced to
    plain text before persistence.
    """
    raw_value = raw_content or ''
    if not isinstance(raw_value, str):
        raise MessageContentRejected('Content must be a string.')

    for pattern in DISALLOWED_MESSAGE_PATTERNS:
        if re.search(pattern, raw_value, flags=re.IGNORECASE):
            raise MessageContentRejected(
                'Content contains unsupported or unsafe markup.'
            )
    return strip_tags(raw_value).strip()


def _delete_stored_media(media_file_path: str) -> None:
    """Best-effort cleanup for a blob whose message was not persisted."""
    try:
        default_storage.delete(media_file_path)
    except Exception:
        logger.warning('Unable to remove orphaned media blob')


def _recipient_has_active_client(recipient_id: object, match_id: object) -> bool:
    """Delivery receipt check backed by the single device-session service."""
    try:
        recipient = User.objects.only('id').get(pk=recipient_id)
        return PresenceService.is_online(recipient)
    except User.DoesNotExist:
        return False


class MessageService:
    """
    Service for handling messages.
    """
    
    @staticmethod
    def get_conversation_messages(
        user: 'AuthUser',
        match: Match,
        limit: int = 50,
        before_id: Optional[str] = None,
    ) -> MessagePage:
        """Return a stable, read-only cursor page of visible messages.

        The cursor is ordered by ``(created_at, id)`` so a timestamp collision
        cannot duplicate or omit a message.  Invalid cursors are deliberately
        rejected instead of silently falling back to the first page.
        """
        other_user = match.get_other_user(user)
        query = Message.objects.filter(match=match).filter(
            Q(is_deleted_for_everyone=True)
            | Q(sender=user, is_deleted_by_sender=False)
            | Q(sender=other_user, is_deleted_by_recipient=False)
        )

        if before_id:
            cursor = Message.objects.filter(id=before_id, match=match).only(
                'id', 'created_at'
            ).first()
            if cursor is None:
                raise InvalidReadCursor(_('Invalid message cursor.'))
            query = query.filter(
                Q(created_at__lt=cursor.created_at)
                | Q(created_at=cursor.created_at, id__lt=cursor.id)
            )

        # Fetch one extra row so `has_more` reflects the current cursor, not
        # the total history length.  A GET never changes read state.
        rows = list(query.order_by('-created_at', '-id')[: limit + 1])
        has_more = len(rows) > limit
        return MessagePage(messages=tuple(rows[:limit]), has_more=has_more)
    
    @staticmethod
    def send_message(
        sender: 'AuthUser',
        match: Match,
        content: str,
        message_type: str = Message.TEXT,
        media_file_path: Optional[str] = None,
        media_url: Optional[str] = None,
        media_mime_type: Optional[str] = None,
        media_size_bytes: Optional[int] = None,
        media_file_name: Optional[str] = None,
        media_duration_ms: Optional[int] = None,
        client_message_id: Optional[str] = None
    ) -> Tuple[Optional[Message], Optional[str]]:
        """
        Send a message in a conversation.
        Returns (message, error_message).
        """
        try:
            content = sanitize_message_content(content)
        except MessageContentRejected as exc:
            return None, str(exc)

        # Validate media messages for premium users only
        if message_type in [Message.IMAGE, Message.VIDEO, Message.AUDIO]:
            feature_check = check_feature_availability(sender, 'media_messaging')
            if not feature_check['available']:
                return None, _("Sending media messages is a premium feature.")
            
            if not media_file_path:
                return None, _("Media file path is required for media messages.")
        
        normalized_client_message_id = client_message_id or ''
        normalized_content = content or ''
        normalized_media_file_path = media_file_path or ''

        try:
            with transaction.atomic():
                locked_match = Match.objects.select_for_update().select_related(
                    'user1', 'user2'
                ).get(pk=match.pk)
                if sender.pk not in (locked_match.user1_id, locked_match.user2_id):
                    return None, _("You are not part of this conversation.")
                if locked_match.status != Match.ACTIVE:
                    return None, _("This conversation is no longer active.")

                if normalized_client_message_id:
                    existing = Message.objects.filter(
                        match=locked_match,
                        sender=sender,
                        client_message_id=normalized_client_message_id,
                    ).first()
                    if existing:
                        return existing, None

                # The entitlement is checked after the canonical idempotency
                # lookup and while the Match row is locked. A transport retry
                # with the same client_message_id cannot consume a second slot.
                if message_type == Message.TEXT:
                    try:
                        FreeMatchAccessService.ensure_can_send_text(
                            locked_match, sender
                        )
                    except FreeMatchAccessError as exc:
                        return None, exc

                try:
                    # The savepoint lets us recover from the database-level
                    # idempotency constraint without invalidating the locked
                    # outer transaction.
                    with transaction.atomic():
                        message = Message.objects.create(
                            match=locked_match,
                            sender=sender,
                            content=normalized_content,
                            message_type=message_type,
                            media_file_path=normalized_media_file_path,
                            media_url=media_url or '',
                            media_mime_type=media_mime_type or '',
                            media_size_bytes=media_size_bytes,
                            media_file_name=media_file_name or '',
                            media_duration_ms=media_duration_ms,
                            client_message_id=normalized_client_message_id,
                            status=Message.SENT,
                        )
                except IntegrityError:
                    if normalized_client_message_id:
                        existing = Message.objects.filter(
                            match=locked_match,
                            sender=sender,
                            client_message_id=normalized_client_message_id,
                        ).first()
                        if existing:
                            return existing, None
                    raise

                if message_type == Message.TEXT:
                    FreeMatchAccessService.record_sent_text(locked_match, sender)

                recipient = locked_match.get_other_user(sender)
                locked_match.last_message_at = message.created_at
                locked_match.last_message_preview = (
                    normalized_content[:100] if normalized_content else _("[Media]")
                )
                if recipient.pk == locked_match.user1_id:
                    locked_match.user1_unread_count += 1
                    unread_field = 'user1_unread_count'
                else:
                    locked_match.user2_unread_count += 1
                    unread_field = 'user2_unread_count'
                locked_match.save(
                    update_fields=['last_message_at', 'last_message_preview', unread_field]
                )

                # A validated incoming message makes the conversation visible
                # again only to its recipient.
                ConversationHiddenState.objects.filter(
                    match=locked_match,
                    user=recipient,
                ).delete()
                if _recipient_has_active_client(recipient.id, locked_match.id):
                    delivered_at = timezone.now()
                    message.status = Message.DELIVERED
                    message.delivered_at = delivered_at
                    message.save(update_fields=['status', 'delivered_at'])

                    def broadcast_immediate_delivery(
                        conversation_id=locked_match.id,
                        sender_id=sender.id,
                        message_id=str(message.id),
                        receipt_at=delivered_at,
                    ):
                        _broadcast_delivery_receipt(
                            conversation_id=conversation_id,
                            sender_id=sender_id,
                            message_ids=[message_id],
                            delivered_at=receipt_at,
                        )

                    transaction.on_commit(
                        broadcast_immediate_delivery
                    )
                return message, None
        except Match.DoesNotExist:
            return None, _("This conversation is no longer available.")
        except IntegrityError:
            logger.warning('Message creation constraint failed for match_id=%s', match.pk)
            return None, _("Failed to send message. Please try again.")
    
    @staticmethod
    def mark_incoming_as_delivered(
        user: 'AuthUser',
        match: Optional[Match] = None,
    ) -> List['DeliveryReceipt']:
        """Flip the user's incoming ``sent`` messages to ``delivered``.

        Called when a socket belonging to ``user`` connects, which is the
        natural "the device has the message" signal — the same semantics the
        mainstream messengers use for their second tick.  ``match=None`` sweeps
        every active conversation (notifications socket: the whole device came
        online); passing a match scopes it to that conversation.

        ``delivered`` is deliberately still counted as unread by
        :meth:`_mark_messages_as_read`, so this never disturbs unread counters.
        The bulk ``update`` also bypasses ``post_save``, so no message signal
        re-fires.
        """
        query = Message.objects.filter(
            status=Message.SENT,
            is_deleted_for_everyone=False,
        ).exclude(sender=user)
        if match is not None:
            query = query.filter(match=match)
        else:
            query = query.filter(
                Q(match__user1=user) | Q(match__user2=user),
                match__status=Match.ACTIVE,
            )

        rows = list(query.values_list('id', 'match_id', 'sender_id'))
        if not rows:
            return []

        delivered_at = timezone.now()
        # Compare-and-set on ``status``: a message the recipient managed to read
        # between the select above and this update must keep its ``read`` state
        # rather than be pushed back to ``delivered``.
        Message.objects.filter(
            id__in=[row[0] for row in rows],
            status=Message.SENT,
        ).update(
            status=Message.DELIVERED,
            delivered_at=delivered_at,
        )

        grouped: dict = {}
        for message_id, match_id, sender_id in rows:
            grouped.setdefault((match_id, sender_id), []).append(str(message_id))

        return [
            DeliveryReceipt(
                conversation_id=str(match_id),
                sender_id=str(sender_id),
                message_ids=tuple(ids),
                delivered_at=delivered_at,
            )
            for (match_id, sender_id), ids in grouped.items()
        ]

    @staticmethod
    def broadcast_delivery_receipts(receipts: Iterable['DeliveryReceipt']) -> None:
        """Best-effort real-time announcement for a batch of delivery receipts."""
        for receipt in receipts:
            _broadcast_delivery_receipt(
                conversation_id=receipt.conversation_id,
                sender_id=receipt.sender_id,
                message_ids=list(receipt.message_ids),
                delivered_at=receipt.delivered_at,
            )

    @staticmethod
    def edit_message(
        user: 'AuthUser',
        match: Match,
        message_id: object,
        content: str,
    ) -> Message:
        """Edit one eligible text message without changing its chronology."""
        try:
            clean_content = sanitize_message_content(content)
        except MessageContentRejected as exc:
            raise MessageEditRejected('invalid_content', str(exc)) from exc
        if not clean_content:
            raise MessageEditRejected(
                'invalid_content', _('Content is required for text messages.')
            )

        with transaction.atomic():
            try:
                locked_match = Match.objects.select_for_update().select_related(
                    'user1', 'user2'
                ).get(pk=match.pk, status=Match.ACTIVE)
            except Match.DoesNotExist as exc:
                raise MessageEditRejected(
                    'conversation_unavailable', _('Conversation not found.'), 404
                ) from exc

            if user.pk not in (locked_match.user1_id, locked_match.user2_id):
                raise MessageEditRejected(
                    'forbidden', _('You are not part of this conversation.'), 403
                )

            message = Message.objects.select_for_update().filter(
                pk=message_id, match=locked_match
            ).first()
            if message is None:
                raise MessageEditRejected('message_not_found', _('Message not found.'), 404)
            if message.sender_id != user.id:
                raise MessageEditRejected(
                    'edit_not_author', _('Only the author can edit this message.'), 403
                )
            if not is_premium_user(user):
                raise MessageEditRejected(
                    'premium_required',
                    _('This feature requires a premium subscription.'),
                    403,
                )
            if (
                message.message_type != Message.TEXT
                or message.is_deleted_for_everyone
                or message.is_deleted_by_sender
            ):
                raise MessageEditRejected(
                    'message_not_editable',
                    _('Only an intact text message can be edited.'),
                    409,
                )
            if message.created_at < timezone.now() - timedelta(minutes=15):
                raise MessageEditRejected(
                    'edit_window_expired',
                    _('Messages can be edited only within 15 minutes of sending.'),
                    403,
                )

            message.content = clean_content
            message.edited_at = timezone.now()
            message.save(update_fields=['content', 'edited_at'])
            MessageService._refresh_match_message_state(locked_match)
            transaction.on_commit(
                lambda message_id=str(message.id), match_id=locked_match.id,
                edited_content=message.content, edited_at=message.edited_at:
                MessageService._broadcast_message_updated(
                    match_id, message_id, edited_content, edited_at
                )
            )
            return message

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
    def delete_messages(
        user: 'AuthUser',
        match: Match,
        message_ids: Iterable[object],
        scope: str,
    ) -> None:
        """Apply a local or global deletion as one all-or-nothing operation.

        The service is the authority for REST and future WebSocket callers.
        It deliberately performs every eligibility check while holding the
        match lock, so a retry, a second device or a late receipt cannot cause
        a partial deletion.
        """
        ids = list(dict.fromkeys(str(value) for value in message_ids))
        if not ids:
            raise MessageDeletionRejected('invalid_request', _('No messages were selected.'))

        media_paths: list[str] = []
        deleted_message_ids: list[str] = []
        with transaction.atomic():
            try:
                locked_match = Match.objects.select_for_update().select_related(
                    'user1', 'user2'
                ).get(pk=match.pk, status=Match.ACTIVE)
            except Match.DoesNotExist as exc:
                raise MessageDeletionRejected(
                    'conversation_unavailable', _('Conversation not found.'), 404
                ) from exc

            if user.pk not in (locked_match.user1_id, locked_match.user2_id):
                raise MessageDeletionRejected('forbidden', _('You are not part of this conversation.'), 403)

            messages = list(
                Message.objects.select_for_update()
                .filter(match=locked_match, id__in=ids)
                .order_by('created_at', 'id')
            )
            if len(messages) != len(ids):
                raise MessageDeletionRejected('message_not_found', _('A selected message was not found.'), 404)

            if scope == 'for_me':
                sender_ids = [message.id for message in messages if message.sender_id == user.id]
                recipient_ids = [message.id for message in messages if message.sender_id != user.id]
                if sender_ids:
                    Message.objects.filter(id__in=sender_ids).update(is_deleted_by_sender=True)
                if recipient_ids:
                    Message.objects.filter(id__in=recipient_ids).update(is_deleted_by_recipient=True)
                return

            if scope != 'for_everyone':
                raise MessageDeletionRejected('invalid_scope', _('Unknown message deletion scope.'))
            if not is_premium_user(user):
                raise MessageDeletionRejected(
                    'premium_required', _('This feature requires a premium subscription.'), 403
                )

            deadline = timezone.now() - timedelta(minutes=15)
            invalid = [
                message for message in messages
                if message.sender_id != user.id or message.created_at < deadline
            ]
            if invalid:
                raise MessageDeletionRejected(
                    'global_delete_not_allowed',
                    _('Messages can be deleted for everyone only by their author within 15 minutes.'),
                    403,
                )

            targets = [message for message in messages if not message.is_deleted_for_everyone]
            if not targets:
                return
            media_paths = [message.media_file_path for message in targets if message.media_file_path]
            deleted_message_ids = [str(message.id) for message in targets]
            now = timezone.now()
            Message.objects.filter(id__in=[message.id for message in targets]).update(
                is_deleted_for_everyone=True,
                deleted_for_everyone_at=now,
                content='',
                media_url='',
                media_thumbnail_url='',
                media_file_path='',
                media_mime_type='',
                media_size_bytes=None,
                media_file_name='',
                media_duration_ms=None,
                edited_at=None,
            )

            # A deleted message must neither retain a push notification nor an
            # unread badge. JSON filtering is intentionally performed in Python
            # for the SQLite test database and PostgreSQL alike.
            from notifications.models import Notification
            notification_ids = [
                notification.id
                for notification in Notification.objects.filter(
                    user__in=(locked_match.user1, locked_match.user2), type='new_message'
                ).only('id', 'data')
                if str((notification.data or {}).get('message_id', '')) in deleted_message_ids
            ]
            if notification_ids:
                Notification.objects.filter(id__in=notification_ids).delete()

            MessageService._refresh_match_message_state(locked_match)

            transaction.on_commit(
                lambda: MessageService._broadcast_messages_deleted(
                    locked_match.id, deleted_message_ids
                )
            )
            transaction.on_commit(
                lambda: [_delete_stored_media(path) for path in set(media_paths)]
            )

    @staticmethod
    def _refresh_match_message_state(match: Match) -> None:
        """Rebuild only the denormalized fields affected by global deletion."""
        latest = Message.objects.filter(
            match=match, is_deleted_for_everyone=False
        ).order_by('-created_at', '-id').first()
        match.last_message_at = latest.created_at if latest else None
        match.last_message_preview = (
            latest.content[:100] if latest and latest.content else (_('[Media]') if latest else '')
        )
        match.user1_unread_count = Message.objects.filter(
            match=match,
            sender_id=match.user2_id,
            status__in=(Message.SENT, Message.DELIVERED),
            is_deleted_for_everyone=False,
        ).count()
        match.user2_unread_count = Message.objects.filter(
            match=match,
            sender_id=match.user1_id,
            status__in=(Message.SENT, Message.DELIVERED),
            is_deleted_for_everyone=False,
        ).count()
        match.save(update_fields=[
            'last_message_at', 'last_message_preview',
            'user1_unread_count', 'user2_unread_count',
        ])

    @staticmethod
    def _broadcast_message_updated(
        match_id: object,
        message_id: str,
        content: str,
        edited_at,
    ) -> None:
        """Broadcast a canonical edit after the database transaction commits."""
        try:
            channel_layer = get_channel_layer()
            if channel_layer is None:
                return
            async_to_sync(channel_layer.group_send)(
                f'conversation_{match_id}',
                {
                    'type': 'message_updated',
                    'conversation_id': str(match_id),
                    'message_id': message_id,
                    'content': content,
                    'edited_at': edited_at.isoformat(),
                },
            )
        except Exception:
            logger.warning('Failed to broadcast message update')

    @staticmethod
    def _broadcast_messages_deleted(match_id: object, message_ids: list[str]) -> None:
        if not message_ids:
            return
        try:
            channel_layer = get_channel_layer()
            if channel_layer is None:
                return
            async_to_sync(channel_layer.group_send)(
                f'conversation_{match_id}',
                {
                    'type': 'message_deleted',
                    'conversation_id': str(match_id),
                    'message_ids': message_ids,
                },
            )
        except Exception:
            logger.warning('Failed to broadcast message deletion')
    
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

        # Parity with the WebSocket ``typing.start``/``typing.stop`` path: a
        # REST caller must notify the other participant too, otherwise the
        # endpoint silently does nothing observable for them.
        try:
            channel_layer = get_channel_layer()
            if channel_layer is None:
                return
            async_to_sync(channel_layer.group_send)(
                f'conversation_{match.id}',
                {
                    'type': 'typing_indicator',
                    'user_id': str(user.id),
                    'status': 'typing' if is_typing else 'stopped',
                },
            )
        except Exception:
            logger.warning('Failed to broadcast typing indicator')

    @staticmethod
    def mark_messages_as_read(
        user: 'AuthUser',
        match: Match,
        last_read_message_id: Optional[str] = None,
    ) -> ReadReceiptResult:
        """Mark only incoming unread messages up to a validated cursor."""
        return MessageService._mark_messages_as_read(
            user=user,
            match=match,
            last_read_message_id=last_read_message_id,
        )

    @staticmethod
    def mark_single_message_as_read(
        user: 'AuthUser',
        match: Match,
        message_id: str,
    ) -> ReadReceiptResult:
        """Mark exactly one incoming message through the canonical service."""
        return MessageService._mark_messages_as_read(
            user=user,
            match=match,
            single_message_id=message_id,
        )

    @staticmethod
    def _mark_messages_as_read(
        user: 'AuthUser',
        match: Match,
        last_read_message_id: Optional[str] = None,
        single_message_id: Optional[str] = None,
    ) -> ReadReceiptResult:
        """Perform the locked, authoritative read receipt state transition."""
        if bool(last_read_message_id) and bool(single_message_id):
            raise ValueError('Only one read target may be supplied.')

        with transaction.atomic():
            try:
                locked_match = Match.objects.select_for_update().select_related(
                    'user1', 'user2'
                ).get(pk=match.pk)
            except Match.DoesNotExist as exc:
                raise InvalidReadCursor(_('Conversation is unavailable.')) from exc

            if user.pk not in (locked_match.user1_id, locked_match.user2_id):
                raise InvalidReadCursor(_('Invalid message read request.'))

            other_user = locked_match.get_other_user(user)
            unread_messages = Message.objects.select_for_update().filter(
                match=locked_match,
                sender=other_user,
                status__in=[Message.SENT, Message.DELIVERED],
                is_deleted_for_everyone=False,
            ).order_by('created_at', 'id')

            if single_message_id:
                target = Message.objects.filter(
                    id=single_message_id,
                    match=locked_match,
                    sender=other_user,
                ).only('id').first()
                if target is None:
                    raise InvalidReadCursor(_('Invalid message read request.'))
                unread_messages = unread_messages.filter(id=target.id)
            elif last_read_message_id:
                cursor = Message.objects.filter(
                    id=last_read_message_id,
                    match=locked_match,
                    sender=other_user,
                ).only('id', 'created_at').first()
                if cursor is None:
                    # Do not reveal whether the UUID belongs to another match
                    # or was sent by the requesting user.
                    raise InvalidReadCursor(_('Invalid message read cursor.'))
                # UUID primary keys are random, so they cannot break ties by
                # creation order. On clocks with coarse precision, two
                # sequential messages can share the exact same timestamp and
                # comparing their UUIDs would leave one unread at random.
                unread_messages = unread_messages.filter(
                    created_at__lte=cursor.created_at
                )

            message_ids = tuple(str(value) for value in unread_messages.values_list('id', flat=True))
            read_at = None
            if message_ids:
                read_at = timezone.now()
                Message.objects.filter(id__in=message_ids).update(
                    status=Message.READ,
                    read_at=read_at,
                )

            unread_count = Message.objects.filter(
                match=locked_match,
                sender=other_user,
                status__in=[Message.SENT, Message.DELIVERED],
                is_deleted_for_everyone=False,
            ).count()
            if user.pk == locked_match.user1_id:
                locked_match.user1_unread_count = unread_count
                unread_field = 'user1_unread_count'
            else:
                locked_match.user2_unread_count = unread_count
                unread_field = 'user2_unread_count'
            locked_match.save(update_fields=[unread_field])

            read_alert = None
            if message_ids:
                read_alert = _create_read_alert_notification(
                    recipient=other_user,
                    reader=user,
                    match=locked_match,
                    message_ids=message_ids,
                    read_at=read_at,
                )

            result = ReadReceiptResult(
                messages_marked=len(message_ids),
                message_ids=message_ids,
                read_at=read_at,
                unread_count_for_me=unread_count,
            )
            if message_ids:
                read_alert_id = str(read_alert.id) if read_alert is not None else None
                read_alert_payload = dict(read_alert.data) if read_alert is not None else None
                transaction.on_commit(
                    lambda read_alert_id=read_alert_id, read_alert_payload=read_alert_payload: MessageService._dispatch_read_receipt(
                        match_id=locked_match.id,
                        reader_id=user.id,
                        recipient_id=other_user.id,
                        message_ids=message_ids,
                        read_at=read_at,
                        read_alert_id=read_alert_id,
                        read_alert_payload=read_alert_payload,
                    )
                )
            return result

    @staticmethod
    def _dispatch_read_receipt(
        *,
        match_id,
        reader_id,
        recipient_id,
        message_ids: Tuple[str, ...],
        read_at,
        read_alert_id: str | None = None,
        read_alert_payload: dict | None = None,
    ) -> None:
        """Deliver best-effort external effects only after the transaction commits."""
        try:
            match = Match.objects.get(pk=match_id)
            reader = User.objects.get(pk=reader_id)
            # ``recipient_id`` here is the author of the acknowledged messages.
            _broadcast_read_receipt(
                match, reader, message_ids, read_at, sender_id=recipient_id
            )
        except Exception:
            logger.warning('Read receipt websocket dispatch failed for match_id=%s', match_id)

        if read_alert_id is None or read_alert_payload is None:
            return

        _broadcast_read_alert(
            recipient_id=recipient_id,
            notification_id=read_alert_id,
            payload=read_alert_payload,
        )
        try:
            # The row already exists.  A failed FCM delivery must never remove
            # this in-app alert or alter the universal read receipts.
            send_read_notification.delay(
                recipient_id=recipient_id,
                reader_id=reader_id,
                match_id=str(match_id),
                message_id=message_ids[-1],
                notification_id=read_alert_id,
            )
        except Exception:
            logger.warning('Read alert push dispatch failed for match_id=%s', match_id)

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
        if client_message_id:
            existing_message = Message.objects.filter(
                match=match,
                sender=sender,
                client_message_id=client_message_id,
            ).first()
            if existing_message:
                return existing_message

        original_filename = get_valid_filename(os.path.basename(media_file.name)) or 'upload'
        media_mime_type = (
            getattr(media_file, 'content_type', '') or ''
        ).lower().split(';')[0]
        media_size_bytes = getattr(media_file, 'size', None)
        requested_path = f"messages/{match.id}/{uuid4()}_{original_filename}"
        media_file_path = ''
        try:
            media_file_path = default_storage.save(requested_path, media_file)
        except Exception:
            if media_file_path:
                _delete_stored_media(media_file_path)
            logger.warning('Unable to store media upload for conversation_id=%s', match.id)
            raise ValueError(_('Unable to store media file.'))

        message, error = MessageService.send_message(
            sender=sender,
            match=match,
            content=text,
            message_type=media_type,
            media_file_path=media_file_path,
            # Serializers expose the authorised download endpoint, never a
            # provider/local URL derived from this storage handle.
            media_url='',
            media_mime_type=media_mime_type,
            media_size_bytes=media_size_bytes,
            media_file_name=original_filename,
            client_message_id=client_message_id,
        )
        if not message:
            _delete_stored_media(media_file_path)
            raise ValueError(error or "Unable to create media message")

        if message.media_file_path != media_file_path:
            _delete_stored_media(media_file_path)
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

            # LOG-07 : dispatcher la notification uniquement après commit.
            # Évite qu'une notification soit envoyée si la transaction est annulée.
            _call_id = call.id
            _callee_id = callee.id
            _caller_id = caller.id
            _call_type_val = call_type
            _match_id = str(match.id)

            def _dispatch_call_notification():
                try:
                    send_call_notification.delay(
                        callee_id=_callee_id,
                        caller_id=_caller_id,
                        call_type=_call_type_val,
                        match_id=_match_id,
                    )
                except Exception:
                    logger.warning('Call notification dispatch failed')

            transaction.on_commit(_dispatch_call_notification)

            return call, None
            
        except Exception:
            logger.error('Call initiation failed')
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
