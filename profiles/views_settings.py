"""
Views for user settings.
"""
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from django.db import transaction
import logging

from authentication.serializers import UserSerializer
from profiles.models import AccountDeletionRequest, DataExportRequest
from profiles.tasks import generate_data_export, process_account_deletion

logger = logging.getLogger('hivmeet.profiles')
User = get_user_model()


class NotificationPreferencesView(generics.RetrieveUpdateAPIView):
    """
    Get or update notification preferences.
    
    GET /api/v1/user-settings/notification-preferences
    PUT /api/v1/user-settings/notification-preferences
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get notification preferences."""
        user = request.user
        preferences = user.notification_settings or {}
        
        # Default preferences
        from subscriptions.utils import is_premium_user
        is_premium = is_premium_user(user)
        default_preferences = {
            'new_match_notifications': True,
            'new_message_notifications': True,
            'profile_like_notifications': is_premium,
            # An absent preference is enabled for Premium.  Only an explicit
            # false value is an opt-out; Free is always presented as false.
            'message_read_notifications': is_premium,
            'app_update_notifications': True,
            'promotional_notifications': False,
            'do_not_disturb_settings': {
                'enabled': False,
                'start_time_utc': '22:00',
                'end_time_utc': '07:00'
            }
        }
        
        # Merge with user preferences
        preferences = {**default_preferences, **preferences}
        if not is_premium:
            preferences['message_read_notifications'] = False
        return Response(preferences)
    
    def put(self, request):
        """Update notification preferences with a bounded, typed payload."""
        from subscriptions.utils import is_premium_user

        user = request.user
        data = request.data if isinstance(request.data, dict) else {}
        current = user.notification_settings or {}
        bool_keys = (
            'new_match_notifications',
            'new_message_notifications',
            'profile_like_notifications',
            'app_update_notifications',
            'promotional_notifications',
            'message_read_notifications',
        )
        is_premium = is_premium_user(user)
        for key in bool_keys:
            if key in data and isinstance(data[key], bool):
                # A Free account cannot create or overwrite the Premium-only
                # choice.  This preserves an explicit choice made before an
                # expiry so it is restored on a future Premium renewal.
                if key == 'message_read_notifications' and not is_premium:
                    continue
                current[key] = data[key]
        if isinstance(data.get('do_not_disturb_settings'), dict):
            current['do_not_disturb_settings'] = data['do_not_disturb_settings']

        user.notification_settings = current
        user.save(update_fields=['notification_settings'])
        return Response(self.get(request).data)


class PrivacyPreferencesView(generics.RetrieveUpdateAPIView):
    """
    Get or update privacy preferences.
    
    GET /api/v1/user-settings/privacy-preferences
    PUT /api/v1/user-settings/privacy-preferences
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get privacy preferences."""
        profile = request.user.profile
        
        preferences = {
            'profile_visibility': 'visible_to_all' if profile.allow_profile_in_discovery else 'hidden',
            'show_online_status': profile.show_online_status,
            'show_distance': not profile.hide_exact_location,
            'profile_discoverable': profile.allow_profile_in_discovery
        }
        
        return Response(preferences)
    
    def put(self, request):
        """Update privacy preferences."""
        profile = request.user.profile
        data = request.data
        
        # Update profile fields
        if 'profile_visibility' in data:
            profile.allow_profile_in_discovery = data['profile_visibility'] == 'visible_to_all'
        
        if 'show_online_status' in data:
            profile.show_online_status = data['show_online_status']
        
        if 'show_distance' in data:
            profile.hide_exact_location = not data['show_distance']
        
        if 'profile_discoverable' in data:
            profile.allow_profile_in_discovery = data['profile_discoverable']
        
        profile.save()
        
        logger.info("Privacy preferences updated")
        
        return Response({
            'message': _('Privacy preferences updated successfully.')
        })


