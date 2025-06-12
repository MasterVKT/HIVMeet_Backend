"""
Utility functions for authentication.
"""
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils.translation import gettext as _
import logging

logger = logging.getLogger('hivmeet.auth')


def send_verification_email(user, verification_link):
    """
    Send email verification to user.
    """
    subject = _('Verify your HIVMeet account')
    
    # Prepare context for email template
    context = {
        'user': user,
        'verification_link': verification_link,
        'app_name': 'HIVMeet',
    }
    
    # Render email content
    html_message = render_to_string('authentication/emails/verify_email.html', context)
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Verification email sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send verification email to {user.email}: {str(e)}")
        return False


def send_password_reset_email(user, reset_link):
    """
    Send password reset email to user.
    """
    subject = _('Reset your HIVMeet password')
    
    # Prepare context for email template
    context = {
        'user': user,
        'reset_link': reset_link,
        'app_name': 'HIVMeet',
    }
    
    # Render email content
    html_message = render_to_string('authentication/emails/password_reset.html', context)
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Password reset email sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send password reset email to {user.email}: {str(e)}")
        return False


def send_welcome_email(user):
    """
    Send welcome email to new user.
    """
    subject = _('Welcome to HIVMeet')
    
    # Prepare context for email template
    context = {
        'user': user,
        'app_name': 'HIVMeet',
    }
    
    # Render email content
    html_message = render_to_string('authentication/emails/welcome.html', context)
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Welcome email sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send welcome email to {user.email}: {str(e)}")
        return False