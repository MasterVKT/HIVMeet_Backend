"""Shared fixtures for matching tests protected by the KYC access gate."""

from datetime import timedelta

from django.utils import timezone

from profiles.models import KycAttempt


def grant_social_access(*users):
    """Give synthetic users both prerequisites for social test scenarios."""
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
