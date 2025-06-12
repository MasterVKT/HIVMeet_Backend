"""
Asynchronous tasks for matching app.
"""
from celery import shared_task
from django.contrib.auth import get_user_model
from firebase_admin import messaging
import logging

logger = logging.getLogger('hivmeet.matching')
User = get_user_model()


@shared_task
def send_match_notification(user_id, matched_user_id):
    """
    Send push notification for new match.
    """
    try:
        user = User.objects.get(id=user_id)
        matched_user = User.objects.get(id=matched_user_id)
        
        # Get FCM tokens
        tokens = [token['token'] for token in user.fcm_tokens if token.get('token')]
        
        if not tokens:
            logger.warning(f"No FCM tokens found for user {user.email}")
            return
        
        # Create notification
        notification = messaging.Notification(
            title="C'est un Match !",
            body=f"Vous et {matched_user.display_name} vous êtes plu !",
            image=matched_user.profile.photos.filter(is_main=True).first().thumbnail_url if hasattr(matched_user, 'profile') else None
        )
        
        # Create message
        message = messaging.MulticastMessage(
            notification=notification,
            data={
                'notification_type': 'NEW_MATCH',
                'match_id': str(matched_user_id),
                'matched_user_name': matched_user.display_name,
                'click_action': 'FLUTTER_NOTIFICATION_CLICK'
            },
            tokens=tokens
        )
        
        # Send notification
        response = messaging.send_multicast(message)
        
        logger.info(
            f"Match notification sent to {user.email}: "
            f"{response.success_count} successful, {response.failure_count} failed"
        )
        
    except User.DoesNotExist:
        logger.error(f"User not found: {user_id} or {matched_user_id}")
    except Exception as e:
        logger.error(f"Error sending match notification: {str(e)}")


@shared_task
def send_like_notification(user_id, liker_id, is_super_like=False):
    """
    Send push notification for new like (premium feature).
    """
    try:
        user = User.objects.get(id=user_id)
        liker = User.objects.get(id=liker_id)
        
        # Only send if user is premium and has enabled like notifications
        if not user.is_premium:
            return
        
        notification_settings = user.notification_settings or {}
        if not notification_settings.get('profile_like_notifications', True):
            return
        
        # Get FCM tokens
        tokens = [token['token'] for token in user.fcm_tokens if token.get('token')]
        
        if not tokens:
            return
        
        # Create notification
        if is_super_like:
            title = "Super Like reçu !"
            body = f"{liker.display_name} vous a envoyé un Super Like 💙"
        else:
            title = "Quelqu'un s'intéresse à vous !"
            body = f"{liker.display_name} a aimé votre profil"
        
        notification = messaging.Notification(
            title=title,
            body=body
        )
        
        # Create message
        message = messaging.MulticastMessage(
            notification=notification,
            data={
                'notification_type': 'PROFILE_LIKED',
                'liker_user_id': str(liker_id),
                'liker_user_name': liker.display_name,
                'is_super_like': str(is_super_like),
                'click_action': 'FLUTTER_NOTIFICATION_CLICK'
            },
            tokens=tokens
        )
        
        # Send notification
        response = messaging.send_multicast(message)
        
        logger.info(
            f"Like notification sent to {user.email}: "
            f"{response.success_count} successful"
        )
        
    except User.DoesNotExist:
        logger.error(f"User not found: {user_id} or {liker_id}")
    except Exception as e:
        logger.error(f"Error sending like notification: {str(e)}")