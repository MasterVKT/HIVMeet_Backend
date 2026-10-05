"""
Notification model — persisted server-side notifications.
Créé à chaque like, match, nouveau message pour alimenter GET /api/v1/notifications/.
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    TYPES = [
        ('new_match', _('Nouveau match')),
        ('new_message', _('Nouveau message')),
        ('message_read', _('Message read')),
        ('like', _('Like reçu')),
        ('super_like', _('Super like reçu')),
        ('subscription_expiring', _('Abonnement expirant')),
        ('report_resolved', _('Signalement résolu')),
        ('system', _('Système')),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_('ID'),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('Utilisateur'),
    )
    type = models.CharField(
        max_length=30,
        choices=TYPES,
        verbose_name=_('Type'),
    )
    title = models.CharField(max_length=255, verbose_name=_('Titre'))
    body = models.TextField(blank=True, verbose_name=_('Corps'))
    # Contient: match_id, conversation_id, from_user_id, notification_id, etc.
    data = models.JSONField(default=dict, verbose_name=_('Données'))
    is_read = models.BooleanField(default=False, verbose_name=_('Lu'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Créé le'))

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at']),
        ]
        verbose_name = _('Notification')
        verbose_name_plural = _('Notifications')

    def __str__(self) -> str:
        return f"[{self.type}] {self.user_id} — {self.title}"
