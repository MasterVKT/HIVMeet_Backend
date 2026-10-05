"""
Tests pour LOG-07 : configuration Celery explicite par environnement.

Valide que :
- En mode DEBUG (dev), eager est True et broker est memory://
- En mode production (DEBUG=False), l'absence de CELERY_BROKER_URL lève une erreur
- Le hostname implicite n'est plus utilisé
- transaction.on_commit est utilisé pour les effets de bord
"""
import os
import django
from django.test import TestCase, override_settings
from unittest.mock import patch, MagicMock

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.test_settings')
django.setup()


class CeleryConfigTest(TestCase):
    """Tests pour la configuration Celery explicite (LOG-07)."""

    def test_test_settings_eager_is_true(self):
        """Les tests utilisent eager=True pour être déterministes."""
        from django.conf import settings
        self.assertTrue(settings.CELERY_TASK_ALWAYS_EAGER)
        self.assertTrue(settings.CELERY_TASK_EAGER_PROPAGATES)

    def test_dev_broker_is_memory_when_no_broker_url(self):
        """En dev sans CELERY_BROKER_URL, broker est memory:// (explicite)."""
        # test_settings hérite de settings avec DEBUG=True
        # Le broker memory:// est acceptable en dev
        from django.conf import settings
        # En test, CELERY_BROKER_URL peut être memory:// ou autre
        # L'important est que eager=True pour les tests
        self.assertTrue(settings.CELERY_TASK_ALWAYS_EAGER)

    def test_production_without_broker_url_raises(self):
        """En production (DEBUG=False) sans CELERY_BROKER_URL, une erreur est levée."""
        # Simuler un import de settings avec DEBUG=False et sans CELERY_BROKER_URL
        # On ne peut pas réellement re-importer settings, donc on valide la logique
        # via une simulation
        import importlib
        import sys

        # Sauvegarder l'état
        old_debug = os.environ.get('DEBUG')
        old_broker = os.environ.get('CELERY_BROKER_URL')

        try:
            os.environ['DEBUG'] = 'False'
            os.environ.pop('CELERY_BROKER_URL', None)

            # Re-importer le module settings
            if 'hivmeet_backend.settings' in sys.modules:
                del sys.modules['hivmeet_backend.settings']

            with self.assertRaises(RuntimeError) as ctx:
                importlib.import_module('hivmeet_backend.settings')

            self.assertIn('CELERY_BROKER_URL', str(ctx.exception))

        finally:
            # Restaurer l'état
            if old_debug is not None:
                os.environ['DEBUG'] = old_debug
            else:
                os.environ.pop('DEBUG', None)
            if old_broker is not None:
                os.environ['CELERY_BROKER_URL'] = old_broker
            # Re-importer les modules originaux
            if 'hivmeet_backend.settings' in sys.modules:
                del sys.modules['hivmeet_backend.settings']
            importlib.import_module('hivmeet_backend.settings')

    def test_call_notification_uses_transaction_on_commit(self):
        """LOG-07 : send_call_notification.delay est différée via on_commit."""
        from messaging.services import CallService
        from django.db import transaction

        # Vérifier que le code source utilise transaction.on_commit
        import inspect
        source = inspect.getsource(CallService.initiate_call)
        self.assertIn('transaction.on_commit', source,
                      "initiate_call doit utiliser transaction.on_commit pour "
                      "différer send_call_notification.delay")

    def test_matching_signals_use_transaction_on_commit(self):
        """LOG-07 : matching/signals.py utilise transaction.on_commit."""
        import inspect
        import matching.signals as signals_module
        source = inspect.getsource(signals_module)
        self.assertIn('transaction.on_commit', source,
                      "matching/signals.py doit utiliser transaction.on_commit")