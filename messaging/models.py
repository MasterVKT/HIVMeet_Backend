"""
Messaging models for HIVMeet.
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.validators import MaxLengthValidator
import uuid

from matching.models import Match

User = get_user_model()


class Message(models.Model):
    """
    Model for messages between users.
    """
    
    # Message types
    TEXT = 'text'
    IMAGE = 'image'
    VIDEO = 'video'
    AUDIO = 'audio'
    CALL_LOG = 'call_log'
    
    MESSAGE_TYPE_CHOICES = [
        (TEXT, _('Text')),
        (IMAGE, _('Image')),
        (VIDEO, _('Video')),
        (AUDIO, _('Audio')),
        (CALL_LOG, _('Call log')),
    ]
    
    # Message statuses
    SENDING = 'sending'
    SENT = 'sent'
    DELIVERED = 'delivered'
    READ = 'read'
    FAILED = 'failed'
    
    STATUS_CHOICES = [
        (SENDING, _('Sending')),
        (SENT, _('Sent')),
        (DELIVERED, _('Delivered')),
        (READ, _('Read')),
        (FAILED, _('Failed')),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # Client-generated ID for deduplication
    client_message_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Client message ID')
    )
    
    # Match this message belongs to
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name=_('Match')
    )
    
    # Sender
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='messages_sent',
        verbose_name=_('Sender')
    )
    
    # Message content
    message_type = models.CharField(
        max_length=10,
        choices=MESSAGE_TYPE_CHOICES,
        default=TEXT,
        verbose_name=_('Message type')
    )
    
    content = models.TextField(
        max_length=1000,
        blank=True,
        validators=[MaxLengthValidator(1000)],
        verbose_name=_('Content')
    )
    
    # Media fields (for premium users)
    media_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name=_('Media URL')
    )
    
    media_thumbnail_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name=_('Media thumbnail URL')
    )
    
    media_file_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Media file path')
    )
    
    # Status tracking
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=SENT,
        verbose_name=_('Status')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at')
    )
    
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Delivered at')
    )
    
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Read at')
    )
    
    # Soft delete
    is_deleted_by_sender = models.BooleanField(
        default=False,
        verbose_name=_('Deleted by sender')
    )
    
    is_deleted_by_recipient = models.BooleanField(
        default=False,
        verbose_name=_('Deleted by recipient')
    )
    
    class Meta:
        verbose_name = _('Message')
        verbose_name_plural = _('Messages')
        db_table = 'messages'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['match', '-created_at']),
            models.Index(fields=['sender', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['client_message_id']),
        ]
    
    def __str__(self):
        return f"Message from {self.sender.display_name} in match {self.match.id}"
    
    def get_recipient(self):
        """Get the recipient of this message."""
        return self.match.get_other_user(self.sender)
    
    def mark_as_delivered(self):
        """Mark message as delivered."""
        if self.status in [self.SENDING, self.SENT]:
            self.status = self.DELIVERED
            self.delivered_at = timezone.now()
            self.save(update_fields=['status', 'delivered_at'])
    
    def mark_as_read(self):
        """Mark message as read."""
        if self.status != self.READ:
            self.status = self.READ
            self.read_at = timezone.now()
            self.save(update_fields=['status', 'read_at'])
            
            # Update unread count in match
            recipient = self.get_recipient()
            self.match.reset_unread(recipient)
    
    def delete_for_user(self, user):
        """Soft delete message for a specific user."""
        if user == self.sender:
            self.is_deleted_by_sender = True
        else:
            self.is_deleted_by_recipient = True
        self.save(update_fields=['is_deleted_by_sender', 'is_deleted_by_recipient'])


class MessageReaction(models.Model):
    """
    Model for message reactions (future feature).
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='reactions',
        verbose_name=_('Message')
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='message_reactions',
        verbose_name=_('User')
    )
    
    emoji = models.CharField(
        max_length=10,
        verbose_name=_('Emoji')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at')
    )
    
    class Meta:
        verbose_name = _('Message Reaction')
        verbose_name_plural = _('Message Reactions')
        db_table = 'message_reactions'
        unique_together = ['message', 'user']


