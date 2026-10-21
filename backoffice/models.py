import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class AppendOnlyError(Exception):
    """Une entrée d'audit ne peut être ni modifiée ni supprimée."""


class StaffAuditLogQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise AppendOnlyError('StaffAuditLog is append-only.')

    def delete(self):
        raise AppendOnlyError('StaffAuditLog is append-only.')

    def bulk_update(self, objs, fields, batch_size=None):
        raise AppendOnlyError('StaffAuditLog is append-only.')


class StaffAuditLog(models.Model):
    """Journal d'audit des actions du staff (ajout seul).

    ``actor`` passe à NULL si le compte est supprimé; ``actor_ref`` conserve
    l'identifiant. ``target_id`` est une chaîne: il survit à la suppression de la
    cible. Écrire via ``backoffice.audit.record`` uniquement (liste blanche
    d'actions et de métadonnées).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name=_('Actor'),
    )
    actor_ref = models.CharField(max_length=64, blank=True, verbose_name=_('Actor reference'))
    action = models.CharField(max_length=64, verbose_name=_('Action'))
    target_type = models.CharField(max_length=32, blank=True, verbose_name=_('Target type'))
    target_id = models.CharField(max_length=64, blank=True, verbose_name=_('Target identifier'))
    reason = models.TextField(blank=True, verbose_name=_('Reason'))
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_('Metadata'))
    ip_hash = models.CharField(max_length=64, blank=True, verbose_name=_('IP hash'))
    created_at = models.DateTimeField(default=timezone.now, editable=False, verbose_name=_('Created at'))

    objects = StaffAuditLogQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Staff audit entry')
        verbose_name_plural = _('Staff audit entries')
        indexes = [
            models.Index(fields=['target_type', 'target_id', 'created_at'], name='bo_audit_target_idx'),
            models.Index(fields=['actor', 'created_at'], name='bo_audit_actor_idx'),
            models.Index(fields=['action', 'created_at'], name='bo_audit_action_idx'),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise AppendOnlyError('StaffAuditLog is append-only.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AppendOnlyError('StaffAuditLog is append-only.')

    def __str__(self):
        return f'{self.action} {self.target_type}:{self.target_id}'
