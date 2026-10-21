"""Audit append-only, métadonnées filtrées, groupes/migrations et isolation."""

import importlib
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import Group
from django.test import SimpleTestCase, override_settings

from backoffice import audit, checks, lockout, roles
from backoffice.models import AppendOnlyError, StaffAuditLog

from .helpers import BackofficeTestCase, make_staff


class AuditRecordTests(BackofficeTestCase):
    def test_unknown_action_is_refused(self):
        with self.assertRaises(ValueError):
            audit.record(action='not.in.the.allow.list')
        self.assertEqual(StaffAuditLog.objects.count(), 0)

    def test_metadata_is_filtered_by_allow_list_and_type(self):
        entry = audit.record(action='access.denied', metadata={
            'reason_code': 'x' * 500,
            'capability': 'dashboard',
            'count': 3,
            'status': True,
            'email': 'leak@example.test',        # clé interdite
            'path': {'nested': 'dict'},           # valeur non scalaire
            'identifier_hash': ['list'],          # valeur non scalaire
        })
        self.assertEqual(entry.metadata, {
            'reason_code': 'x' * 128, 'capability': 'dashboard', 'count': 3, 'status': True,
        })

    def test_ip_is_stored_hashed_only(self):
        class Req:
            META = {'REMOTE_ADDR': '203.0.113.9'}
        entry = audit.record(action='auth.locked', request=Req())
        self.assertRegex(entry.ip_hash, r'^[0-9a-f]{32}$')
        self.assertNotIn('203.0.113.9', entry.ip_hash)
        self.assertEqual(entry.ip_hash, lockout.ip_hash(Req()))

    def test_actor_snapshot_survives_account_deletion(self):
        user = make_staff(groups=[roles.GROUP_ADMIN])
        entry = audit.record(action='auth.logout', actor=user)
        pk = str(user.pk)
        user.delete()
        entry.refresh_from_db()
        self.assertIsNone(entry.actor)
        self.assertEqual(entry.actor_ref, pk)


class AppendOnlyTests(BackofficeTestCase):
    def setUp(self):
        super().setUp()
        self.entry = audit.record(action='auth.logout')

    def test_instance_cannot_be_updated(self):
        self.entry.reason = 'tampered'
        with self.assertRaises(AppendOnlyError):
            self.entry.save()

    def test_instance_cannot_be_deleted(self):
        with self.assertRaises(AppendOnlyError):
            self.entry.delete()

    def test_queryset_update_and_delete_are_refused(self):
        with self.assertRaises(AppendOnlyError):
            StaffAuditLog.objects.all().update(reason='tampered')
        with self.assertRaises(AppendOnlyError):
            StaffAuditLog.objects.all().delete()
        self.assertEqual(StaffAuditLog.objects.get().reason, '')


class LockoutPrimitiveTests(BackofficeTestCase):
    def test_identifier_hash_is_stable_normalised_and_not_reversible_by_eye(self):
        a = lockout.hash_identifier(' Staff@Example.test ')
        self.assertEqual(a, lockout.hash_identifier('staff@example.test'))
        self.assertNotIn('staff', a)
        self.assertEqual(len(a), 32)

    def test_counter_window_and_clear(self):
        self.assertEqual(lockout.register_failure('k', 'id', 60), 1)
        self.assertEqual(lockout.register_failure('k', 'id', 60), 2)
        self.assertTrue(lockout.is_locked('k', 'id', 2))
        self.assertFalse(lockout.is_locked('k', 'other', 2))
        lockout.clear('k', 'id')
        self.assertEqual(lockout.failures('k', 'id'), 0)

    def test_forwarded_header_is_ignored_unless_trusted(self):
        class Req:
            META = {'REMOTE_ADDR': '10.0.0.1', 'HTTP_X_FORWARDED_FOR': '1.1.1.1, 2.2.2.2'}
        self.assertEqual(lockout.client_ip(Req()), '10.0.0.1')
        with override_settings(BACKOFFICE_TRUST_X_FORWARDED_FOR=True):
            self.assertEqual(lockout.client_ip(Req()), '2.2.2.2')


