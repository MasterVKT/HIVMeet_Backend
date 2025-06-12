"""
Views for profiles app.
"""
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
import logging

from .models import Profile, ProfilePhoto, Verification
from .serializers import (
    ProfileSerializer,
    ProfileCreateUpdateSerializer,
    PublicProfileSerializer,
    PhotoUploadSerializer,
    VerificationSerializer,
    VerificationUploadSerializer,
    VerificationSubmitSerializer
)
from .signals import generate_verification_code
from hivmeet_backend.storage.manager import storage_manager

logger = logging.getLogger('hivmeet.profiles')
User = get_user_model()


class MyProfileView(generics.RetrieveUpdateAPIView):
    """
    Get or update the current user's profile.
    
    GET /api/v1/user-profiles/me
    PUT/PATCH /api/v1/user-profiles/me
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ProfileCreateUpdateSerializer
        return ProfileSerializer
    
    def get_object(self):
        """Get or create profile for current user."""
        profile, created = Profile.objects.get_or_create(user=self.request.user)
        if created:
            logger.info(f"Profile created for user: {self.request.user.email}")
        return profile
    
    def perform_update(self, serializer):
        """Update profile and log the action."""
        serializer.save()
        logger.info(f"Profile updated for user: {self.request.user.email}")


class UserProfileView(generics.RetrieveAPIView):
    """
    Get another user's public profile.
    
    GET /api/v1/user-profiles/{user_id}
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PublicProfileSerializer
    lookup_field = 'user__id'
    lookup_url_kwarg = 'user_id'
    
    def get_queryset(self):
        """Get profiles that are visible."""
        return Profile.objects.filter(
            user__is_active=True,
            is_hidden=False,
            allow_profile_in_discovery=True
        ).select_related('user').prefetch_related('photos')
    
    def get_object(self):
        """Get profile and check permissions."""
        queryset = self.get_queryset()
        
        # Get the profile
        filter_kwargs = {self.lookup_field: self.kwargs[self.lookup_url_kwarg]}
        profile = get_object_or_404(queryset, **filter_kwargs)
        
        # Check if user is blocked
        if self.request.user in profile.user.blocked_users.all():
            raise PermissionDenied(_("You cannot view this profile."))
        
        # Check if current user is blocked by this user
        if profile.user in self.request.user.blocked_users.all():
            raise PermissionDenied(_("You cannot view this profile."))
        
        # Increment view count
        profile.increment_views()
        
        return profile


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_photo_view(request):
    """
    Upload a profile photo.
    
    POST /api/v1/user-profiles/me/photos
    """
    serializer = PhotoUploadSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        profile = request.user.profile
        
        # Check photo limit
        photo_count = profile.photos.count()
        max_photos = 6 if request.user.is_premium else 1
        
        if photo_count >= max_photos:
            return Response({
                'error': True,
                'message': _('Photo limit reached. %(max)d photos allowed.') % {'max': max_photos}
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Upload image to Firebase Storage
        file = serializer.validated_data['file']
        base_path = f"profiles/{request.user.id}/"
        
        upload_result = storage_manager.upload_image(
            image_data=file.read(),
            base_path=base_path
        )
        
        # Create photo record
        with transaction.atomic():
            photo = ProfilePhoto.objects.create(
                profile=profile,
                photo_url=upload_result['main'],
                thumbnail_url=upload_result['thumbnail'],
                is_main=serializer.validated_data.get('is_main', False) or photo_count == 0,
                caption=serializer.validated_data.get('caption', ''),
                order=photo_count
            )
        
        logger.info(f"Photo uploaded for user: {request.user.email}")
        
        return Response({
            'photo_id': str(photo.id),
            'url': photo.photo_url,
            'thumbnail_url': photo.thumbnail_url,
            'is_main': photo.is_main,
            'caption': photo.caption,
            'uploaded_at': photo.uploaded_at
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Photo upload error for user {request.user.email}: {str(e)}")
        return Response({
            'error': True,
            'message': _('Failed to upload photo. Please try again.')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def set_main_photo_view(request, photo_id):
    """
    Set a photo as the main profile photo.
    
    PUT /api/v1/user-profiles/me/photos/{photo_id}/set-main
    """
    try:
        photo = ProfilePhoto.objects.get(
            id=photo_id,
            profile__user=request.user
        )
        
        photo.is_main = True
        photo.save()
        
        logger.info(f"Main photo set for user: {request.user.email}")
        
        return Response({
            'message': _('Main photo updated successfully.')
        }, status=status.HTTP_200_OK)
        
    except ProfilePhoto.DoesNotExist:
        return Response({
            'error': True,
            'message': _('Photo not found.')
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def delete_photo_view(request, photo_id):
    """
    Delete a profile photo.
    
    DELETE /api/v1/user-profiles/me/photos/{photo_id}
    """
    try:
        photo = ProfilePhoto.objects.get(
            id=photo_id,
            profile__user=request.user
        )
        
        # Check if it's the only photo and is main
        if photo.is_main and photo.profile.photos.count() == 1:
            return Response({
                'error': True,
                'message': _('Cannot delete the only photo.')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Delete from storage
        # Note: We're not deleting from Firebase Storage immediately
        # This could be done in a background task
        
        # Delete record
        photo.delete()
        
        # If it was main, set another as main
        if photo.is_main:
            next_photo = photo.profile.photos.first()
            if next_photo:
                next_photo.is_main = True
                next_photo.save()
        
        logger.info(f"Photo deleted for user: {request.user.email}")
        
        return Response(status=status.HTTP_204_NO_CONTENT)
        
    except ProfilePhoto.DoesNotExist:
        return Response({
            'error': True,
            'message': _('Photo not found.')
        }, status=status.HTTP_404_NOT_FOUND)


class VerificationStatusView(generics.RetrieveAPIView):
    """
    Get verification status for current user.
    
    GET /api/v1/user-profiles/me/verification
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = VerificationSerializer
    
    def get_object(self):
        """Get or create verification record."""
        verification, created = Verification.objects.get_or_create(
            user=self.request.user
        )
        
        # Generate verification code if needed
        if not verification.verification_code and verification.status != Verification.VERIFIED:
            verification.verification_code = generate_verification_code()
            verification.save()
        
        return verification


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_upload_url_view(request):
    """
    Generate a signed URL for document upload.
    
    POST /api/v1/user-profiles/me/verification/generate-upload-url
    """
    serializer = VerificationUploadSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        document_type = serializer.validated_data['document_type']
        file_type = serializer.validated_data['file_type']
        
        # Generate file path
        file_extension = file_type.split('/')[-1]
        file_path = f"verification/{request.user.id}/{document_type}.{file_extension}"
        
        # Generate signed URL for upload
        upload_url = storage_manager.generate_signed_url(
            file_path=file_path,
            expiration_minutes=30,
            method='PUT'
        )
        
        return Response({
            'upload_url': upload_url,
            'file_path_on_storage': file_path
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error generating upload URL for user {request.user.email}: {str(e)}")
        return Response({
            'error': True,
            'message': _('Failed to generate upload URL.')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@transaction.atomic
def submit_verification_documents_view(request):
    """
    Submit verification documents for review.
    
    POST /api/v1/user-profiles/me/verification/submit-documents
    """
    serializer = VerificationSubmitSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'error': True,
            'message': _('Validation error'),
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        verification = request.user.verification
        documents = serializer.validated_data['documents']
        
        # Update document paths
        for doc in documents:
            doc_type = doc['document_type']
            file_path = doc['file_path_on_storage']
            
            if doc_type == 'identity_document':
                verification.id_document_path = file_path
            elif doc_type == 'medical_document':
                verification.medical_document_path = file_path
            elif doc_type == 'selfie_with_code':
                verification.selfie_path = file_path
                
                # Verify code if provided
                code_used = serializer.validated_data.get('selfie_code_used')
                if code_used and code_used != verification.verification_code:
                    return Response({
                        'error': True,
                        'message': _('Invalid verification code.')
                    }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update status
        if verification.id_document_path and verification.medical_document_path and verification.selfie_path:
            verification.status = Verification.PENDING_REVIEW
            verification.submitted_at = timezone.now()
        else:
            # Determine what's missing
            if not verification.id_document_path:
                verification.status = Verification.PENDING_ID
            elif not verification.medical_document_path:
                verification.status = Verification.PENDING_MEDICAL
            elif not verification.selfie_path:
                verification.status = Verification.PENDING_SELFIE
        
        verification.save()
        
        # Update user verification status
        request.user.verification_status = 'pending'
        request.user.save(update_fields=['verification_status'])
        
        logger.info(f"Verification documents submitted for user: {request.user.email}")
        
        return Response({
            'verification_status': verification.status,
            'message': _('Documents submitted for verification.')
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error submitting verification for user {request.user.email}: {str(e)}")
        return Response({
            'error': True,
            'message': _('Failed to submit documents.')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)