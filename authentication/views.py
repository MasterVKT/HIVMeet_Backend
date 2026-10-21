"""
Authentication views for HIVMeet API.
"""
from datetime import timedelta
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import authenticate, get_user_model
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from .serializers import (
    UserRegistrationSerializer,
    LoginSerializer,
    UserSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    TokenRefreshSerializer,
    EmailVerificationSerializer,
    FCMTokenSerializer
)
from .utils import (
    send_password_reset_email,
    send_welcome_email
)

import logging
import secrets
import hashlib
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model

logger = logging.getLogger('hivmeet.auth')
User = get_user_model()


def _firebase_service():
    from hivmeet_backend.firebase_service import firebase_service
    return firebase_service


def _serializer_error_codes(errors):
    """Return ``{field: [code, ...]}`` without exposing submitted values.

    The mobile client localises these stable codes; raw validator messages
    remain available in ``details`` for compatibility, but the client never
    displays backend strings directly.
    """
    codes = {}
    for field, details in errors.items():
        if isinstance(details, dict):
            codes[field] = _serializer_error_codes(details)
        else:
            codes[field] = [
                getattr(detail, 'code', 'invalid') for detail in details
            ]
    return codes


def _email_not_verified_response():
    """Use one stable, localisable error contract for every entry point."""
    return Response(
        {
            'code': 'email_not_verified',
            'message': _('Verify your email address before signing in.'),
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def _sync_email_verification_from_firebase(user):
    """Synchronise the local projection without creating or linking accounts.

    Password login and refresh tokens do not carry a fresh Firebase claim.  A
    Firebase user-record lookup keeps those legacy paths from becoming a way
    around Firebase verification.  Callers deliberately fail closed if this
    lookup is unavailable.
    """
    if not user.firebase_uid:
        return False

    firebase_user = _firebase_service().get_user(user.firebase_uid)
    firebase_email = str(getattr(firebase_user, 'email', '')).strip().lower()
    if not firebase_email or firebase_email != user.email.lower():
        return False

    firebase_verified = getattr(firebase_user, 'email_verified', False) is True
    if user.email_verified != firebase_verified:
        user.email_verified = firebase_verified
        user.save(update_fields=['email_verified', 'updated_at'])
    return firebase_verified


def generate_tokens(user, remember_me=False):
    """
    Generate access and refresh tokens for a user.
    """
    refresh = RefreshToken.for_user(user)
    
    # Extend refresh token lifetime if remember_me is True
    if remember_me:
        refresh.set_exp(lifetime=timedelta(days=30))
    
    return {
        'access_token': str(refresh.access_token),
        'refresh_token': str(refresh),
    }


def generate_verification_token():
    """
    Generate a secure verification token.
    """
    return secrets.token_urlsafe(32)


class FirebaseLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        """Exchange a Firebase identity only for an already registered user."""
        id_token = request.data.get('id_token') or request.data.get('firebase_token')
        if not id_token:
            return Response(
                {'code': 'id_token_required', 'message': _('Firebase ID token is required.')},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from firebase_admin import auth as firebase_auth
            decoded_token = firebase_auth.verify_id_token(id_token)
            uid = decoded_token.get('uid')
            email = decoded_token.get('email')
            email_verified = decoded_token.get('email_verified') is True
            if not uid or not email:
                return Response(
                    {'code': 'invalid_firebase_identity', 'message': _('Firebase email is required.')},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not email_verified:
                return _email_not_verified_response()

            with transaction.atomic():
                user = User.objects.select_for_update().filter(firebase_uid=uid).first()
                if user is None:
                    user = User.objects.select_for_update().filter(email__iexact=email).first()
                    if user is None:
                        # An ID token is authentication proof, not complete
                        # registration data. Never recreate an account here.
                        return Response(
                            {'code': 'registration_required', 'message': _('Complete registration before signing in.')},
                            status=status.HTTP_409_CONFLICT,
                        )
                    if user.firebase_uid:
                        return Response(
                            {'code': 'firebase_uid_mismatch', 'message': _('Firebase identity does not match this account.')},
                            status=status.HTTP_409_CONFLICT,
                        )
                    # Compatibility bridge for a pre-rollout local account;
                    # it links identity but never creates an account.
                    user.firebase_uid = uid
                    user.save(update_fields=['firebase_uid', 'updated_at'])
                elif user.email.lower() != str(email).lower():
                    return Response(
                        {'code': 'firebase_uid_mismatch', 'message': _('Firebase identity does not match this account.')},
                        status=status.HTTP_409_CONFLICT,
                    )

                if not user.is_active:
                    return Response(
                        {'code': 'account_disabled', 'message': _('Account is disabled.')},
                        status=status.HTTP_403_FORBIDDEN,
                    )

                if not user.email_verified:
                    user.email_verified = True
                    user.save(update_fields=['email_verified', 'updated_at'])
                user.update_last_active()

            refresh = RefreshToken.for_user(user)
            from subscriptions.utils import is_premium_user
            return Response({
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
                'token': str(refresh.access_token),
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'display_name': user.display_name,
                    'firebase_uid': uid,
                    'email_verified': user.email_verified,
                    'is_verified': user.is_verified,
                    'is_premium': is_premium_user(user),
                    'premium_until': user.premium_until.isoformat() if user.premium_until else None,
                    'last_active': user.last_active.isoformat(),
                },
            }, status=status.HTTP_200_OK)
        except Exception as exc:
            message = str(exc).lower()
            if 'expired' in message:
                return Response({'code': 'firebase_token_expired', 'message': _('Firebase token expired.')}, status=status.HTTP_400_BAD_REQUEST)
            if 'invalid' in message or 'verify' in message:
                return Response({'code': 'firebase_token_invalid', 'message': _('Invalid Firebase token.')}, status=status.HTTP_400_BAD_REQUEST)
            logger.error('Firebase token exchange failed')
            return Response({'code': 'firebase_exchange_failed', 'message': _('Unable to sign in right now.')}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    """Provision Firebase and the local account as one compensating operation."""
    serializer = UserRegistrationSerializer(data=request.data)
    if not serializer.is_valid():
        field_errors = _serializer_error_codes(serializer.errors)
        # Field names and validator codes only: never log submitted values.
        logger.warning(
            'Registration validation failed fields=%s codes=%s',
            sorted(field_errors),
            field_errors,
        )
        return Response({
            'error': True,
            'code': 'registration_invalid',
            'message': _('Validation error'),
            'details': serializer.errors,
            'field_errors': field_errors,
        }, status=status.HTTP_400_BAD_REQUEST)

    firebase_user = None
    try:
        # Provision external identity first.  A later local transaction failure
        # deletes it again, so Firebase and Django cannot drift silently.
        firebase_user = _firebase_service().create_user(
            email=serializer.validated_data['email'],
            password=serializer.validated_data['password'],
            display_name=serializer.validated_data['display_name'],
        )
        with transaction.atomic():
            user = serializer.save(firebase_uid=firebase_user.uid)
        return Response({
            'user_id': str(user.id),
            'verification_required': True,
            'message': _('Registration successful. Email verification is required.'),
        }, status=status.HTTP_201_CREATED)
    except Exception:
        if firebase_user is not None:
            try:
                _firebase_service().delete_user(firebase_user.uid)
            except Exception:
                logger.error('Firebase registration compensation failed')
        logger.error('Registration failed')
        return Response({
            'code': 'registration_failed',
            'message': _('Registration failed. Please try again.'),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def verify_email_view(request, verification_token):
    """
    Verify user's email address.
    
    GET /api/v1/auth/verify-email/{verification_token}
    """
    cache_key = f"email_verify_{verification_token}"
    user_id = cache.get(cache_key)
    
    if not user_id:
        return Response({
            'error': True,
            'message': _('Invalid or expired verification token.')
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        firebase_service = _firebase_service()
        user = User.objects.get(id=user_id)
        
        # This route is retained only for links issued by older releases.  The
        # Firebase record is updated first so the source of truth cannot lag
        # behind the local projection if the transaction fails.
        firebase_service.update_user(
            user.firebase_uid,
            email_verified=True
        )

        with transaction.atomic():
            if not user.email_verified:
                user.email_verified = True
                user.save(update_fields=['email_verified', 'updated_at'])
            cache.delete(cache_key)

        try:
            send_welcome_email(user)
        except Exception:
            # Verification already succeeded.  Welcome-mail delivery is not a
            # reason to reverse either verified state.
            logger.error('Welcome email delivery failed after verification')
        
        return Response({
            'message': _('Email verified successfully. You can now log in.')
        }, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response({
            'error': True,
            'message': _('User not found.')
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception:
        logger.error('Legacy email verification failed')
        return Response({
            'error': True,
            'message': _('Verification failed. Please try again.')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Authenticate user and return JWT tokens.
    
    POST /api/v1/auth/login
    """
    serializer = LoginSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data['email']
    password = serializer.validated_data['password']
    remember_me = serializer.validated_data.get('remember_me', False)
    
    try:
        # Authenticate user
        user = authenticate(request, email=email, password=password)
        
        if not user:
            return Response({
                'error': True,
                'message': _('Invalid credentials.')
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        if not user.is_active:
            return Response({
                'error': True,
                'message': _('Account is disabled.')
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            if not _sync_email_verification_from_firebase(user):
                return _email_not_verified_response()
        except Exception:
            logger.error('Firebase verification lookup failed during password login')
            return Response(
                {'code': 'firebase_verification_unavailable', 'message': _('Unable to sign in right now.')},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        
        # Update last login
        user.last_login = timezone.now()
        user.update_last_active()
        
        # Generate tokens
        tokens = generate_tokens(user, remember_me)
        
        # Serialize user data
        user_data = UserSerializer(user).data
        
        logger.info('Password login completed')
        
        return Response({
            'access_token': tokens['access_token'],
            'refresh_token': tokens['refresh_token'],
            'user': user_data
        }, status=status.HTTP_200_OK)
        
    except Exception:
        logger.error('Password login failed')
        return Response({
            'error': True,
            'message': _('Login failed. Please try again.')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password_view(request):
    """
    Request password reset.
    
    POST /api/v1/auth/forgot-password
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data['email']
    
    # Always return success to prevent email enumeration
    try:
        user = User.objects.get(email=email)
        
        # Generate reset token
        reset_token = generate_verification_token()
        cache_key = f"password_reset_{reset_token}"
        cache.set(cache_key, user.id, timeout=3600)  # 1 hour
        
        # Send password reset email
        reset_link = f"{settings.FRONTEND_URL}/reset-password/{reset_token}"
        send_password_reset_email(user, reset_link)
        
        logger.info('Password reset requested')
        
    except User.DoesNotExist:
        # Don't reveal that the email doesn't exist
        logger.warning('Password reset requested for unknown account')
    
    return Response({
        'message': _('If an account with this email exists, a password reset link has been sent.')
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password_view(request):
    """
    Reset password with token.
    
    POST /api/v1/auth/reset-password
    """
    serializer = PasswordResetConfirmSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    token = serializer.validated_data['token']
    new_password = serializer.validated_data['new_password']
    
    cache_key = f"password_reset_{token}"
    user_id = cache.get(cache_key)
    
    if not user_id:
        return Response({
            'error': True,
            'message': _('Invalid or expired reset token.')
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        firebase_service = _firebase_service()
        user = User.objects.get(id=user_id)
        
        # Update password
        user.set_password(new_password)
        user.save()
        
        # Update Firebase user
        firebase_service.update_user(
            user.firebase_uid,
            password=new_password
        )
        
        # Delete cache key
        cache.delete(cache_key)
        
        logger.info('Password reset completed')
        
        return Response({
            'message': _('Password reset successfully. You can now log in with your new password.')
        }, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response({
            'error': True,
            'message': _('User not found.')
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception:
        logger.error('Password reset failed')
        return Response({
            'error': True,
            'message': _('Password reset failed. Please try again.')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token_view(request):
    """
    Refresh access token.
    
    POST /api/v1/auth/refresh-token
    """
    serializer = TokenRefreshSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    refresh_token = serializer.validated_data['refresh_token']
    
    try:
        # Verify and refresh token
        refresh = RefreshToken(refresh_token)
        
        try:
            user = User.objects.get(id=refresh['user_id'])
        except User.DoesNotExist:
            return Response({
                'code': 'invalid_refresh_token',
                'message': _('Invalid or expired refresh token.'),
            }, status=status.HTTP_401_UNAUTHORIZED)

        try:
            if not _sync_email_verification_from_firebase(user):
                return _email_not_verified_response()
        except Exception:
            logger.error('Firebase verification lookup failed during token refresh')
            return Response(
                {'code': 'firebase_verification_unavailable', 'message': _('Unable to refresh the session right now.')},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Get new tokens only after Firebase verification has been confirmed.
        new_access_token = str(refresh.access_token)
        new_refresh_token = str(refresh)  # Rotates the refresh token
        
        return Response({
            # Clés standardisées
            'access_token': new_access_token,
            'refresh_token': new_refresh_token,
            # Alias pour compatibilité
            'token': new_access_token,
            'access': new_access_token,
            'refresh': new_refresh_token
        }, status=status.HTTP_200_OK)
        
    except TokenError as e:
        return Response({
            'error': True,
            'message': _('Invalid or expired refresh token.')
        }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    Logout user (invalidate refresh token).
    
    POST /api/v1/auth/logout
    """
    try:
        refresh_token = request.data.get('refresh_token')

        if refresh_token:
            # Blacklist the refresh token
            token = RefreshToken(refresh_token)
            token.blacklist()

        fcm_token = request.data.get('fcm_token')
        if fcm_token:
            request.user.remove_fcm_token(fcm_token)

        logger.info('User logged out')
        
        return Response(status=status.HTTP_204_NO_CONTENT)
        
    except Exception:
        # Even if token blacklisting fails, consider logout successful
        logger.warning('Logout cleanup failed')
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegisterFCMTokenView(generics.GenericAPIView):
    """
    FCM token management for push notifications.

    POST /api/v1/auth/fcm-token   — enregistre un nouveau token
    DELETE /api/v1/auth/fcm-token — supprime un token existant
    """
    serializer_class = FCMTokenSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        fcm_token = serializer.validated_data['fcm_token']
        device_id = serializer.validated_data.get('device_id')
        platform = serializer.validated_data.get('platform')

        user.add_fcm_token(fcm_token, device_id, platform)

        logger.info('FCM token registered')

        return Response({
            'message': _('FCM token registered successfully.')
        }, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        """
        Supprime un token FCM de l'utilisateur connecté.
        Body: {"fcm_token": "<token>"}
        """
        fcm_token = request.data.get('fcm_token')
        if not fcm_token:
            return Response(
                {'error': _('fcm_token is required.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.remove_fcm_token(fcm_token)

        logger.info('FCM token removed')

        return Response(status=status.HTTP_204_NO_CONTENT)


# ──────────────────────────────────────────────────────────────────────
# Report (Signalement) endpoints
# ──────────────────────────────────────────────────────────────────────

import logging as _logging
from .models import Report

_report_logger = _logging.getLogger('hivmeet.reports')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def report_user_view(request):
    """
    POST /api/v1/auth/report-user

    Crée un signalement d'un utilisateur par l'utilisateur connecté.
    Body: {"reported_user_id": str, "reason": str, "description"?: str}
    """
    reported_user_id = request.data.get('reported_user_id')
    reason = request.data.get('reason')
    description = request.data.get('description', '').strip()

    if not reported_user_id:
        return Response(
            {'error': _('reported_user_id is required.')},
            status=status.HTTP_400_BAD_REQUEST,
        )

    valid_reasons = [r[0] for r in Report.REASON_CHOICES]
    if not reason or reason not in valid_reasons:
        return Response(
            {'error': _('Invalid reason.')},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if reported_user_id == str(request.user.id):
        return Response(
            {'error': _('You cannot report yourself.')},
            status=status.HTTP_400_BAD_REQUEST,
        )

    User = get_user_model()
    try:
        reported_user = User.objects.get(id=reported_user_id)
    except User.DoesNotExist:
        return Response(
            {'error': _('Reported user not found.')},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Anti-abuse: un utilisateur ne peut pas signaler le même utilisateur
    # plus d'une fois avec le même motif en 24h
    recent_duplicate = Report.objects.filter(
        reporter=request.user,
        reported_user=reported_user,
        reason=reason,
        created_at__gte=timezone.now() - timezone.timedelta(hours=24),
    ).exists()

    if recent_duplicate:
        return Response(
            {'error': _('You have already reported this user recently.')},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    report = Report.objects.create(
        reporter=request.user,
        reported_user=reported_user,
        reason=reason,
        description=description,
    )

    _report_logger.info(
        f"Report created: {report.id} — {request.user.email} reported {reported_user.email} ({reason})"
    )

    return Response(
        {
            'id': str(report.id),
            'status': report.status,
            'message': _('Your report has been submitted and will be reviewed.'),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_reports_view(request):
    """
    GET /api/v1/auth/reports

    Liste les signalements faits par l'utilisateur connecté.
    Permet à l'utilisateur de suivre le statut de ses signalements.
    """
    reports = Report.objects.filter(reporter=request.user).order_by('-created_at')

    data = [
        {
            'id': str(r.id),
            'reported_user_id': str(r.reported_user_id),
            'reason': r.reason,
            'description': r.description,
            'status': r.status,
            'resolution_notes': r.resolution_notes,
            'created_at': r.created_at.isoformat(),
            'resolved_at': r.resolved_at.isoformat() if r.resolved_at else None,
        }
        for r in reports
    ]

    return Response({'results': data}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def resolve_report_view(request, report_id):
    """
    POST /api/v1/auth/reports/<uuid:report_id>/resolve

    Admin only: résout un signalement et notifie le reporter.
    Body: {"status": "resolved"|"dismissed", "resolution_notes": str}
    """
    user = request.user
    if user.role not in ('admin', 'moderator'):
        return Response(
            {'error': _('Only admin or moderator can resolve reports.')},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        report = Report.objects.select_related('reporter').get(id=report_id)
    except Report.DoesNotExist:
        return Response(
            {'error': _('Report not found.')},
            status=status.HTTP_404_NOT_FOUND,
        )

    new_status = request.data.get('status')
    if new_status not in (Report.STATUS_RESOLVED, Report.STATUS_DISMISSED):
        return Response(
            {'error': _('Invalid status. Use "resolved" or "dismissed".')},
            status=status.HTTP_400_BAD_REQUEST,
        )

    resolution_notes = request.data.get('resolution_notes', '').strip()

    report.status = new_status
    report.resolution_notes = resolution_notes
    report.resolved_by = user
    report.resolved_at = timezone.now()
    report.save()

    _report_logger.info(
        f"Report {report.id} resolved by {user.email}: {new_status}"
    )

    # Créer la notification pour le reporter
    try:
        from notifications.models import Notification
        from notifications.payloads import report_resolved_payload
        from notifications.fcm import send_fcm_to_user
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        import firebase_admin.messaging as fcm_messaging

        reporter = report.reporter
        status_label = 'Résolu' if new_status == Report.STATUS_RESOLVED else 'Rejeté'
        summary = resolution_notes if resolution_notes else 'Votre signalement a été traité.'

        # 1. Notification DB record
        Notification.objects.create(
            user=reporter,
            type='report_resolved',
            title='Votre signalement a été traité',
            body=f'Décision : {status_label}. {summary}',
            data={
                'type': 'report_resolved',
                'notification_id': f'report_{report.id}',
                'report_id': str(report.id),
                'status': new_status,
                'resolution_summary': summary,
            },
        )

        # 2. FCM push
        try:
            payload = report_resolved_payload(
                report_id=str(report.id),
                status=new_status,
                resolution_summary=summary,
            )
            notif = fcm_messaging.Notification(
                title=payload['title'],
                body=payload['body'],
            )
            send_fcm_to_user(reporter, notification=notif, data=payload)
        except Exception as e:
            _report_logger.warning(f"FCM push failed for report resolution: {e}")

        # 3. WebSocket
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f"user_{reporter.id}",
                    {
                        "type": "report_resolved",
                        "notification_id": f"report_{report.id}",
                        "report_id": str(report.id),
                        "status": new_status,
                        "resolution_summary": summary,
                    }
                )
        except Exception as e:
            _report_logger.warning(f"WebSocket dispatch failed for report resolution: {e}")

    except Exception as e:
        _report_logger.error(f"Failed to create report resolution notification: {e}")

    return Response(
        {
            'id': str(report.id),
            'status': report.status,
            'resolution_notes': report.resolution_notes,
            'resolved_at': report.resolved_at.isoformat() if report.resolved_at else None,
        },
        status=status.HTTP_200_OK,
    )
