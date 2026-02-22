"""
Profile models for HIVMeet.
"""
from django.db import models
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
    
    # Gender choices
    MALE = 'male'
    FEMALE = 'female'
    NON_BINARY = 'non_binary'
    TRANS_MALE = 'trans_male'
    TRANS_FEMALE = 'trans_female'
    OTHER = 'other'
    PREFER_NOT_TO_SAY = 'prefer_not_to_say'
    
    GENDER_CHOICES = [
        (MALE, _('Male')),
        (FEMALE, _('Female')),
        (NON_BINARY, _('Non-binary')),
        (TRANS_MALE, _('Trans male')),
        (TRANS_FEMALE, _('Trans female')),
        (OTHER, _('Other')),
        (PREFER_NOT_TO_SAY, _('Prefer not to say')),
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
        default=PREFER_NOT_TO_SAY,
        verbose_name=_('Gender')
    )
    
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
    hide_exact_location = models.BooleanField(
        default=False,
        verbose_name=_('Hide exact location')
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
        if self.genders_sought:
            valid_genders = dict(self.GENDER_CHOICES).keys()
            invalid = [g for g in self.genders_sought if g not in valid_genders]
            if invalid:
                raise ValidationError({
                    'genders_sought': _('Invalid genders: %(invalid)s') % {'invalid': invalid}
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
    
    # Photo URLs (stored in Firebase Storage)
    photo_url = models.URLField(
        max_length=500,
        verbose_name=_('Photo URL')
    )
    thumbnail_url = models.URLField(
        max_length=500,
        verbose_name=_('Thumbnail URL')
    )
    
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