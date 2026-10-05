"""
Serializers for profiles app.
"""
import bleach
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.utils import timezone
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.db import transaction

from .models import GeoCity, GeoCountry, Profile, ProfilePhoto, Verification
from .geography import city_for_coordinates, distance_between
from authentication.serializers import UserSerializer
from subscriptions.utils import get_premium_limits
from subscriptions.pricing import resolve_effective_currency

User = get_user_model()


class ProfilePhotoSerializer(serializers.ModelSerializer):
    """
    Serializer for profile photos.
    Normalizes photo URLs via normalize_media_url (LOG-05).
    """
    photo_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = ProfilePhoto
        fields = [
            'id', 'photo_url', 'thumbnail_url', 'is_main',
            'caption', 'order', 'uploaded_at'
        ]
        read_only_fields = ['id', 'uploaded_at']

    def get_photo_url(self, obj):
        from .photo_storage import profile_photo_delivery_url
        return profile_photo_delivery_url(obj, self.context.get('request'))

    def get_thumbnail_url(self, obj):
        from .photo_storage import profile_photo_delivery_url
        return profile_photo_delivery_url(
            obj,
            self.context.get('request'),
            thumbnail=True,
        )


class ProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profiles with premium features.
    """
    user = UserSerializer(read_only=True)
    photos = ProfilePhotoSerializer(many=True, read_only=True)
    age = serializers.SerializerMethodField()
    distance_from_me_km = serializers.SerializerMethodField()
    premium_limits = serializers.SerializerMethodField()
    effective_currency = serializers.SerializerMethodField()
    geo_city_id = serializers.IntegerField(read_only=True)
    country_code = serializers.CharField(
        source='geo_city.country.code', read_only=True, allow_null=True,
    )

    class Meta:
        model = Profile
        fields = [
            'id', 'user', 'bio', 'gender', 'latitude', 'longitude',
            'city', 'country', 'preferred_currency', 'effective_currency',
            'hide_exact_location', 'location_enabled', 'location_mode',
            'location_accuracy_m', 'location_updated_at', 'geo_city_id',
            'country_code', 'gender_confirmation_required', 'interests',
            'relationship_types_sought', 'age_min_preference',
            'age_max_preference', 'distance_max_km', 'genders_sought',
            'is_hidden', 'show_online_status', 'allow_profile_in_discovery',
            'photos', 'age', 'distance_from_me_km', 'premium_limits',
            'created_at', 'updated_at'
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

    def get_premium_limits(self, obj):
        """Get premium limits for the profile owner."""
        request = self.context.get('request')
        if request and request.user == obj.user:
            return get_premium_limits(request.user)
        return None

    def get_effective_currency(self, obj):
        return resolve_effective_currency(obj.user)

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

    effective_currency = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            'bio', 'gender',
            'preferred_currency', 'effective_currency',
            'hide_exact_location', 'interests', 'relationship_types_sought',
            'age_min_preference', 'age_max_preference', 'distance_max_km',
            'genders_sought', 'is_hidden', 'show_online_status',
            'allow_profile_in_discovery'
        ]

    def get_effective_currency(self, obj):
        return resolve_effective_currency(obj.user)

    def validate_bio(self, value):
        """Sanitize bio to prevent XSS attacks — strip all HTML tags."""
        if value:
            return bleach.clean(value, tags=[], strip=True)
        return value

    def validate_interests(self, value):
        """Validate interests list."""
        if len(value) > 3:
            raise serializers.ValidationError(
                _("You can select a maximum of 3 interests.")
            )
        return value

    def validate_genders_sought(self, value):
        if len(value) > 1 or any(item not in {Profile.MALE, Profile.FEMALE} for item in value):
            raise serializers.ValidationError(
                _('Choose Homme, Femme, or leave the list empty for everyone.')
            )
        return value

    def validate_gender(self, value):
        """A gender can only be supplied once for an unconfirmed legacy profile."""
        instance = self.instance
        if value not in {Profile.MALE, Profile.FEMALE}:
            raise serializers.ValidationError(_('Choose Homme or Femme.'))
        if instance and instance.gender:
            if value != instance.gender:
                raise serializers.ValidationError(
                    _('Gender cannot be changed.'), code='gender_immutable'
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

    def update(self, instance, validated_data):
        # The first explicit choice completes the migration and permits the
        # profile to return to Discovery if it was withdrawn there.
        if 'gender' in validated_data and not instance.gender:
            validated_data['gender_confirmation_required'] = False
            if not instance.is_hidden:
                validated_data['allow_profile_in_discovery'] = True
        return super().update(instance, validated_data)


class GeoCountrySerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField()

    class Meta:
        model = GeoCountry
        fields = ['code', 'label', 'catalog_version']

    def get_label(self, obj):
        request = self.context.get('request')
        language = getattr(request, 'LANGUAGE_CODE', '') if request else ''
        return obj.name_fr if language.startswith('fr') and obj.name_fr else obj.name


class GeoCitySerializer(serializers.ModelSerializer):
    country_code = serializers.CharField(source='country.code', read_only=True)
    country_name = serializers.SerializerMethodField()

    class Meta:
        model = GeoCity
        fields = ['geonames_id', 'name', 'country_code', 'country_name']

    def get_country_name(self, obj):
        request = self.context.get('request')
        language = getattr(request, 'LANGUAGE_CODE', '') if request else ''
        return (
            obj.country.name_fr
            if language.startswith('fr') and obj.country.name_fr
            else obj.country.name
        )


class ProfileLocationUpdateSerializer(serializers.Serializer):
    """Dedicated private endpoint for automatic and manual location updates."""

    location_enabled = serializers.BooleanField(required=True)
    city_id = serializers.IntegerField(required=False, allow_null=True)
    latitude = serializers.DecimalField(
        max_digits=12, decimal_places=9, required=False, allow_null=True,
        min_value=-90, max_value=90,
    )
    longitude = serializers.DecimalField(
        max_digits=12, decimal_places=9, required=False, allow_null=True,
        min_value=-180, max_value=180,
    )
    accuracy_m = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=100000,
    )

    def validate(self, attrs):
        enabled = attrs['location_enabled']
        city_id = attrs.get('city_id')
        latitude = attrs.get('latitude')
        longitude = attrs.get('longitude')
        if enabled:
            if latitude is None or longitude is None:
                raise serializers.ValidationError({
                    'location_enabled': _('Device coordinates are required when location is enabled.')
                })
            if city_id is not None:
                raise serializers.ValidationError({
                    'city_id': _('A manual city cannot be combined with device location.')
                })
        elif city_id is None:
            # Disabling location with no city retains the previous manual city.
            return attrs
        return attrs

    @staticmethod
    def _quantize_coordinate(value):
        return value.quantize(Decimal('0.0000001'), rounding=ROUND_HALF_UP)

    @transaction.atomic
    def update(self, instance, validated_data):
        if not validated_data['location_enabled']:
            city_id = validated_data.get('city_id')
            if city_id is not None:
                city = GeoCity.objects.select_related('country').filter(
                    geonames_id=city_id
                ).first()
                if city is None:
                    raise serializers.ValidationError({'city_id': _('Unknown city.')})
                instance.geo_city = city
                instance.city = city.name
                instance.country = city.country.name
                instance.location_mode = 'manual'
            instance.location_enabled = False
            # Precise foreground readings are deleted as soon as the user
            # opts out. Manual city centroids remain for estimated distance.
            instance.latitude = None
            instance.longitude = None
            instance.location_accuracy_m = None
            instance.location_updated_at = None
            instance.save()
            return instance

        latitude = self._quantize_coordinate(validated_data['latitude'])
        longitude = self._quantize_coordinate(validated_data['longitude'])
        city = city_for_coordinates(latitude, longitude)
        if city is None:
            raise serializers.ValidationError({
                'location_enabled': _(
                    'No catalog city is available near this position. Choose a city manually.'
                )
            })
        instance.geo_city = city
        instance.city = city.name
        instance.country = city.country.name
        instance.latitude = latitude
        instance.longitude = longitude
        instance.location_accuracy_m = validated_data.get('accuracy_m')
        instance.location_updated_at = timezone.now()
        instance.location_enabled = True
        instance.location_mode = 'automatic'
        instance.save()
        return instance


class PhotoReorderSerializer(serializers.Serializer):
    photo_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False,
    )


class PublicProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for public profile view (other users viewing).
    """
    user_id = serializers.UUIDField(source='user.id', read_only=True)
    display_name = serializers.CharField(source='user.display_name')
    age = serializers.SerializerMethodField()
    is_verified = serializers.BooleanField(source='user.is_verified')
    is_premium = serializers.BooleanField(source='user.is_premium')
    last_active_display = serializers.SerializerMethodField()
    photos = ProfilePhotoSerializer(many=True, read_only=True)
    distance_from_me_km = serializers.SerializerMethodField()
    distance_estimated = serializers.SerializerMethodField()
    same_city = serializers.SerializerMethodField()
    liked_at = serializers.DateTimeField(required=False, allow_null=True)

    class Meta:
        model = Profile
        fields = [
            'id', 'user_id', 'display_name', 'bio', 'age', 'city', 'country',
            'interests', 'relationship_types_sought', 'is_verified',
            'is_premium', 'last_active_display', 'photos',
            'distance_from_me_km', 'distance_estimated', 'same_city', 'liked_at'
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
        request = self.context.get('request')
        if not request or not hasattr(request.user, 'profile'):
            return None
        result = self._distance(obj)
        return result.km if result else None

    def _distance(self, obj):
        request = self.context.get('request')
        if not request or not hasattr(request.user, 'profile'):
            return None
        cache = self.context.setdefault('_profile_distance_cache', {})
        key = str(obj.pk)
        if key not in cache:
            cache[key] = distance_between(request.user.profile, obj)
        return cache[key]

    def get_distance_estimated(self, obj):
        result = self._distance(obj)
        return result.estimated if result else None

    def get_same_city(self, obj):
        result = self._distance(obj)
        return result.same_city if result else False

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
        # The same explicit bound is enforced by the private storage adapter
        # so administrative scripts cannot bypass the HTTP serializer.
        if value.size > settings.PROFILE_MEDIA_MAX_UPLOAD_BYTES:
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
    """Legacy projection serializer with no KYC evidence or challenge data."""

    class Meta:
        model = Verification
        fields = [
            'id', 'status', 'rejection_reason', 'submitted_at',
            'reviewed_at', 'expires_at',
        ]
        read_only_fields = [
            'id', 'status', 'rejection_reason', 'submitted_at',
            'reviewed_at', 'expires_at',
        ]


class KycStartSerializer(serializers.Serializer):
    """Validate a consented, idempotent KYC start request."""

    consent_version = serializers.CharField(max_length=80)
    confirmations = serializers.DictField()
    idempotency_key = serializers.RegexField(r'^[A-Za-z0-9._:-]{16,128}$')

    REQUIRED_CONFIRMATIONS = {
        'official_identity_document',
        'medical_document_under_90_days',
        'single_use_selfie_challenge',
        'human_review_acknowledged',
    }

    def validate_confirmations(self, value):
        if set(value) != self.REQUIRED_CONFIRMATIONS:
            raise serializers.ValidationError(
                _('All required KYC confirmations must be provided.')
            )
        if any(item is not True for item in value.values()):
            raise serializers.ValidationError(
                _('All KYC confirmations must be accepted.')
            )
        return value


class KycUploadIntentRequestSerializer(serializers.Serializer):
    """Validate future upload constraints without accepting a file or path."""

    attempt_id = serializers.UUIDField()
    document_type = serializers.ChoiceField(
        choices=['identity_document', 'medical_document', 'selfie_with_code']
    )
    mime_type = serializers.ChoiceField(
        choices=['image/jpeg', 'image/jpg', 'image/png', 'application/pdf']
    )
    size_bytes = serializers.IntegerField(min_value=1, max_value=10 * 1024 * 1024)
    sha256 = serializers.RegexField(r'^[A-Fa-f0-9]{64}$')
    idempotency_key = serializers.RegexField(r'^[A-Za-z0-9._:-]{16,128}$')

    def validate(self, attrs):
        if attrs['document_type'] == 'selfie_with_code':
            if attrs['mime_type'] == 'application/pdf':
                raise serializers.ValidationError(
                    {'mime_type': _('A selfie must be a JPEG or PNG image.')}
                )
            if attrs['size_bytes'] > 5 * 1024 * 1024:
                raise serializers.ValidationError(
                    {'size_bytes': _('A selfie cannot exceed 5 MiB.')}
                )
        return attrs


class KycSubmitRequestSerializer(serializers.Serializer):
    """Validate references to server-owned upload intents only."""

    attempt_id = serializers.UUIDField()
    identity_upload_id = serializers.UUIDField()
    medical_upload_id = serializers.UUIDField()
    selfie_upload_id = serializers.UUIDField()
    selfie_challenge_code = serializers.CharField(min_length=6, max_length=32)
    idempotency_key = serializers.RegexField(r'^[A-Za-z0-9._:-]{16,128}$')


class KycUploadCompleteSerializer(serializers.Serializer):
    """Accept only the opaque server-issued upload identifier after direct PUT."""

    upload_id = serializers.UUIDField()
