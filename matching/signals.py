"""
Signals for matching app.
"""
from django.db.models.signals import post_save
from django.db import transaction
from django.conf import settings
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging
from contextlib import contextmanager
from threading import Thread

from .models import Match, Like, Boost
from .tasks import send_match_notification

logger = logging.getLogger('hivmeet.matching')


def get_channel_layer_safe():
    """
    Get channel layer with error handling for when Redis is not available.
    Returns None if Redis is not running.
    """
    try:
        return get_channel_layer()
    except Exception as e:
        logger.warning(f"Redis non disponible: {str(e)}")
        return None


@contextmanager
def channel_layer_context():
    """
    Context manager for safely using channel layer.
    Yields None if Redis is not available.
    """
    layer = None
    try:
        layer = get_channel_layer()
    except Exception as e:
        logger.warning(f"Redis non disponible (Channel Layer): {str(e)}")
    yield layer


def dispatch_group_event(group_name, event):
    """Dispatch a websocket event without blocking the HTTP transaction.

    Redis can be unavailable during local device testing. Channel delivery is
    best-effort and must never prevent the matching endpoint from responding.
    """
    def _send():
        with channel_layer_context() as channel_layer:
            if channel_layer:
                try:
                    async_to_sync(channel_layer.group_send)(group_name, event)
                except Exception as exc:
                    logger.warning("Realtime notification unavailable: %s", exc)

    transaction.on_commit(
        lambda: Thread(
            target=_send,
            daemon=True,
            name="matching-realtime",
        ).start()
    )


def enqueue_after_commit(task, *args):
    """Queue side effects only after commit; emulate a worker in eager mode."""
    def _enqueue():
        try:
            task.delay(*args)
        except Exception as exc:
            logger.warning("Notification task unavailable: %s", exc)

    def _dispatch():
        if getattr(settings, 'TESTING', False):
            # Les tests doivent pouvoir observer l'appel Celery de manière
            # déterministe, tout en conservant la garantie after-commit.
            _enqueue()
        elif getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            Thread(
                target=_enqueue,
                daemon=True,
                name="matching-notification",
            ).start()
        else:
            _enqueue()

    transaction.on_commit(_dispatch)


@receiver(post_save, sender=Match)
def handle_new_match(sender, instance, created, **kwargs):
    """
    Handle new match creation.
    """
    if created:
        try:
            # Send push notifications to both users
            enqueue_after_commit(
                send_match_notification,
                instance.user1.id,
                instance.user2.id
            )
            enqueue_after_commit(
                send_match_notification,
                instance.user2.id,
                instance.user1.id
            )

            # Persister les notifications en base
            try:
                from notifications.models import Notification

                for recipient, other in [
                    (instance.user1, instance.user2),
                    (instance.user2, instance.user1),
                ]:
                    Notification.objects.create(
                        user=recipient,
                        type='new_match',
                        title="C'est un match !",
                        body=f'Vous avez matché avec {other.display_name}',
                        data={
                            'type': 'new_match',
                            'notification_id': f'match_{instance.id}',
                            'match_id': str(instance.id),
                            'from_user_id': str(other.id),
                            'conversation_id': str(instance.id),
                        },
                    )
            except Exception as e:
                logger.warning(f"Impossible de persister la Notification new_match: {e}")

            # WebSocket delivery is best-effort and must not block this signal.
            dispatch_group_event(
                f"user_{instance.user1.id}",
                {
                    "type": "new_match",
                    "match_id": str(instance.id),
                    "matched_user_id": str(instance.user2.id),
                },
            )
            dispatch_group_event(
                f"user_{instance.user2.id}",
                {
                    "type": "new_match",
                    "match_id": str(instance.id),
                    "matched_user_id": str(instance.user1.id),
                },
            )

        except Exception as e:
            logger.error(f"Error sending match notifications: {str(e)}")


@receiver(post_save, sender=Like)
def handle_new_like(sender, instance, created, **kwargs):
    """
    Handle new like creation (stub — handled by handle_like_notification).
    """
    if created and instance.like_type == Like.SUPER:
        try:
            if instance.to_user.is_premium:
                # Notification push déjà gérée par handle_like_notification
                pass
        except Exception as e:
            logger.error(f"Error sending super like notification: {str(e)}")


@receiver(post_save, sender=Boost)
def track_boost_statistics(sender, instance, created, **kwargs):
    """
    Track boost statistics.
    """
    if not created and instance.is_active():
        logger.info(
            "Boost statistics: %s views, %s likes",
            instance.views_gained,
            instance.likes_gained,
        )


@receiver(post_save, sender=Like)
def handle_super_like_sent(sender, instance, created, **kwargs):
    """Mirror Premium counters; free allowances are history-based."""
    if not created or instance.like_type != Like.SUPER:
        return

    from subscriptions.models import Subscription
    from subscriptions.utils import consume_premium_feature

    try:
        subscription = instance.from_user.subscription
    except Subscription.DoesNotExist:
        return
    if not subscription.is_premium:
        return

    result = consume_premium_feature(instance.from_user, 'super_like')
    if not result['success']:
        logger.warning("Could not synchronize the Premium super-like counter")
    else:
        logger.info("Premium super-like counter synchronized")


@receiver(post_save, sender=Boost)
def handle_boost_activation(sender, instance, created, **kwargs):
    """Handle boost activation."""
    if created and instance.is_active:
        from subscriptions.utils import consume_premium_feature

        result = consume_premium_feature(instance.user, 'boost')
        if not result['success']:
            logger.error(f"Failed to consume boost: {result['error']}")
        else:
            logger.info("Boost consumed")


@receiver(post_save, sender=Like)
def handle_like_notification(sender, instance, created, **kwargs):
    """Send notification for likes and super likes."""
    if created:
        from .tasks import send_like_notification

        is_super = instance.like_type == Like.SUPER

        # Persister d'abord : l'UUID serveur est l'identifiant canonique qui
        # doit voyager à l'identique via FCM, WebSocket et l'API REST.
        try:
            from notifications.models import Notification

            notif_type = 'super_like' if is_super else 'like'
            recipient = instance.to_user
            liker = instance.from_user

            if recipient.is_premium:
                body = f'{liker.display_name} vous a {"Super Liké" if is_super else "liké"}'
            else:
                body = (
                    'Quelqu\'un vous a Super Liké ! Passez Premium pour voir qui'
                    if is_super else
                    'Passez Premium pour voir qui vous a liké'
                )

            notification = Notification(
                user=recipient,
                type=notif_type,
                title='Vous avez reçu un Super Like !' if is_super else 'Quelqu\'un vous a liké !',
                body=body,
            )
            notification_id = str(notification.id)
            notification.data = {
                'type': notif_type,
                'notification_id': notification_id,
                'like_id': str(instance.id),
                'from_user_id': str(liker.id) if recipient.is_premium else '',
                'is_super': str(is_super).lower(),
            }
            notification.save()
        except Exception:
            logger.warning("Unable to persist like notification")
            return

        # Ordre correct : (destinataire, likeur), avec l'UUID canonique.
        enqueue_after_commit(
            send_like_notification,
            instance.to_user.id,
            instance.from_user.id,
            is_super,
            notification_id,
        )

        notification_type = "super_like" if is_super else "like"
        from_user_id_ws = (
            str(instance.from_user.id) if instance.to_user.is_premium else ''
        )
        dispatch_group_event(
            f"user_{instance.to_user.id}",
            {
                "type": notification_type,
                "notification_id": notification_id,
                "from_user_id": from_user_id_ws,
                "like_id": str(instance.id),
                "is_super": str(is_super).lower(),
            },
        )