class Call(models.Model):
    """
    Model for audio/video calls.
    """
    
    # Call types
    AUDIO = 'audio'
    VIDEO = 'video'
    
    CALL_TYPE_CHOICES = [
        (AUDIO, _('Audio')),
        (VIDEO, _('Video')),
    ]
    
    # Call statuses
    INITIATED = 'initiated'
    RINGING = 'ringing'
    ANSWERED = 'answered'
    ENDED = 'ended'
    DECLINED = 'declined'
    MISSED = 'missed'
    FAILED = 'failed'
    
    STATUS_CHOICES = [
        (INITIATED, _('Initiated')),
        (RINGING, _('Ringing')),
        (ANSWERED, _('Answered')),
        (ENDED, _('Ended')),
        (DECLINED, _('Declined')),
        (MISSED, _('Missed')),
        (FAILED, _('Failed')),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # Match this call belongs to
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name='calls',
        verbose_name=_('Match')
    )
    
    # Call participants
    caller = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='calls_initiated',
        verbose_name=_('Caller')
    )
    
    callee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='calls_received',
        verbose_name=_('Callee')
    )
    
    # Call details
    call_type = models.CharField(
        max_length=10,
        choices=CALL_TYPE_CHOICES,
        verbose_name=_('Call type')
    )
    
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=INITIATED,
        verbose_name=_('Status')
    )
    
    # WebRTC signaling data
    offer_sdp = models.TextField(
        blank=True,
        verbose_name=_('Offer SDP')
    )
    
    answer_sdp = models.TextField(
        blank=True,
        verbose_name=_('Answer SDP')
    )
    
    ice_candidates = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('ICE candidates')
    )
    
    # Call timing
    initiated_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Initiated at')
    )
    
    answered_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Answered at')
    )
    
    ended_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Ended at')
    )
    
    duration_seconds = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Duration (seconds)')
    )
    
    # End reason
    end_reason = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('End reason')
    )
    
    class Meta:
        verbose_name = _('Call')
        verbose_name_plural = _('Calls')
        db_table = 'calls'
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['match', '-initiated_at']),
            models.Index(fields=['caller', '-initiated_at']),
            models.Index(fields=['callee', '-initiated_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.call_type} call from {self.caller.display_name} to {self.callee.display_name}"
    
    def calculate_duration(self):
        """Calculate call duration."""
        if self.answered_at and self.ended_at:
            duration = (self.ended_at - self.answered_at).total_seconds()
            self.duration_seconds = int(duration)
            self.save(update_fields=['duration_seconds'])
    
    def end_call(self, reason):
        """End the call."""
        self.status = self.ENDED
        self.ended_at = timezone.now()
        self.end_reason = reason
        self.calculate_duration()
        self.save(update_fields=['status', 'ended_at', 'end_reason'])
        
        # Create call log message
        Message.objects.create(
            match=self.match,
            sender=self.caller,
            message_type=Message.CALL_LOG,
            content=self._get_call_log_message()
        )
    
    def _get_call_log_message(self):
        """Generate call log message."""
        call_type = _("Audio call") if self.call_type == self.AUDIO else _("Video call")
        
        if self.status == self.ENDED and self.duration_seconds > 0:
            minutes = self.duration_seconds // 60
            seconds = self.duration_seconds % 60
            return f"{call_type} - {minutes}:{seconds:02d}"
        elif self.status == self.DECLINED:
            return f"{call_type} - {_('Declined')}"
        elif self.status == self.MISSED:
            return f"{call_type} - {_('Missed')}"
        else:
            return f"{call_type} - {_('Failed')}"
    
    @classmethod
    def check_call_limit(cls, user):
        """Check if user has reached call duration limit (30 min for premium)."""
        if not user.is_premium:
            return False, _("Audio/video calls are a premium feature.")
        
        # Check today's total call duration
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_duration = cls.objects.filter(
            models.Q(caller=user) | models.Q(callee=user),
            initiated_at__gte=today_start,
            status=cls.ENDED
        ).aggregate(
            total=models.Sum('duration_seconds')
        )['total'] or 0
        
        # 30 minutes limit per day
        if today_duration >= 1800:
            return False, _("Daily call limit of 30 minutes reached.")
        
        return True, None


class TypingIndicator(models.Model):
    """
    Model for tracking typing indicators.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name='typing_indicators',
        verbose_name=_('Match')
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='typing_indicators',
        verbose_name=_('User')
    )
    
    is_typing = models.BooleanField(
        default=True,
        verbose_name=_('Is typing')
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated at')
    )
    
    class Meta:
        verbose_name = _('Typing Indicator')
        verbose_name_plural = _('Typing Indicators')
        db_table = 'typing_indicators'
        unique_together = ['match', 'user']