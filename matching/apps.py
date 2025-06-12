from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class MatchingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'matching'
    verbose_name = _('Matching')

    def ready(self):
        import matching.signals  # noqa