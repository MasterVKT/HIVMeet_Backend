"""
Profile models for HIVMeet.
"""
from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import uuid

User = get_user_model()


class Profile(models.Model):
    """
    User profile model containing detailed information.
    """
    
    # Relationship types
    FRIENDSHIP = 'friendship'
    LONG_TERM = 'long_term'
    SHORT_TERM = 'short_term'
    CASUAL = 'casual'
    
    RELATIONSHIP_CHOICES = [
        (FRIENDSHIP, _('Friendship')),
        (LONG_TERM, _('Long-term relationship')),
        (SHORT_TERM, _('Short-term relationship')),
        (CASUAL, _('Casual dating')),
    ]

    CURRENCY_AUTO = 'AUTO'
    CURRENCY_XAF = 'XAF'
    CURRENCY_EUR = 'EUR'

    CURRENCY_CHOICES = [
        (CURRENCY_AUTO, _('Automatic')),
        (CURRENCY_XAF, _('Central African CFA franc')),
        (CURRENCY_EUR, _('Euro')),
    ]
    
    # Gender choices
    MALE = 'male'
    FEMALE = 'female'
    GENDER_CHOICES = [
        (MALE, _('Male')),
        (FEMALE, _('Female')),
    ]
    
    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # One-to-one relationship with User
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    
    # Bio and personal info
    bio = models.TextField(
        max_length=500,
        blank=True,
        verbose_name=_('Bio'),
        help_text=_('Tell us about yourself (max 500 characters)')
    )
    
    gender = models.CharField(
        max_length=20,
        choices=GENDER_CHOICES,
        blank=True,
        default='',
        verbose_name=_('Gender')
    )
    # Kept only during the explicit-confirmation migration.  It is never
    # serialized and is not used for discovery or matching decisions.
    legacy_gender = models.CharField(max_length=20, blank=True, default='')
    gender_confirmation_required = models.BooleanField(default=False)
    
    # Location
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        verbose_name=_('Latitude')
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        verbose_name=_('Longitude')
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('City')
    )
    country = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Country')
    )
    preferred_currency = models.CharField(
        max_length=4,
        choices=CURRENCY_CHOICES,
        default=CURRENCY_AUTO,
        verbose_name=_('Preferred payment currency'),
    )
    hide_exact_location = models.BooleanField(
        default=False,
        verbose_name=_('Hide exact location')
    )
    # ``location_enabled`` means the user has opted into a foreground device
    # lookup.  Manual city selection remains available when it is disabled.
    location_enabled = models.BooleanField(
        default=True,
        verbose_name=_('Use device location')
    )
    location_mode = models.CharField(
        max_length=12,
        choices=[('automatic', _('Automatic')), ('manual', _('Manual'))],
        default='manual',
        verbose_name=_('Location mode')
    )
    location_accuracy_m = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Location accuracy in metres')
    )
    location_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Location updated at')
    )
    geo_city = models.ForeignKey(
        'GeoCity',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='profiles',
        verbose_name=_('Catalog city')
    )
    
    # Interests (limited to 3)
    interests = ArrayField(
        models.CharField(max_length=50),
        size=3,
        blank=True,
        default=list,
        verbose_name=_('Interests')
    )
    
    # Relationship preferences
    relationship_types_sought = ArrayField(
        models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES),
        blank=True,
        default=list,
        verbose_name=_('Types of relationships sought')
    )
    
    # Search preferences
    age_min_preference = models.IntegerField(
        default=18,
        validators=[MinValueValidator(18), MaxValueValidator(99)],
        verbose_name=_('Minimum age preference')
    )
    age_max_preference = models.IntegerField(
        default=99,
        validators=[MinValueValidator(18), MaxValueValidator(99)],
        verbose_name=_('Maximum age preference')
    )
    distance_max_km = models.IntegerField(
        default=25,
        validators=[MinValueValidator(5), MaxValueValidator(100)],
        verbose_name=_('Maximum distance (km)')
    )
    genders_sought = ArrayField(
        models.CharField(max_length=20, choices=GENDER_CHOICES),
        blank=True,
        default=list,
        null=False,  # Prevent NULL values
        verbose_name=_('Gender preferences'),
        help_text=_('List of genders this profile is interested in. Empty list means open to all genders.')
    )
    
    # Additional search filters
    verified_only = models.BooleanField(
        default=False,
        verbose_name=_('Show verified profiles only')
    )
    online_only = models.BooleanField(
        default=False,
        verbose_name=_('Show online profiles only')
    )
    
    # Visibility settings
    is_hidden = models.BooleanField(
        default=False,
        verbose_name=_('Profile hidden')
    )
    show_online_status = models.BooleanField(
        default=True,
        verbose_name=_('Show online status')
    )
    allow_profile_in_discovery = models.BooleanField(
        default=True,
        verbose_name=_('Allow profile in discovery')
    )
    
    # Statistics
    profile_views = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Profile views')
    )
    likes_received = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Likes received')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated at')
    )
    
    class Meta:
        verbose_name = _('Profile')
        verbose_name_plural = _('Profiles')
        db_table = 'profiles'
        indexes = [
            models.Index(fields=['city', 'country']),
            models.Index(fields=['is_hidden', 'allow_profile_in_discovery']),
        ]
    
    def __str__(self):
        return f"{self.user.display_name}'s profile"
    
    def clean(self):
        """Validate the profile."""
        from django.core.exceptions import ValidationError
        
        # Ensure genders_sought is a list, never NULL or empty string
        if self.genders_sought is None:
            self.genders_sought = []
        elif isinstance(self.genders_sought, str) and not self.genders_sought:
            self.genders_sought = []
        
        # Validate all gender choices are valid
        if self.gender and self.gender not in dict(self.GENDER_CHOICES):
            raise ValidationError({'gender': _('Invalid gender.')})
        if self.genders_sought:
            valid_genders = dict(self.GENDER_CHOICES).keys()
            invalid = [g for g in self.genders_sought if g not in valid_genders]
            if invalid:
                raise ValidationError({
                    'genders_sought': _('Invalid genders: %(invalid)s') % {'invalid': invalid}
                })
            if len(set(self.genders_sought)) != 1:
                raise ValidationError({
                    'genders_sought': _(
                        'Choose one gender or leave the list empty for everyone.'
                    )
                })
    
    def save(self, *args, **kwargs):
        """Save the profile with validation."""
        self.clean()
        super().save(*args, **kwargs)
    
    def get_location_display(self):
        """Get displayable location based on privacy settings."""
        if self.hide_exact_location:
            return self.country
        return f"{self.city}, {self.country}" if self.city else self.country
    
    def increment_views(self):
        """Increment profile view count."""
        self.profile_views += 1
        self.save(update_fields=['profile_views'])


