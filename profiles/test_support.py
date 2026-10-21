"""Fixtures shared by tests that exercise the verified social surface."""

from datetime import timedelta

from django.utils import timezone

from .models import KycAttempt


def grant_social_access(*users):
    """Make synthetic users email-verified with a current approved KYC state."""
    for user in users:
        if not user.email_verified:
            user.email_verified = True
            user.save(update_fields=['email_verified'])
        KycAttempt.objects.create(
            user=user,
            status=KycAttempt.VERIFIED,
            is_open=False,
            expires_at=timezone.now() + timedelta(days=1),
        )
