"""
Asynchronous tasks for matching app.
"""
from celery import shared_task
from django.contrib.auth import get_user_model
from firebase_admin import messaging
import logging

from notifications.fcm import send_fcm_to_user
from notifications.payloads import match_payload, like_payload

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

        # Sécuriser la récupération de la photo principale (peut être absente)
        main_photo = None
        if hasattr(matched_user, 'profile'):
            main_photo = matched_user.profile.photos.filter(is_main=True).first()
        # Push payloads have no authenticated recipient request context; never
        # include a profile-media URL or private-object capability here.
        image_url = None

        data = match_payload(
            match_id=str(matched_user_id),  # match_id = l'id du match (== conversation)
            other_user_display_name=matched_user.display_name,
            other_user_id=str(matched_user.id),
        )

        notif = messaging.Notification(
            title=data['title'],
            body=data['body'],
            image=image_url,
        )

        send_fcm_to_user(user, notification=notif, data=data)

    except User.DoesNotExist:
        logger.error(f"User not found: {user_id} or {matched_user_id}")
    except Exception as e:
        logger.error(f"Error sending match notification: {str(e)}")


@shared_task
def send_like_notification(
    user_id,
    liker_id,
    is_super_like=False,
    notification_id=None,
):
    """
    Send push notification for new like / super-like.

    Tous les utilisateurs reçoivent une notification :
    - Premium : révèle l'identité du likeur.
    - Non-premium : notification anonymisée (titre générique, from_user_id vide).

    La notification est supprimée seulement si l'utilisateur a désactivé
    les notifications de like dans ses préférences.
    """
    try:
        user = User.objects.get(id=user_id)
        liker = User.objects.get(id=liker_id)

        # Respect des préférences utilisateur
        notification_settings = user.notification_settings or {}
        if not notification_settings.get('profile_like_notifications', True):
            return

        if not notification_id:
            logger.warning("Like notification skipped: missing canonical notification ID")
            return

        data = like_payload(
            notification_id=str(notification_id),
            is_super=is_super_like,
            liker_display_name=liker.display_name,
            liker_id=str(liker.id),
            recipient_is_premium=user.is_premium,
        )

        notif = messaging.Notification(
            title=data['title'],
            body=data['body'],
        )

        send_fcm_to_user(user, notification=notif, data=data)

    except User.DoesNotExist:
        logger.error("Like notification recipient or sender not found")
    except Exception:
        logger.error("Like notification delivery failed")