class BlockedUsersListView(generics.ListAPIView):
    """
    Get list of blocked users.
    
    GET /api/v1/user-settings/blocks
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer
    
    def get_queryset(self):
        """Get blocked users."""
        return self.request.user.blocked_users.all()
    
    def list(self, request, *args, **kwargs):
        """Custom list response."""
        queryset = self.get_queryset()
        
        blocked_users = []
        from profiles.photo_storage import profile_photo_delivery_url
        for user in queryset:
            photo_url = None
            if hasattr(user, 'profile') and user.profile.photos.exists():
                photo = user.profile.photos.filter(is_main=True).first()
                if photo:
                    photo_url = profile_photo_delivery_url(photo, request, thumbnail=True)
            blocked_users.append({
                'user_id': str(user.id),
                'display_name': user.display_name,
                'profile_photo_url': photo_url
            })
        
        return Response({
            'count': len(blocked_users),
            'results': blocked_users
        })


@api_view(['POST', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def block_unblock_user_view(request, user_id):
    """
    Block or unblock a user.
    
    POST /api/v1/user-settings/blocks/{user_id} - Block user
    DELETE /api/v1/user-settings/blocks/{user_id} - Unblock user
    """
    try:
        target_user = User.objects.get(id=user_id)
        
        if target_user == request.user:
            return Response({
                'error': True,
                'message': _('You cannot block yourself.')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if request.method == 'POST':
            # Block user
            if target_user in request.user.blocked_users.all():
                return Response({
                    'error': True,
                    'message': _('User already blocked.')
                }, status=status.HTTP_409_CONFLICT)
            
            # Check block limit
            if request.user.blocked_users.count() >= 100:
                return Response({
                    'error': True,
                    'message': _('Block limit reached (100 users).')
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            request.user.blocked_users.add(target_user)
            logger.info("User block state changed: blocked")
            
            return Response({
                'status': 'user_blocked',
                'blocked_user_id': str(target_user.id)
            }, status=status.HTTP_201_CREATED)
        
        else:  # DELETE
            # Unblock user
            if target_user not in request.user.blocked_users.all():
                return Response({
                    'error': True,
                    'message': _('User not in blocked list.')
                }, status=status.HTTP_404_NOT_FOUND)
            
            request.user.blocked_users.remove(target_user)
            logger.info("User block state changed: unblocked")
            
            return Response(status=status.HTTP_204_NO_CONTENT)
            
    except User.DoesNotExist:
        return Response({
            'error': True,
            'message': _('User not found.')
        }, status=status.HTTP_404_NOT_FOUND)


def _has_pending_data_export(user):
    return DataExportRequest.objects.filter(
        user=user,
        status__in=(DataExportRequest.STATUS_PENDING, DataExportRequest.STATUS_PROCESSING),
    ).exists()


def _has_pending_deletion(user):
    return AccountDeletionRequest.objects.filter(
        user=user,
        status__in=(
            AccountDeletionRequest.STATUS_PENDING,
            AccountDeletionRequest.STATUS_CONFIRMED,
            AccountDeletionRequest.STATUS_PROCESSING,
        ),
    ).exists()


def _serialize_data_request(request_obj, action_type):
    """Build a consistent response for frontend pending-state display."""
    return {
        'request_id': str(request_obj.id),
        'action_type': action_type,
        'status': request_obj.status,
        'requested_at': request_obj.requested_at.isoformat(),
        'message': request_obj.__str__(),
    }


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def delete_account_view(request):
    """
    Request account deletion with email confirmation and a reversible grace period.

    POST /api/v1/user-settings/delete-account

    Required body field:
        - password: current password (for re-authentication)
    """
    user = request.user

    if _has_pending_deletion(user):
        existing = AccountDeletionRequest.objects.filter(
            user=user,
            status__in=(
                AccountDeletionRequest.STATUS_PENDING,
                AccountDeletionRequest.STATUS_CONFIRMED,
                AccountDeletionRequest.STATUS_PROCESSING,
            ),
        ).order_by('-requested_at').first()
        return Response(
            _serialize_data_request(existing, 'account_deletion'),
            status=status.HTTP_200_OK,
        )

    password = request.data.get('password')
    if not password:
        return Response(
            {'error': 'password_required', 'message': _('Password is required to request account deletion.')},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not check_password(password, user.password):
        return Response(
            {'error': 'invalid_password', 'message': _('The password you entered is incorrect.')},
            status=status.HTTP_403_FORBIDDEN,
        )

    if _has_pending_data_export(user):
        return Response(
            {
                'error': 'export_in_progress',
                'message': _('A data export is in progress. Please wait until it completes before deleting your account.'),
            },
            status=status.HTTP_409_CONFLICT,
        )

    with transaction.atomic():
        request_obj = AccountDeletionRequest.objects.create(
            user=user,
            status=AccountDeletionRequest.STATUS_PENDING,
            reason=request.data.get('reason', ''),
            grace_period_hours=settings.HIVMEET_DELETION_GRACE_HOURS,
            confirmation_token=get_random_string(length=40),
            cancellation_token=get_random_string(length=40),
        )

    # TODO: send confirmation email with confirmation_token and cancellation_token
    # once the notification/email service is wired.

    logger.warning("Account deletion requested")

    return Response(
        _serialize_data_request(request_obj, 'account_deletion'),
        status=status.HTTP_202_ACCEPTED,
    )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def export_data_view(request):
    """
    Request a GDPR data export. Returns the pending request immediately and
    queues the background task that builds the downloadable JSON archive.

    GET /api/v1/user-settings/export-data
    """
    user = request.user

    if _has_pending_deletion(user):
        return Response(
            {
                'error': 'deletion_in_progress',
                'message': _('An account deletion is in progress. Data export cannot be requested.'),
            },
            status=status.HTTP_409_CONFLICT,
        )

    pending = DataExportRequest.objects.filter(
        user=user,
        status__in=(DataExportRequest.STATUS_PENDING, DataExportRequest.STATUS_PROCESSING),
    ).order_by('-requested_at').first()

    if pending:
        return Response(
            _serialize_data_request(pending, 'data_export'),
            status=status.HTTP_200_OK,
        )

    # Throttle: allow one export per day per user.
    last_ready = DataExportRequest.objects.filter(
        user=user,
        status=DataExportRequest.STATUS_READY,
        completed_at__gte=timezone.now() - timezone.timedelta(days=1),
    ).first()
    if last_ready:
        return Response(
            _serialize_data_request(last_ready, 'data_export'),
            status=status.HTTP_200_OK,
        )

    with transaction.atomic():
        request_obj = DataExportRequest.objects.create(user=user)
        generate_data_export.delay(str(request_obj.id))

    logger.info("Data export requested")

    return Response(
        _serialize_data_request(request_obj, 'data_export'),
        status=status.HTTP_202_ACCEPTED,
    )
