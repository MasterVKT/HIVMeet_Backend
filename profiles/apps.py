from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ProfilesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'profiles'
    verbose_name = _('Profiles')

    def ready(self):
        import profiles.signals  # noqa
        import profiles.checks  # noqa
        # Import tasks so Celery autodiscovers them even if no other module
        # references them explicitly.
        import profiles.tasks  # noqa