from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ResourcesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'resources'
    verbose_name = _('Resources')

    def ready(self):
        import resources.signals  # noqa