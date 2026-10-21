from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class BackofficeConfig(AppConfig):
    name = 'backoffice'
    verbose_name = _('HIVMeet back-office')
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from . import checks  # noqa: F401  (enregistre les contrôles système)
