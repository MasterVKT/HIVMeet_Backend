"""
Serializers for profiles app.
"""
from django.utils import timezone
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.db import transaction

from .models import Profile, ProfilePhoto, Verification
from authentication.serializers import UserSerializer

User = get_user_model()


class ProfilePhotoSerializer(serializers.ModelSerializer):
    """
    Serializer for profile photos.
    """
    
    class Meta:
        model = ProfilePhoto
        fields = [
            'id', 'photo_url', 'thumbnail_url', 'is_main',
            'caption', 'order', 'uploaded_at'
        ]
        read_only_fields = ['id', 'uploaded_at']


class ProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profiles.
    """
    user = UserSerializer(read_only=True)
    photos = ProfilePhotoSerializer(many=True, read_only=True)
    age = serializers.SerializerMethodField()
    distance_from_me_km = serializers.SerializerMethodField()
    
    class Meta:
        model = Profile
        fields = [
            'id', 'user', 'bio', 'gender', 'latitude', 'longitude',
            'city', 'country', 'hide_exact_location', 'interests',
            'relationship_types_sought', 'age_min_preference',
            'age_max_preference', 'distance_max_km', 'genders_sought',
            'is_hidden', 'show_online_status', 'allow_profile_in_discovery',
            'photos', 'age', 'distance_from_me_km', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_age(self, obj):
        """Get user's age."""
        return obj.user.age
    
    def get_distance_from_me_km(self, obj):
        """Calculate distance from current user (if applicable)."""
        request = self.context.get('request')
        if request and hasattr(request.user, 'profile'):
            # This would use a proper distance calculation
            # For now, return None
            return None
        return None
    
    def validate_interests(self, value):
        """Validate interests list."""
        if len(value) > 3:
            raise serializers.ValidationError(
                _("You can select a maximum of 3 interests.")
            )
        return value
    
    def validate(self, attrs):
        """Validate age preferences."""
        age_min = attrs.get('age_min_preference', 18)
        age_max = attrs.get('age_max_preference', 99)
        
        if age_min > age_max:
            raise serializers.ValidationError({
                'age_max_preference': _("Maximum age must be greater than minimum age.")
            })
        
        return attrs


class ProfileCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/updating profiles.
    """
    
    class Meta:
        model = Profile
        fields = [
            'bio', 'gender', 'latitude', 'longitude', 'city', 'country',
            'hide_exact_location', 'interests', 'relationship_types_sought',
            'age_min_preference', 'age_max_preference', 'distance_max_km',
            'genders_sought', 'is_hidden', 'show_online_status',
            'allow_profile_in_discovery'
        ]
    
    def validate_interests(self, value):
        """Validate interests list."""
        if len(value) > 3:
            raise serializers.ValidationError(
                _("You can select a maximum of 3 interests.")
            )
        return value
    
    def validate(self, attrs):
        """Validate age preferences."""
        age_min = attrs.get('age_min_preference', self.instance.age_min_preference if self.instance else 18)
        age_max = attrs.get('age_max_preference', self.instance.age_max_preference if self.instance else 99)
        
        if age_min > age_max:
            raise serializers.ValidationError({
                'age_max_preference': _("Maximum age must be greater than minimum age.")
            })
        
        return attrs


class PublicProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for public profile view (other users viewing).
    """
    display_name = serializers.CharField(source='user.display_name')
    age = serializers.SerializerMethodField()
    is_verified = serializers.BooleanField(source='user.is_verified')
    is_premium = serializers.BooleanField(source='user.is_premium')
    last_active_display = serializers.SerializerMethodField()
    photos = ProfilePhotoSerializer(many=True, read_only=True)
    distance_from_me_km = serializers.SerializerMethodField()
    
    class Meta:
        model = Profile
        fields = [
            'id', 'display_name', 'bio', 'age', 'city', 'country',
            'interests', 'relationship_types_sought', 'is_verified',
            'is_premium', 'last_active_display', 'photos',
            'distance_from_me_km'
        ]
    
    def get_age(self, obj):
        """Get user's age."""
        return obj.user.age
    
    def get_last_active_display(self, obj):
        """Get display-friendly last active time."""
        last_active = obj.user.last_active
        now = timezone.now()
        diff = now - last_active
        
        if diff.total_seconds() < 300:  # 5 minutes
            return _("Online")
        elif diff.total_seconds() < 3600:  # 1 hour
            return _("Active recently")
        elif diff.days == 0:
            return _("Active today")
        elif diff.days == 1:
            return _("Active yesterday")
        else:
            return _("Active %(days)d days ago") % {'days': diff.days}
    
    def get_distance_from_me_km(self, obj):
        """Calculate distance from current user."""
        # Implementation would go here
        return None
    
    def to_representation(self, instance):
        """Customize representation based on privacy settings."""
        data = super().to_representation(instance)
        
        # Hide exact location if requested
        if instance.hide_exact_location:
            data.pop('city', None)
        
        return data