class GroupTests(BackofficeTestCase):
    def test_ensure_groups_is_idempotent(self):
        roles.ensure_backoffice_groups()
        roles.ensure_backoffice_groups()
        for name in roles.OWNED_GROUPS:
            self.assertEqual(Group.objects.filter(name=name).count(), 1)

    def test_data_migration_creates_groups_and_is_idempotent(self):
        migration = importlib.import_module('backoffice.migrations.0002_backoffice_groups')
        migration.create_groups(apps, None)
        migration.create_groups(apps, None)
        self.assertEqual(
            set(Group.objects.filter(name__in=roles.OWNED_GROUPS).values_list('name', flat=True)),
            set(roles.OWNED_GROUPS),
        )
        migration.keep_groups(apps, None)  # le rollback ne supprime rien
        self.assertEqual(Group.objects.filter(name__in=roles.OWNED_GROUPS).count(), 3)

    def test_kyc_group_names_match_the_application(self):
        from profiles import kyc_review
        self.assertEqual(roles.GROUP_KYC_REVIEWER, kyc_review.KYC_REVIEWER_GROUP)
        self.assertEqual(roles.GROUP_KYC_SUPERVISOR, kyc_review.KYC_SUPERVISOR_GROUP)


class IndependenceTests(SimpleTestCase):
    """Le back-office ne doit jamais être chargé par l'application existante."""

    def test_api_settings_do_not_load_backoffice(self):
        from hivmeet_backend import settings as api_settings
        self.assertNotIn('backoffice', api_settings.INSTALLED_APPS)
        self.assertNotIn('backoffice', ' '.join(api_settings.MIDDLEWARE))
        self.assertEqual(api_settings.ROOT_URLCONF, 'hivmeet_backend.urls')

    def test_api_urlconf_does_not_mention_backoffice(self):
        # Lecture du source (sans import: l'URLconf de l'API charge toutes ses vues).
        package = Path(settings.BASE_DIR) / 'hivmeet_backend'
        for name in ('urls.py', 'api_urls.py', 'settings.py', 'asgi.py'):
            self.assertNotIn('backoffice', (package / name).read_text(encoding='utf-8'), name)

    def test_runtime_settings_drop_api_only_apps_and_use_own_urlconf(self):
        for removed in ('daphne', 'corsheaders', 'drf_yasg', 'debug_toolbar', 'django.contrib.admin'):
            self.assertNotIn(removed, settings.INSTALLED_APPS)
        self.assertIn('backoffice', settings.INSTALLED_APPS)
        self.assertEqual(settings.ROOT_URLCONF, 'backoffice.conf.urls')
        for foreign in ('RateLimitMiddleware', 'PremiumRequiredMiddleware', 'PremiumStatusMiddleware',
                        'corsheaders'):
            self.assertNotIn(foreign, ' '.join(settings.MIDDLEWARE))
        self.assertEqual(settings.SESSION_COOKIE_NAME, 'bo_sessionid')
        self.assertEqual(settings.CSRF_COOKIE_NAME, 'bo_csrftoken')

    def test_only_the_audit_model_belongs_to_backoffice(self):
        models = {model.__name__ for model in apps.get_app_config('backoffice').get_models()}
        self.assertEqual(models, {'StaffAuditLog'})

    def test_system_check_fails_when_loaded_with_a_foreign_urlconf(self):
        self.assertEqual(checks.check_isolated_settings(None), [])
        with override_settings(ROOT_URLCONF='hivmeet_backend.urls'):
            errors = checks.check_isolated_settings(None)
        self.assertEqual([error.id for error in errors], ['backoffice.E010'])

    def test_deploy_checks(self):
        locmem = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
        redis = {'default': {'BACKEND': 'django_redis.cache.RedisCache'}}
        with override_settings(DEBUG=True, CACHES=locmem):
            self.assertEqual(checks.check_production_hardening(None), [])
        with override_settings(DEBUG=False, CACHES=locmem, SESSION_COOKIE_SECURE=True,
                               CSRF_COOKIE_SECURE=True, SECRET_KEY='x' * 50):
            self.assertEqual([e.id for e in checks.check_production_hardening(None)], ['backoffice.E001'])
        with override_settings(DEBUG=False, CACHES=redis, SESSION_COOKIE_SECURE=False,
                               CSRF_COOKIE_SECURE=True, SECRET_KEY='django-insecure-abc'):
            ids = sorted(e.id for e in checks.check_production_hardening(None))
        self.assertEqual(ids, ['backoffice.E002', 'backoffice.E003'])