class GeoCountry(models.Model):
    """Versioned GeoNames country entry used by the manual location picker."""

    code = models.CharField(primary_key=True, max_length=2)
    geonames_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    name = models.CharField(max_length=120)
    name_fr = models.CharField(max_length=120, blank=True)
    search_name = models.CharField(max_length=255, blank=True, db_index=True)
    catalog_version = models.CharField(max_length=32, default='geonames-v1')

    class Meta:
        db_table = 'geo_countries'
        ordering = ['name']

    def __str__(self):
        return self.code


class GeoCity(models.Model):
    """A populated GeoNames city entry. Coordinates never leave public DTOs."""

    geonames_id = models.PositiveIntegerField(primary_key=True)
    country = models.ForeignKey(
        GeoCountry,
        on_delete=models.CASCADE,
        related_name='cities',
    )
    name = models.CharField(max_length=180)
    ascii_name = models.CharField(max_length=180, blank=True)
    search_name = models.CharField(max_length=255, blank=True, db_index=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    population = models.PositiveBigIntegerField(default=0)
    catalog_version = models.CharField(max_length=32, default='geonames-v1')

    class Meta:
        db_table = 'geo_cities'
        ordering = ['-population', 'name']
        indexes = [
            models.Index(fields=['country', 'name']),
            models.Index(fields=['country', 'ascii_name']),
        ]

    def __str__(self):
        return f'{self.name}, {self.country_id}'


class GeoCatalogRelease(models.Model):
    """Auditable GeoNames import metadata for the active city catalogue."""

    catalog_version = models.CharField(max_length=32, primary_key=True)
    sha256 = models.CharField(max_length=64)
    city_count = models.PositiveIntegerField()
    attribution_url = models.URLField()
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'geo_catalog_releases'


class ProfilePhoto(models.Model):
    """
    Model for user profile photos.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='photos'
    )
    
    # Legacy URLs remain only until the private-media migration has copied,
    # verified and deleted their public source object. New photos use opaque
    # private keys below and never persist a delivery URL.
    photo_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name=_('Photo URL')
    )
    thumbnail_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name=_('Thumbnail URL')
    )
    LEGACY_PUBLIC = 'legacy_public'
    MIGRATION_COPIED = 'migration_copied'
    PRIVATE = 'private'
    MIGRATION_FAILED = 'migration_failed'
    STORAGE_STATE_CHOICES = [
        (LEGACY_PUBLIC, _('Legacy public object')),
        (MIGRATION_COPIED, _('Private copy awaiting legacy deletion')),
        (PRIVATE, _('Private object')),
        (MIGRATION_FAILED, _('Private migration failed')),
    ]
    storage_key = models.CharField(max_length=255, blank=True, db_index=True)
    thumbnail_storage_key = models.CharField(max_length=255, blank=True)
    storage_state = models.CharField(
        max_length=24,
        choices=STORAGE_STATE_CHOICES,
        default=LEGACY_PUBLIC,
        db_index=True,
    )
    # Only the one-time data migration may mark a pre-phase-2 reference as a
    # genuine legacy source. New writes with a raw URL must never be delivered.
    legacy_source_verified = models.BooleanField(default=False)
    private_migrated_at = models.DateTimeField(null=True, blank=True)
    legacy_deleted_at = models.DateTimeField(null=True, blank=True)
    
    # Photo metadata
    is_main = models.BooleanField(
        default=False,
        verbose_name=_('Is main photo')
    )
    caption = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('Caption')
    )
    order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_('Display order')
    )
    
    # Moderation
    is_approved = models.BooleanField(
        default=True,
        verbose_name=_('Is approved')
    )
    moderation_notes = models.TextField(
        blank=True,
        verbose_name=_('Moderation notes')
    )
    
    # Timestamps
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Uploaded at')
    )
    
    class Meta:
        verbose_name = _('Profile Photo')
        verbose_name_plural = _('Profile Photos')
        db_table = 'profile_photos'
        ordering = ['order', '-uploaded_at']
        constraints = [
            models.UniqueConstraint(
                fields=['profile'],
                condition=models.Q(is_main=True),
                name='unique_main_photo_per_profile'
            )
        ]
    
    def __str__(self):
        return f"Photo for {self.profile.user.display_name}"
    
    def save(self, *args, **kwargs):
        """Ensure only one main photo per profile."""
        if self.is_main:
            # Set all other photos as non-main
            ProfilePhoto.objects.filter(
                profile=self.profile,
                is_main=True
            ).exclude(id=self.id).update(is_main=False)
        
        super().save(*args, **kwargs)


class Verification(models.Model):
    """
    Model for user verification process.
    """
    
    # Status choices
    NOT_STARTED = 'not_started'
    PENDING_ID = 'pending_id'
    PENDING_MEDICAL = 'pending_medical'
    PENDING_SELFIE = 'pending_selfie'
    PENDING_REVIEW = 'pending_review'
    VERIFIED = 'verified'
    REJECTED = 'rejected'
    EXPIRED = 'expired'
    
    STATUS_CHOICES = [
        (NOT_STARTED, _('Not started')),
        (PENDING_ID, _('Pending ID verification')),
        (PENDING_MEDICAL, _('Pending medical verification')),
        (PENDING_SELFIE, _('Pending selfie verification')),
        (PENDING_REVIEW, _('Pending review')),
        (VERIFIED, _('Verified')),
        (REJECTED, _('Rejected')),
        (EXPIRED, _('Expired')),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='verification'
    )
    
    # Document paths (encrypted in Firebase Storage)
    id_document_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('ID document path')
    )
    medical_document_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Medical document path')
    )
    selfie_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Selfie path')
    )
    
    # Verification code for selfie
    verification_code = models.CharField(
        max_length=10,
        blank=True,
        verbose_name=_('Verification code')
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=NOT_STARTED,
        verbose_name=_('Status')
    )
    
    # Review information
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verifications_reviewed',
        verbose_name=_('Reviewed by')
    )
    rejection_reason = models.TextField(
        blank=True,
        verbose_name=_('Rejection reason')
    )
    
    # Timestamps
    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Submitted at')
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Reviewed at')
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Expires at')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated at')
    )
    
    class Meta:
        verbose_name = _('Verification')
        verbose_name_plural = _('Verifications')
        db_table = 'verifications'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Verification for {self.user.display_name} - {self.status}"
    
    def is_expired(self):
        """Check if verification has expired."""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


class KycAttempt(models.Model):
    """Authoritative and privacy-minimised KYC attempt state."""

    NOT_STARTED = 'not_started'
    PENDING_ID = 'pending_id'
    PENDING_MEDICAL = 'pending_medical'
    PENDING_SELFIE = 'pending_selfie'
    PENDING_REVIEW = 'pending_review'
    VERIFIED = 'verified'
    REJECTED = 'rejected'
    EXPIRED = 'expired'

    STATUS_CHOICES = [
        (NOT_STARTED, _('Not started')),
        (PENDING_ID, _('Pending identity document')),
        (PENDING_MEDICAL, _('Pending medical document')),
        (PENDING_SELFIE, _('Pending selfie')),
        (PENDING_REVIEW, _('Pending review')),
        (VERIFIED, _('Verified')),
        (REJECTED, _('Rejected')),
        (EXPIRED, _('Expired')),
    ]

    ORIGIN_USER_START = 'user_start'
    ORIGIN_LEGACY_PROJECTION = 'legacy_projection'
    ORIGIN_CHOICES = [
        (ORIGIN_USER_START, _('User start')),
        (ORIGIN_LEGACY_PROJECTION, _('Legacy projection')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='kyc_attempts',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=NOT_STARTED,
        db_index=True,
    )
    origin = models.CharField(
        max_length=24,
        choices=ORIGIN_CHOICES,
        default=ORIGIN_USER_START,
    )
    is_open = models.BooleanField(
        default=True,
        help_text=_('Only one open KYC attempt is allowed per user.'),
    )
    consent_version = models.CharField(max_length=80, blank=True)
    rejection_reason_code = models.CharField(max_length=80, blank=True)

    # The challenge is verifiable without persisting its plain-text value.
    challenge_hash = models.CharField(max_length=256, blank=True)
    challenge_nonce = models.CharField(max_length=64, blank=True)
    challenge_idempotency_key = models.CharField(max_length=128, blank=True)
    challenge_expires_at = models.DateTimeField(null=True, blank=True)
    challenge_used_at = models.DateTimeField(null=True, blank=True)

    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyc_attempts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'expires_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_open=True),
                name='profiles_one_open_kyc_attempt_per_user',
            ),
        ]

    def __str__(self):
        return f"KYC attempt {self.id} ({self.status})"


class KycDocument(models.Model):
    """Metadata for a KYC object, never the document itself or a public URL."""

    IDENTITY_DOCUMENT = 'identity_document'
    MEDICAL_DOCUMENT = 'medical_document'
    SELFIE_WITH_CODE = 'selfie_with_code'
    TYPE_CHOICES = [
        (IDENTITY_DOCUMENT, _('Identity document')),
        (MEDICAL_DOCUMENT, _('Medical document')),
        (SELFIE_WITH_CODE, _('Selfie with challenge')),
    ]

    ISSUED = 'issued'
    UPLOADED = 'uploaded'
    SCANNING = 'scanning'
    QUARANTINED = 'quarantined'
    ACCEPTED = 'accepted'
    PURGED = 'purged'
    SCAN_STATUS_CHOICES = [
        (ISSUED, _('Issued')),
        (UPLOADED, _('Uploaded')),
        (SCANNING, _('Scanning')),
        (QUARANTINED, _('Quarantined')),
        (ACCEPTED, _('Accepted')),
        (PURGED, _('Purged')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(
        KycAttempt,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    document_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    opaque_storage_key = models.CharField(max_length=255, unique=True)
    sha256 = models.CharField(max_length=64, blank=True)
    size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    detected_mime_type = models.CharField(max_length=100, blank=True)
    scan_status = models.CharField(
        max_length=16,
        choices=SCAN_STATUS_CHOICES,
        default=ISSUED,
        db_index=True,
    )
    scan_attempts = models.PositiveSmallIntegerField(default=0)
    scan_started_at = models.DateTimeField(null=True, blank=True)
    scan_completed_at = models.DateTimeField(null=True, blank=True)
    quarantine_reason_code = models.CharField(max_length=80, blank=True)
    purge_after = models.DateTimeField(null=True, blank=True)
    next_purge_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    purge_attempts = models.PositiveSmallIntegerField(default=0)
    purged_at = models.DateTimeField(null=True, blank=True)
    deletion_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyc_documents'
        constraints = [
            models.UniqueConstraint(
                fields=['attempt', 'document_type'],
                name='profiles_one_kyc_document_type_per_attempt',
            ),
        ]
        indexes = [
            models.Index(fields=['attempt', 'scan_status']),
            models.Index(fields=['purge_after']),
        ]

    def __str__(self):
        return f"KYC document {self.document_type} for {self.attempt_id}"


class KycUploadIntent(models.Model):
    """Single-use declaration for a future constrained upload."""

    ISSUED = 'issued'
    CONSUMED = 'consumed'
    EXPIRED = 'expired'
    STATUS_CHOICES = [
        (ISSUED, _('Issued')),
        (CONSUMED, _('Consumed')),
        (EXPIRED, _('Expired')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(
        KycAttempt,
        on_delete=models.CASCADE,
        related_name='upload_intents',
    )
    document = models.ForeignKey(
        KycDocument,
        on_delete=models.SET_NULL,
        related_name='upload_intents',
        null=True,
        blank=True,
    )
    document_type = models.CharField(
        max_length=32,
        choices=KycDocument.TYPE_CHOICES,
    )
    declared_mime_type = models.CharField(max_length=100)
    declared_size_bytes = models.PositiveBigIntegerField()
    declared_sha256 = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=128)
    opaque_object_key = models.CharField(max_length=255, unique=True)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=ISSUED,
        db_index=True,
    )
    expires_at = models.DateTimeField(db_index=True)
    upload_confirmed_at = models.DateTimeField(null=True, blank=True)
    scan_enqueued_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kyc_upload_intents'
        constraints = [
            models.UniqueConstraint(
                fields=['attempt', 'idempotency_key'],
                name='profiles_kyc_upload_intent_idempotency',
            ),
        ]
        indexes = [
            models.Index(fields=['attempt', 'document_type']),
            models.Index(fields=['status', 'expires_at']),
        ]

    def __str__(self):
        return f"KYC upload intent {self.id}"


class KycAuditEvent(models.Model):
    """Append-only KYC audit metadata without documents or health details."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(
        KycAttempt,
        on_delete=models.CASCADE,
        related_name='audit_events',
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kyc_audit_events',
    )
    actor_role = models.CharField(max_length=32, blank=True)
    event_type = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'kyc_audit_events'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['attempt', 'created_at']),
            models.Index(fields=['event_type', 'created_at']),
        ]

    def __str__(self):
        return f"KYC audit {self.event_type} for {self.attempt_id}"


