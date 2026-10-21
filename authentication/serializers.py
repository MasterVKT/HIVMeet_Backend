"""
Serializers for authentication app.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _
from datetime import date
import re

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    gender = serializers.ChoiceField(choices=('male', 'female'), write_only=True)
    
    class Meta:
        model = User
        fields = [
            'email', 'password', 'password_confirm',
            'birth_date', 'display_name', 'phone_number', 'gender'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'birth_date': {'required': True},
            'display_name': {'required': True},
        }
    
    def validate_email(self, value):
        """Validate email format and uniqueness."""
        normalized = value.strip().lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError(
                _("A user with this email already exists."),
                code='unique',
            )
        return normalized
    
    def validate_display_name(self, value):
        """Validate display name."""
        value = value.strip()
        if len(value) < 3 or len(value) > 30:
            raise serializers.ValidationError(
                _("Display name must be between 3 and 30 characters."),
                code='invalid_length',
            )
        
        # Markup delimiters and control characters are rejected. Apostrophes
        # and ampersands are legitimate in names (e.g. "N'Guessan") and are
        # escaped when displayed, so they must not block registration.
        if re.search(r'[<>"]', value) or any(ord(char) < 32 for char in value):
            raise serializers.ValidationError(
                _("Display name contains invalid characters."),
                code='invalid_characters',
            )
        
        return value
    
    def validate_birth_date(self, value):
        """Validate birth date (must be 18+)."""
        if not value:
            raise serializers.ValidationError(
                _("Birth date is required."),
                code='required',
            )
        
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        
        if age < 18:
            raise serializers.ValidationError(
                _("You must be at least 18 years old to use this service."),
                code='age_requirement',
            )
        
        if age > 150:
            raise serializers.ValidationError(
                _("Please enter a valid birth date."),
                code='invalid',
            )
        
        return value
    
    def validate_phone_number(self, value):
        """Validate and normalise a phone number.

        Separators commonly typed on mobile keyboards are removed before the
        length check. The accepted contract is an optional leading ``+``
        followed by 8 to 15 digits, which covers local and international
        numbers used by the mobile client.
        """
        if not value:
            return value

        normalized = re.sub(r'[\s\-.()]', '', value)
        if not re.fullmatch(r'\+?[0-9]{8,15}', normalized):
            raise serializers.ValidationError(
                _("Phone number must be in international format."),
                code='invalid',
            )
        return normalized
    
    def validate(self, attrs):
        """Validate passwords match."""
        if attrs.get('password') != attrs.get('password_confirm'):
            raise serializers.ValidationError({
                'password_confirm': serializers.ErrorDetail(
                    _("Password fields didn't match."),
                    code='password_mismatch',
                )
            })
        
        attrs.pop('password_confirm')
        return attrs
    
    def create(self, validated_data):
        """Create user with validated data."""
        gender = validated_data.pop('gender')
        user = User.objects.create_user(**validated_data)
        # The post-save signal created the related profile in this transaction.
        user.profile.gender = gender
        user.profile.gender_confirmation_required = False
        user.profile.legacy_gender = ''
        user.profile.save(update_fields=[
            'gender', 'gender_confirmation_required', 'legacy_gender',
        ])
        return user


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login.
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    remember_me = serializers.BooleanField(
        required=False,
        default=False
    )
    
    def validate_email(self, value):
        """Normalize email."""
        return value.lower()


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for user data in responses.
    """
    age = serializers.ReadOnlyField()
    profile_complete = serializers.SerializerMethodField()
    is_premium = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'display_name', 'birth_date', 'age',
            'is_verified', 'is_premium', 'premium_until', 'verification_status',
            'profile_complete', 'last_active', 'date_joined'
        ]
        read_only_fields = [
            'id', 'email', 'is_verified', 'is_premium', 'premium_until',
            'verification_status', 'last_active', 'date_joined'
        ]
    
    def get_profile_complete(self, obj):
        """Check if user has completed their profile."""
        # This will be properly implemented when we have the Profile model
        return hasattr(obj, 'profile') and obj.profile is not None

    def get_is_premium(self, obj):
        from subscriptions.utils import is_premium_user
        return is_premium_user(obj)


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Serializer for password reset request.
    """
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        """Normalize email."""
        return value.lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer for password reset confirmation.
    """
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    new_password_confirm = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    
    def validate(self, attrs):
        """Validate passwords match."""
        if attrs.get('new_password') != attrs.get('new_password_confirm'):
            raise serializers.ValidationError({
                'new_password_confirm': _("Password fields didn't match.")
            })
        
        attrs.pop('new_password_confirm')
        return attrs


class TokenRefreshSerializer(serializers.Serializer):
    """
    Serializer for token refresh.
    """
    refresh_token = serializers.CharField(required=True)


class EmailVerificationSerializer(serializers.Serializer):
    """
    Serializer for email verification.
    """
    token = serializers.CharField(required=True)


class FCMTokenSerializer(serializers.Serializer):
    """
    Serializer for FCM token registration.
    """
    fcm_token = serializers.CharField(required=True)
    device_id = serializers.CharField(required=False, allow_blank=True)
    platform = serializers.ChoiceField(
        choices=['ios', 'android', 'web'],
        required=False
    )
