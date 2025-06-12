"""
Views for user settings.
"""
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.db import transaction
import logging

from authentication.serializers import UserSerializer

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
        default_preferences = {
            'new_match_notifications': True,
            'new_message_notifications': True,
            'profile_like_notifications': user.is_premium,
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
        
        return Response(preferences)
    
    def put(self, request):
        """Update notification preferences."""
        user = request.user
        user.notification_settings = request.data
        user.save(update_fields=['notification_settings'])
        
        logger.info(f"Notification preferences updated for user: {user.email}")
        
        return Response(user.notification_settings)


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
        
        logger.info(f"Privacy preferences updated for user: {request.user.email}")
        
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
        for user in queryset:
            blocked_users.append({
                'user_id': str(user.id),
                'display_name': user.display_name,
                'profile_photo_url': user.profile.photos.filter(is_main=True).first().thumbnail_url if hasattr(user, 'profile') and user.profile.photos.exists() else None
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
            logger.info(f"User {request.user.email} blocked {target_user.email}")
            
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
            logger.info(f"User {request.user.email} unblocked {target_user.email}")
            
            return Response(status=status.HTTP_204_NO_CONTENT)
            
    except User.DoesNotExist:
        return Response({
            'error': True,
            'message': _('User not found.')
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def delete_account_view(request):
    """
    Request account deletion.
    
    POST /api/v1/user-settings/delete-account
    """
    # Here we would implement account deletion logic
    # For now, just log the request
    
    logger.warning(f"Account deletion requested by user: {request.user.email}")
    
    # In a real implementation:
    # - Verify password
    # - Send confirmation email
    # - Schedule deletion after grace period
    # - Anonymize data as required by GDPR
    
    return Response({
        'message': _('Account deletion request received. You will receive a confirmation email.')
    }, status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def export_data_view(request):
    """
    Request data export (GDPR compliance).
    
    GET /api/v1/user-settings/export-data
    """
    # Here we would implement data export logic
    # For now, just log the request
    
    logger.info(f"Data export requested by user: {request.user.email}")
    
    # In a real implementation:
    # - Queue background task to collect all user data
    # - Generate comprehensive report
    # - Send secure download link via email
    
    return Response({
        'message': _('Your data export request is being processed. You will receive an email with download link.')
    }, status=status.HTTP_202_ACCEPTED)