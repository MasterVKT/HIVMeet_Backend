"""
Signals for profiles app.
"""
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import logging

from .models import Profile, Verification

logger = logging.getLogger('hivmeet.profiles')
User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Create a profile when a new user is created.
    """
    if created:
        try:
            # A profile created outside the registration flow must explicitly
            # confirm its binary discovery gender once.  RecommendationService
            # also filters empty values, so this transient profile never leaks
            # into Discovery.
            profile = Profile.objects.create(
                user=instance,
                gender='',
                gender_confirmation_required=True,
            )
            logger.info("Profile created")
            
            # Also create an empty verification record
            Verification.objects.create(user=instance)
            logger.info("Legacy verification projection created")
            
        except Exception:
            logger.error("Profile or legacy verification projection creation failed")


@receiver(pre_delete, sender=User)
def cleanup_user_firebase(sender, instance, **kwargs):
    """
    Clean up Firebase data when a user is deleted.
    """
    try:
        # Delete Firebase user if exists
        if instance.firebase_uid:
            from hivmeet_backend.firebase_service import firebase_service
            firebase_service.delete_user(instance.firebase_uid)
            logger.info("Firebase identity deleted")
            
        # Note: Profile and Verification will be deleted automatically due to CASCADE
        
    except Exception:
        logger.error("Firebase identity cleanup failed")


@receiver(post_save, sender=Verification)
def handle_verification_status_change(sender, instance, created, **kwargs):
    """
    Handle verification status changes.
    """
    if not created:
        # Check if status changed to verified
        if instance.status == Verification.VERIFIED and not instance.expires_at:
            # Set expiration date (6 months from now)
            instance.expires_at = timezone.now() + timedelta(days=180)
            instance.save(update_fields=['expires_at'])
            
            # Update user verification status
            user = instance.user
            user.is_verified = True
            user.verification_status = 'verified'
            user.save(update_fields=['is_verified', 'verification_status'])
            
            logger.info("Legacy verification projection updated to verified")
            
        elif instance.status == Verification.REJECTED:
            # Update user verification status
            user = instance.user
            user.is_verified = False
            user.verification_status = 'rejected'
            user.save(update_fields=['is_verified', 'verification_status'])
            
            logger.info("Legacy verification projection updated to rejected")