class PhotoUploadSerializer(serializers.Serializer):
    """
    Serializer for photo upload requests.
    """
    file = serializers.ImageField(required=True)
    is_main = serializers.BooleanField(default=False)
    caption = serializers.CharField(max_length=200, required=False, allow_blank=True)
    
    def validate_file(self, value):
        """Validate uploaded file."""
        # Check file size (5MB max)
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError(
                _("File size cannot exceed 5MB.")
            )
        
        # Check file type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                _("Only JPEG and PNG images are allowed.")
            )
        
        return value


class VerificationSerializer(serializers.ModelSerializer):
    """
    Serializer for verification data.
    """
    required_documents = serializers.SerializerMethodField()
    
    class Meta:
        model = Verification
        fields = [
            'id', 'status', 'rejection_reason', 'submitted_at',
            'reviewed_at', 'expires_at', 'verification_code',
            'required_documents'
        ]
        read_only_fields = [
            'id', 'status', 'rejection_reason', 'submitted_at',
            'reviewed_at', 'expires_at', 'verification_code'
        ]
    
    def get_required_documents(self, obj):
        """Get required documents and their status."""
        documents = []
        
        # ID document
        documents.append({
            'type': 'identity_document',
            'status': 'uploaded' if obj.id_document_path else 'pending',
            'name': _('Identity Document')
        })
        
        # Medical document
        documents.append({
            'type': 'medical_document',
            'status': 'uploaded' if obj.medical_document_path else 'pending',
            'name': _('Medical Document')
        })
        
        # Selfie with code
        documents.append({
            'type': 'selfie_with_code',
            'status': 'uploaded' if obj.selfie_path else 'pending',
            'name': _('Selfie with Code')
        })
        
        return documents


class VerificationUploadSerializer(serializers.Serializer):
    """
    Serializer for verification document upload.
    """
    document_type = serializers.ChoiceField(
        choices=['identity_document', 'medical_document', 'selfie_with_code']
    )
    file_type = serializers.CharField()
    file_size = serializers.IntegerField()
    
    def validate_file_size(self, value):
        """Validate file size."""
        # 10MB max for documents
        if value > 10 * 1024 * 1024:
            raise serializers.ValidationError(
                _("File size cannot exceed 10MB.")
            )
        return value
    
    def validate_file_type(self, value):
        """Validate file type."""
        allowed_types = [
            'image/jpeg', 'image/jpg', 'image/png',
            'application/pdf'
        ]
        if value not in allowed_types:
            raise serializers.ValidationError(
                _("Only JPEG, PNG, and PDF files are allowed.")
            )
        return value


class VerificationSubmitSerializer(serializers.Serializer):
    """
    Serializer for submitting verification documents.
    """
    documents = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=False
    )
    selfie_code_used = serializers.CharField(required=False)
    
    def validate_documents(self, value):
        """Validate document list."""
        valid_types = ['identity_document', 'medical_document', 'selfie_with_code']
        
        for doc in value:
            if 'document_type' not in doc or 'file_path_on_storage' not in doc:
                raise serializers.ValidationError(
                    _("Each document must have 'document_type' and 'file_path_on_storage'.")
                )
            
            if doc['document_type'] not in valid_types:
                raise serializers.ValidationError(
                    _("Invalid document type: %(type)s") % {'type': doc['document_type']}
                )
        
        return value