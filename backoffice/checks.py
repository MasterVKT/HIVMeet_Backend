"""Contrôles système du back-office.

- ``backoffice.E010`` (toujours): ``backoffice`` ne doit tourner qu'avec ses
  propres réglages. Si quelqu'un l'ajoute aux ``INSTALLED_APPS`` de l'API, ce
  contrôle fait échouer ``manage.py check`` avant tout impact.
- Contrôles ``--deploy``: cache partagé (verrouillage), cookies sécurisés,
  clé secrète non par défaut.
"""

from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security)
def check_isolated_settings(app_configs, **kwargs):
    if settings.ROOT_URLCONF != 'backoffice.conf.urls':
        return [Error(
            'backoffice is loaded with a foreign URLconf.',
            hint='Run it only with --settings=backoffice.conf.settings; never add '
                 '"backoffice" to the API settings.',
            id='backoffice.E010',
        )]
    return []


@register(Tags.security, deploy=True)
def check_production_hardening(app_configs, **kwargs):
    errors = []
    if settings.DEBUG:
        return errors
    backend = settings.CACHES['default']['BACKEND'].lower()
    if 'locmem' in backend or 'dummy' in backend:
        errors.append(Error(
            'The default cache is not shared between processes.',
            hint='Lockout counters need Redis (USE_REDIS_CACHE=True) in production.',
            id='backoffice.E001',
        ))
    if not settings.SESSION_COOKIE_SECURE or not settings.CSRF_COOKIE_SECURE:
        errors.append(Error(
            'Session/CSRF cookies must be Secure outside DEBUG.', id='backoffice.E002',
        ))
    if settings.SECRET_KEY.startswith('django-insecure'):
        errors.append(Error('SECRET_KEY is the insecure default.', id='backoffice.E003'))
    return errors
