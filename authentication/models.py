"""
Authentication models for HIVMeet.
"""
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import uuid


class UserManager(BaseUserManager):
    """
    Custom user manager for HIVMeet User model.
    """
    
    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save a regular user with the given email and password.
        """
        if not email:
            raise ValueError(_('The Email field must be set'))
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and save a superuser with the given email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('email_verified', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model for HIVMeet.
    Uses email as the username field.
    """
    
    # Unique identifier
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_('ID')
    )
    
    # Firebase UID - links to Firebase Authentication
    firebase_uid = models.CharField(
        max_length=128,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_('Firebase UID'),
        help_text=_('Firebase Authentication UID')
    )
    
    # Authentication fields
    email = models.EmailField(
        unique=True,
        verbose_name=_('Email address')
    )
    email_verified = models.BooleanField(
        default=False,
        verbose_name=_('Email verified')
    )
    
    # User information
    display_name = models.CharField(
        max_length=30,
        verbose_name=_('Display name'),
        help_text=_('Public display name (3-30 characters)')
    )
    birth_date = models.DateField(
        verbose_name=_('Birth date'),
        help_text=_('Must be 18+ years old')
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_('Phone number'),
        help_text=_('International format')
    )
    
    # Account status
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active'),
        help_text=_('Designates whether this user should be treated as active.')
    )
    is_staff = models.BooleanField(
        default=False,
        verbose_name=_('Staff status'),
        help_text=_('Designates whether the user can log into the admin site.')
    )
    is_verified = models.BooleanField(
        default=False,
        verbose_name=_('Verified'),
        help_text=_('Identity and medical status verified')
    )
    verification_status = models.CharField(
        max_length=20,
        choices=[
            ('not_started', _('Not started')),
            ('pending', _('Pending')),
            ('verified', _('Verified')),
            ('rejected', _('Rejected')),
            ('expired', _('Expired'))
        ],
        default='not_started',
        verbose_name=_('Verification status')
    )
    
    # Premium status
    is_premium = models.BooleanField(
        default=False,
        verbose_name=_('Premium status')
    )
    premium_until = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Premium until'),
        help_text=_('Premium subscription expiry date')
    )
    
    # Timestamps
    date_joined = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Date joined')
    )
    last_login = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Last login')
    )
    last_active = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Last active')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated at')
    )
    
    # Blocking functionality
    blocked_users = models.ManyToManyField(
        'self',
        symmetrical=False,
        related_name='blocked_by',
        blank=True,
        verbose_name=_('Blocked users')
    )
    
    # User role
    role = models.CharField(
        max_length=20,
        choices=[
            ('user', _('User')),
            ('moderator', _('Moderator')),
            ('admin', _('Admin'))
        ],
        default='user',
        verbose_name=_('Role')
    )
    
    # Notification tokens
    fcm_tokens = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('FCM tokens'),
        help_text=_('Firebase Cloud Messaging tokens for push notifications')
    )
    
    # Settings
    notification_settings = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Notification settings')
    )
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['display_name', 'birth_date']
    
    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        db_table = 'users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['firebase_uid']),
            models.Index(fields=['is_verified', 'last_active']),
            models.Index(fields=['is_premium']),
            models.Index(fields=['verification_status']),
        ]
    
    def __str__(self):
        return f"{self.display_name} ({self.email})"
    
    @property
    def age(self):
        """Calculate user's age."""
        if self.birth_date:
            today = timezone.now().date()
            return today.year - self.birth_date.year - (
                (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
            )
        return None
    
    def is_adult(self):
        """Check if user is 18+."""
        return self.age >= 18 if self.age else False
    
    def update_last_active(self):
        """Update last active timestamp."""
        self.last_active = timezone.now()
        self.save(update_fields=['last_active'])
    
    def add_fcm_token(self, token, device_id=None, platform=None):
        """Add or update FCM token for push notifications."""
        # A device's FCM registration token is unique per app install, not
        # per account: if another user was previously logged in on this
        # device/emulator and never had the token cleanly removed (crash,
        # uninstall, or a logout whose cleanup call failed), that account
        # would otherwise keep receiving this device's pushes forever.
        # Detach the token from every other account before attaching it here.
        self.detach_fcm_token_from_others(token)

        # Remove existing token if it exists
        self.fcm_tokens = [t for t in self.fcm_tokens if t.get('token') != token]

        # Add new token
        token_data = {
            'token': token,
            'added_at': timezone.now().isoformat(),
        }
        if device_id:
            token_data['device_id'] = device_id
        if platform:
            token_data['platform'] = platform

        self.fcm_tokens.append(token_data)
        self.save(update_fields=['fcm_tokens'])

    def detach_fcm_token_from_others(self, token):
        """Remove `token` from every other user's `fcm_tokens`.

        Called before attaching the token to `self` so a given FCM
        registration token is never listed on more than one account at a
        time (otherwise both accounts receive each other's pushes).
        """
        others = type(self).objects.exclude(pk=self.pk).filter(
            fcm_tokens__contains=[{'token': token}]
        )
        for other in others:
            other.fcm_tokens = [
                t for t in other.fcm_tokens if t.get('token') != token
            ]
            other.save(update_fields=['fcm_tokens'])
    
    def remove_fcm_token(self, token):
        """Remove FCM token."""
        self.fcm_tokens = [t for t in self.fcm_tokens if t.get('token') != token]
        self.save(update_fields=['fcm_tokens'])
    
    def clear_fcm_tokens(self):
        """Clear all FCM tokens."""
        self.fcm_tokens = []
        self.save(update_fields=['fcm_tokens'])
    
    @property
    def premium_features(self):
        """Get available premium features."""
        from subscriptions.utils import get_premium_limits
        return get_premium_limits(self)
    
    @property
    def can_send_super_like(self):
        """Check if user can send super likes."""
        from subscriptions.utils import check_feature_availability
        return check_feature_availability(self, 'super_like')['available']
    
    @property
    def can_use_boost(self):
        """Check if user can use profile boost."""
        from subscriptions.utils import check_feature_availability
        return check_feature_availability(self, 'boost')['available']
    
    @property
    def can_send_media_messages(self):
        """Check if user can send media messages."""
        from subscriptions.utils import check_feature_availability
        return check_feature_availability(self, 'media_messaging')['available']
    
    @property
    def can_make_calls(self):
        """Check if user can make calls."""
        from subscriptions.utils import check_feature_availability
        return check_feature_availability(self, 'calls')['available']
    
    @property
    def can_see_who_liked(self):
        """Check if user can see who liked them."""
        from subscriptions.utils import is_premium_user
        return is_premium_user(self)


class Report(models.Model):
    """
    Signalement d'un utilisateur par un autre.
    Tracke le statut du signalement et permet de notifier le reporter
    quand une décision est prise.
    """

    STATUS_PENDING = 'pending'
    STATUS_UNDER_REVIEW = 'under_review'
    STATUS_RESOLVED = 'resolved'
    STATUS_DISMISSED = 'dismissed'

    STATUS_CHOICES = [
        (STATUS_PENDING, _('En attente')),
        (STATUS_UNDER_REVIEW, _('En cours de traitement')),
        (STATUS_RESOLVED, _('Résolu')),
        (STATUS_DISMISSED, _('Rejeté')),
    ]

    REASON_INAPPROPRIATE = 'inappropriate'
    REASON_HARASSMENT = 'harassment'
    REASON_SCAM = 'scam'
    REASON_OTHER = 'other'

    REASON_CHOICES = [
        (REASON_INAPPROPRIATE, _('Contenu inapproprié')),
        (REASON_HARASSMENT, _('Harcèlement')),
        (REASON_SCAM, _('Arnaque')),
        (REASON_OTHER, _('Autre')),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_('ID'),
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reports_made',
        verbose_name=_('Signaleur'),
    )
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reports_received',
        verbose_name=_('Utilisateur signalé'),
    )
    reason = models.CharField(
        max_length=20,
        choices=REASON_CHOICES,
        verbose_name=_('Motif'),
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description'),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name=_('Statut'),
    )
    resolution_notes = models.TextField(
        blank=True,
        verbose_name=_('Notes de résolution'),
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports_resolved',
        verbose_name=_('Résolu par'),
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Résolu le'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Créé le'),
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['reporter', '-created_at']),
            models.Index(fields=['reported_user', '-created_at']),
            models.Index(fields=['status']),
        ]
        verbose_name = _('Signalement')
        verbose_name_plural = _('Signalements')

    def __str__(self):
        return f"Report {self.id} — {self.reporter} → {self.reported_user} ({self.status})"