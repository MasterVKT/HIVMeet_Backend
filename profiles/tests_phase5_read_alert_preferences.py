"""Tests for Premium defaults and reversible legacy preference repair."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from subscriptions.utils import invalidate_premium_status_cache


User = get_user_model()


class ReadAlertPreferenceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='read-alert-preference@example.test',
            password='TestPass123!',
            display_name='Preference',
            birth_date=date(1990, 1, 1),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = '/api/v1/user-settings/notification-preferences'

    def _activate_premium(self):
        self.user.is_premium = True
        self.user.premium_until = timezone.now() + timedelta(days=30)
        self.user.save(update_fields=['is_premium', 'premium_until'])
        invalidate_premium_status_cache(self.user)

    def test_active_premium_defaults_to_enabled_and_free_write_preserves_choice(self):
        self._activate_premium()
        response = self.client.get(self.url)
        self.assertTrue(response.data['message_read_notifications'])

        response = self.client.put(
            self.url,
            {'message_read_notifications': False},
            format='json',
        )
        self.assertFalse(response.data['message_read_notifications'])

        self.user.is_premium = False
        self.user.premium_until = timezone.now() - timedelta(days=1)
        self.user.save(update_fields=['is_premium', 'premium_until'])
        invalidate_premium_status_cache(self.user)
        response = self.client.put(
            self.url,
            {'message_read_notifications': True},
            format='json',
        )
        self.assertFalse(response.data['message_read_notifications'])
        self.user.refresh_from_db()
        self.assertFalse(self.user.notification_settings['message_read_notifications'])

        self._activate_premium()
        response = self.client.get(self.url)
        self.assertFalse(response.data['message_read_notifications'])

    def test_repair_command_is_dry_run_then_reversible(self):
        self.user.notification_settings = {'message_read_notifications': False}
        self.user.save(update_fields=['notification_settings'])

        call_command('audit_message_read_preferences')
        self.user.refresh_from_db()
        self.assertFalse(self.user.notification_settings['message_read_notifications'])

        with TemporaryDirectory() as directory:
            report_path = Path(directory) / 'read-alert-repair.json'
            call_command(
                'audit_message_read_preferences',
                '--apply',
                '--report',
                str(report_path),
            )
            report = json.loads(report_path.read_text(encoding='utf-8'))
            self.assertTrue(report['applied'])
            self.user.refresh_from_db()
            self.assertNotIn('message_read_notifications', self.user.notification_settings)

            call_command('audit_message_read_preferences', '--restore', str(report_path))
        self.user.refresh_from_db()
        self.assertFalse(self.user.notification_settings['message_read_notifications'])
