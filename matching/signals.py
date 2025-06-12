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