class DataExportRequest(models.Model):
    """
    Trace une demande d'export de données personnelles (RGPD / droit d'accès).
    """

    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_READY = 'ready'
    STATUS_EXPIRED = 'expired'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, _('Pending')),
        (STATUS_PROCESSING, _('Processing')),
        (STATUS_READY, _('Ready')),
        (STATUS_EXPIRED, _('Expired')),
        (STATUS_FAILED, _('Failed')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='data_export_requests',
        verbose_name=_('User'),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name=_('Status'),
    )
    requested_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Requested at'),
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Completed at'),
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Download link expires at'),
    )
    download_url = models.URLField(
        max_length=1000,
        blank=True,
        verbose_name=_('Signed download URL'),
    )
    error_log = models.TextField(
        blank=True,
        verbose_name=_('Error log'),
    )

    class Meta:
        db_table = 'data_export_requests'
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"Export request {self.id} — {self.status}"


class AccountDeletionRequest(models.Model):
    """
    Trace une demande de suppression de compte avec confirmation par email
    et période de grâce réversible.
    """

    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, _('Pending')),
        (STATUS_CONFIRMED, _('Confirmed')),
        (STATUS_PROCESSING, _('Processing')),
        (STATUS_COMPLETED, _('Completed')),
        (STATUS_CANCELLED, _('Cancelled')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='account_deletion_requests',
        verbose_name=_('User'),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name=_('Status'),
    )
    requested_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Requested at'),
    )
    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Confirmed at'),
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Completed at'),
    )
    grace_period_hours = models.PositiveIntegerField(
        default=72,
        verbose_name=_('Grace period (hours)'),
    )
    confirmation_token = models.CharField(
        max_length=64,
        blank=True,
        verbose_name=_('Confirmation token'),
    )
    cancellation_token = models.CharField(
        max_length=64,
        blank=True,
        verbose_name=_('Cancellation token'),
    )
    reason = models.TextField(
        blank=True,
        verbose_name=_('Reason'),
    )

    class Meta:
        db_table = 'account_deletion_requests'
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['confirmation_token']),
            models.Index(fields=['cancellation_token']),
        ]

    def __str__(self):
        return f"Deletion request {self.id} — {self.status}"
