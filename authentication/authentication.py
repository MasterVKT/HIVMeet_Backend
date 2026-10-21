"""Authentication classes for credentials issued by HIVMeet.

An access token is only valid while the local projection of the Firebase
identity says that its email address has been verified.  The projection is
updated when Firebase credentials are exchanged and by the reconciliation
command; this guard makes an already-issued JWT unusable as soon as that
status is withdrawn locally.
"""
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication


class EmailNotVerified(PermissionDenied):
    default_detail = _('Verify your email address before accessing this resource.')
    default_code = 'email_not_verified'


class VerifiedEmailJWTAuthentication(JWTAuthentication):
    """Accept Django JWTs only for accounts with a verified Firebase email."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if not user.email_verified:
            raise EmailNotVerified()
        return user
