"""
Authentication models for HIVMeet.
"""
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
    
    def remove_fcm_token(self, token):
        """Remove FCM token."""
        self.fcm_tokens = [t for t in self.fcm_tokens if t.get('token') != token]
        self.save(update_fields=['fcm_tokens'])
    
    def clear_fcm_tokens(self):
        """Clear all FCM tokens."""
        self.fcm_tokens = []
        self.save(update_fields=['fcm_tokens'])