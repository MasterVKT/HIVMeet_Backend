"""
Signals for matching app.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

from .models import Match, Like, Boost
from .tasks import send_match_notification

logger = logging.getLogger('hivmeet.matching')
channel_layer = get_channel_layer()


@receiver(post_save, sender=Match)
def handle_new_match(sender, instance, created, **kwargs):
    """
    Handle new match creation.
    """
    if created:
        # Send notifications to both users
        try:
            # Send push notifications
            send_match_notification.delay(
                instance.user1.id,
                instance.user2.id
            )
            send_match_notification.delay(
                instance.user2.id,
                instance.user1.id
            )
            
            # Send real-time notifications if users are online
            # This would use WebSockets/Channels
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f"user_{instance.user1.id}",
                    {
                        "type": "new_match",
                        "match_id": str(instance.id),
                        "matched_user_id": str(instance.user2.id)
                    }
                )
                async_to_sync(channel_layer.group_send)(
                    f"user_{instance.user2.id}",
                    {
                        "type": "new_match",
                        "match_id": str(instance.id),
                        "matched_user_id": str(instance.user1.id)
                    }
                )
                
        except Exception as e:
            logger.error(f"Error sending match notifications: {str(e)}")


@receiver(post_save, sender=Like)
def handle_new_like(sender, instance, created, **kwargs):
    """
    Handle new like creation.
    """
    if created and instance.like_type == Like.SUPER:
        # Send notification for super likes (premium feature)
        try:
            if instance.to_user.is_premium:
                # Send notification
                # This would be implemented with the notification system
                pass
        except Exception as e:
            logger.error(f"Error sending super like notification: {str(e)}")


@receiver(post_save, sender=Boost)
def track_boost_statistics(sender, instance, created, **kwargs):
    """
    Track boost statistics.
    """
    if not created and instance.is_active():
        # Log boost performance
        logger.info(
            f"Boost for user {instance.user.email}: "
            f"{instance.views_gained} views, {instance.likes_gained} likes"
        )


@receiver(post_save, sender=Like)
def handle_super_like_sent(sender, instance, created, **kwargs):
    """Handle super like consumption."""
    if created and instance.like_type == Like.SUPER:
        from subscriptions.utils import consume_premium_feature
        
        # Consume super like from user's quota
        result = consume_premium_feature(instance.from_user, 'super_like')
        if not result['success']:
            # This should not happen as it's checked before
            # Log error
            logger.error(f"Failed to consume super like: {result['error']}")
        else:
            logger.info(f"Super like consumed for user {instance.from_user.id}")


@receiver(post_save, sender=Boost)
def handle_boost_activation(sender, instance, created, **kwargs):
    """Handle boost activation."""
    if created and instance.is_active:
        from subscriptions.utils import consume_premium_feature
        
        # Consume boost from user's quota
        result = consume_premium_feature(instance.user, 'boost')
        if not result['success']:
            # This should not happen as it's checked before
            # Log error
            logger.error(f"Failed to consume boost: {result['error']}")
        else:
            logger.info(f"Boost consumed for user {instance.user.id}")


@receiver(post_save, sender=Like)
def handle_like_notification(sender, instance, created, **kwargs):
    """Send notification for likes and super likes."""
    if created:
        from .tasks import send_like_notification
        
        # Send notification to target user
        send_like_notification.delay(
            instance.from_user.id,
            instance.to_user.id,
            instance.like_type == Like.SUPER
        )
        
        # Send real-time notification if target user is online
        if channel_layer:
            notification_type = "super_like" if instance.like_type == Like.SUPER else "like"
            async_to_sync(channel_layer.group_send)(
                f"user_{instance.to_user.id}",
                {
                    "type": notification_type,
                    "from_user_id": str(instance.from_user.id),
                    "like_id": str(instance.id)
                }
            )