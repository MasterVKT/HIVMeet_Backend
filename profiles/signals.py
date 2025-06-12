"""
Signals for profiles app.
"""
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import logging
import random
import string

from .models import Profile, Verification
from hivmeet_backend.firebase_service import firebase_service

logger = logging.getLogger('hivmeet.profiles')
User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Create a profile when a new user is created.
    """
    if created:
        try:
            profile = Profile.objects.create(user=instance)
            logger.info(f"Profile created for user: {instance.email}")
            
            # Also create an empty verification record
            Verification.objects.create(user=instance)
            logger.info(f"Verification record created for user: {instance.email}")
            
        except Exception as e:
            logger.error(f"Error creating profile for user {instance.email}: {str(e)}")


@receiver(pre_delete, sender=User)
def cleanup_user_firebase(sender, instance, **kwargs):
    """
    Clean up Firebase data when a user is deleted.
    """
    try:
        # Delete Firebase user if exists
        if instance.firebase_uid:
            firebase_service.delete_user(instance.firebase_uid)
            logger.info(f"Deleted Firebase user: {instance.firebase_uid}")
            
        # Note: Profile and Verification will be deleted automatically due to CASCADE
        
    except Exception as e:
        logger.error(f"Error cleaning up Firebase for user {instance.email}: {str(e)}")


def generate_verification_code():
    """Generate a random 6-character verification code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


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
            
            logger.info(f"User {user.email} verified successfully")
            
        elif instance.status == Verification.REJECTED:
            # Update user verification status
            user = instance.user
            user.is_verified = False
            user.verification_status = 'rejected'
            user.save(update_fields=['is_verified', 'verification_status'])
            
            logger.info(f"User {user.email} verification rejected")