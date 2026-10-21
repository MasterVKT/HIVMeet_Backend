"""Réglages de test du back-office.

Dérivent de ``hivmeet_backend.test_settings`` (PostgreSQL local, migrations
désactivées, cache mémoire, hasher rapide) puis appliquent les réglages du
back-office. Usage :

    python manage.py test backoffice --settings=backoffice.conf.settings_test
"""

from hivmeet_backend.test_settings import *  # noqa: F401,F403

from backoffice.conf.overrides import apply as _apply

_apply(globals())

TEST_RUNNER = 'backoffice.testing.BackofficeDiscoverRunner'
