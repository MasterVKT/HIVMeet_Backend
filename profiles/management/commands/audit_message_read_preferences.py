"""Audit and reversibly repair legacy Free read-alert preference values."""

from __future__ import annotations

import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from notifications.read_receipt_alerts import MESSAGE_READ_NOTIFICATIONS
from subscriptions.models import Subscription


class Command(BaseCommand):
    help = (
        'Audit legacy message_read_notifications=false values created for users '
        'with no Premium history. --apply requires a private JSON report and '
        '--restore replays that report.'
    )

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument(
            '--apply',
            action='store_true',
            help='Remove only audited automatic false values.',
        )
        mode.add_argument(
            '--restore',
            metavar='REPORT',
            help='Restore a report created by --apply.',
        )
        parser.add_argument(
            '--report',
            metavar='PATH',
            help='Private JSON report path. Required with --apply.',
        )

    def handle(self, *args, **options):
        if options['restore']:
            if options['report']:
                raise CommandError('--report cannot be combined with --restore.')
            return self._restore(Path(options['restore']))

        apply_changes = bool(options['apply'])
        report_path = Path(options['report']) if options['report'] else None
        if apply_changes and report_path is None:
            raise CommandError('--apply requires --report so the change is reversible.')

        candidates = self._candidates()
        report = {
            'kind': 'message_read_preferences_repair',
            'created_at': timezone.now().isoformat(),
            'applied': apply_changes,
            'candidates': candidates,
        }

        if report_path is not None:
            self._write_report(report_path, report)

        if not apply_changes:
            self.stdout.write(
                self.style.WARNING(
                    f'Dry run: {len(candidates)} legacy preference(s) eligible.'
                )
            )
            return

        user_model = get_user_model()
        with transaction.atomic():
            for item in candidates:
                user = user_model.objects.select_for_update().get(pk=item['user_id'])
                settings = dict(user.notification_settings or {})
                if settings.get(MESSAGE_READ_NOTIFICATIONS) is not False:
                    continue
                settings.pop(MESSAGE_READ_NOTIFICATIONS, None)
                user.notification_settings = settings
                user.save(update_fields=['notification_settings'])

        self.stdout.write(
            self.style.SUCCESS(
                f'Applied: removed {len(candidates)} legacy preference(s).'
            )
        )

    def _candidates(self):
        """Return only values whose automatic Free provenance is certain.

        A user with any paid subscription record or either legacy Premium field
        is deliberately excluded: their false value could be an explicit choice.
        """
        user_model = get_user_model()
        candidates = []
        for user in user_model.objects.only(
            'id', 'is_premium', 'premium_until', 'notification_settings'
        ).iterator():
            settings = user.notification_settings or {}
            if settings.get(MESSAGE_READ_NOTIFICATIONS) is not False:
                continue
            if user.is_premium or user.premium_until is not None:
                continue
            if Subscription.objects.filter(user_id=user.id, plan__price__gt=0).exists():
                continue
            candidates.append({
                'user_id': str(user.id),
                'previous_value': False,
            })
        return candidates

    def _restore(self, report_path: Path):
        try:
            report = json.loads(report_path.read_text(encoding='utf-8'))
        except OSError as exc:
            raise CommandError(f'Cannot read report: {exc}') from exc
        except json.JSONDecodeError as exc:
            raise CommandError('Report is not valid JSON.') from exc

        if report.get('kind') != 'message_read_preferences_repair':
            raise CommandError('This is not a message-read-preferences report.')
        candidates = report.get('candidates')
        if not isinstance(candidates, list):
            raise CommandError('Report candidates are invalid.')

        user_model = get_user_model()
        restored = 0
        with transaction.atomic():
            for item in candidates:
                user_id = item.get('user_id') if isinstance(item, dict) else None
                if not user_id or item.get('previous_value') is not False:
                    continue
                user = user_model.objects.select_for_update().filter(pk=user_id).first()
                if user is None:
                    continue
                settings = dict(user.notification_settings or {})
                # Do not overwrite an explicit decision made after the repair.
                if MESSAGE_READ_NOTIFICATIONS in settings:
                    continue
                settings[MESSAGE_READ_NOTIFICATIONS] = False
                user.notification_settings = settings
                user.save(update_fields=['notification_settings'])
                restored += 1

        self.stdout.write(self.style.SUCCESS(f'Restored: {restored} preference(s).'))

    @staticmethod
    def _write_report(path: Path, report: dict):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(report, indent=2, sort_keys=True) + '\n',
                encoding='utf-8',
            )
        except OSError as exc:
            raise CommandError(f'Cannot write report: {exc}') from exc
