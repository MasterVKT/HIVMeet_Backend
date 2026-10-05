"""Preview, apply, and restore the staged interaction-history repair."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from matching.models import InteractionHistory, Match


REPORT_VERSION = 1


class Command(BaseCommand):
    help = (
        'Prévisualise, applique ou restaure la réconciliation réversible des '
        'interactions actives. Ne journalise aucun identifiant dans la sortie.'
    )

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument('--dry-run', action='store_true')
        mode.add_argument('--apply', action='store_true')
        mode.add_argument('--restore', metavar='REPORT_PATH')
        parser.add_argument(
            '--report',
            metavar='REPORT_PATH',
            help='Chemin privé du rapport JSON requis pour --dry-run et --apply.',
        )
        parser.add_argument(
            '--user-id',
            help='Limite la prévisualisation ou l’application à un utilisateur.',
        )

    def handle(self, *args, **options):
        if options['restore']:
            if options.get('user_id') or options.get('report'):
                raise CommandError('--restore ne peut pas être combiné à --report ou --user-id.')
            self._restore(Path(options['restore']))
            return

        report_path = options.get('report')
        if not report_path:
            raise CommandError('--report est requis pour --dry-run et --apply.')

        scope = InteractionHistory.objects.all()
        if options.get('user_id'):
            scope = scope.filter(user_id=options['user_id'])

        if options['dry_run']:
            changes = self._plan(list(scope.order_by('user_id', 'target_user_id', '-created_at', '-id')))
            report = self._report('dry-run', changes, applied=False)
            self._write_report(Path(report_path), report)
            self.stdout.write(self.style.SUCCESS(
                f'Prévisualisation terminée : {len(changes)} ligne(s) seraient modifiées.'
            ))
            return

        with transaction.atomic():
            locked = list(
                scope.select_for_update().order_by(
                    'user_id', 'target_user_id', '-created_at', '-id'
                )
            )
            changes = self._plan(locked)
            report = self._report('apply', changes, applied=False)
            report_file = Path(report_path)
            # Keep a usable before/after report even if the transaction fails.
            self._write_report(report_file, report)
            for change in changes:
                InteractionHistory.objects.filter(pk=change['id']).update(
                    is_revoked=change['after']['is_revoked'],
                    revoked_at=self._parse_time(change['after']['revoked_at']),
                    rewound_at=self._parse_time(change['after']['rewound_at']),
                )

        report['applied'] = True
        self._write_report(Path(report_path), report)
        self.stdout.write(self.style.SUCCESS(
            f'Réconciliation appliquée : {len(changes)} ligne(s) modifiée(s).'
        ))

    def _plan(self, interactions):
        """Return deterministic state transitions without writing the database."""
        now = timezone.now()
        changes = {}

        def state(interaction, *, is_revoked=None, revoked_at=None):
            return {
                'is_revoked': interaction.is_revoked if is_revoked is None else is_revoked,
                'revoked_at': self._time_value(
                    interaction.revoked_at if revoked_at is None else revoked_at
                ),
                'rewound_at': self._time_value(interaction.rewound_at),
            }

        def revoke(interaction, reason, revoked_at):
            before = state(interaction)
            after = state(interaction, is_revoked=True, revoked_at=revoked_at)
            if before == after:
                return
            changes[str(interaction.id)] = {
                'id': str(interaction.id),
                'user_id': str(interaction.user_id),
                'target_user_id': str(interaction.target_user_id),
                'reason': reason,
                'before': before,
                'after': after,
            }

        for interaction in interactions:
            if not interaction.is_revoked and interaction.rewound_at is not None:
                revoke(
                    interaction,
                    'rewound_interaction_still_active',
                    interaction.revoked_at or interaction.rewound_at,
                )

        active_by_pair = defaultdict(list)
        for interaction in interactions:
            planned = changes.get(str(interaction.id))
            if interaction.is_revoked or (planned and planned['after']['is_revoked']):
                continue
            active_by_pair[(interaction.user_id, interaction.target_user_id)].append(interaction)

        active_match_pairs = {
            tuple(sorted((match.user1_id, match.user2_id)))
            for match in Match.objects.filter(status=Match.ACTIVE).only('user1_id', 'user2_id')
        }
        for pair, active in active_by_pair.items():
            if len(active) < 2:
                continue
            matched = tuple(sorted(pair)) in active_match_pairs
            matched_likes = [
                interaction
                for interaction in active
                if interaction.interaction_type
                in (InteractionHistory.LIKE, InteractionHistory.SUPER_LIKE)
            ]
            winner = (
                max(matched_likes, key=self._newest_key)
                if matched and matched_likes
                else max(active, key=self._newest_key)
            )
            for interaction in active:
                if interaction.pk != winner.pk:
                    revoke(interaction, 'duplicate_active_pair', now)

        return list(changes.values())

    @staticmethod
    def _newest_key(interaction):
        # The UUID tie-breaker makes legacy imports with identical timestamps
        # deterministic without ever relying on a display name.
        return (interaction.created_at, str(interaction.id))

    def _report(self, mode, changes, *, applied):
        return {
            'version': REPORT_VERSION,
            'mode': mode,
            'applied': applied,
            'generated_at': self._time_value(timezone.now()),
            'changes': changes,
            'summary': {
                'changed_count': len(changes),
                'rewound_active_count': sum(
                    change['reason'] == 'rewound_interaction_still_active'
                    for change in changes
                ),
                'duplicate_active_count': sum(
                    change['reason'] == 'duplicate_active_pair' for change in changes
                ),
            },
        }

    def _restore(self, report_path):
        report = self._read_report(report_path)
        if report.get('mode') != 'apply' or report.get('applied') is not True:
            raise CommandError('Le rapport ne correspond pas à une application terminée.')
        changes = report.get('changes')
        if not isinstance(changes, list):
            raise CommandError('Le rapport ne contient pas de changements valides.')

        with transaction.atomic():
            ids = [change.get('id') for change in changes]
            interactions = {
                str(interaction.id): interaction
                for interaction in InteractionHistory.objects.select_for_update().filter(pk__in=ids)
            }
            if len(interactions) != len(ids):
                raise CommandError('Restauration annulée : une interaction du rapport est absente.')
            for change in changes:
                interaction = interactions[change['id']]
                if self._state_from_interaction(interaction) != change.get('after'):
                    raise CommandError(
                        'Restauration annulée : une interaction a changé depuis le rapport.'
                    )
            self._require_constraint_compatible_restore(interactions, changes)
            for change in changes:
                before = change['before']
                InteractionHistory.objects.filter(pk=change['id']).update(
                    is_revoked=before['is_revoked'],
                    revoked_at=self._parse_time(before['revoked_at']),
                    rewound_at=self._parse_time(before['rewound_at']),
                )
        self.stdout.write(self.style.SUCCESS(
            f'Restauration terminée : {len(changes)} ligne(s) restaurée(s).'
        ))

    def _require_constraint_compatible_restore(self, interactions, changes):
        """Fail clearly when exact rollback needs migration 0006 reversed first."""
        final_active_ids = set(
            InteractionHistory.objects.filter(is_revoked=False).values_list('id', flat=True)
        )
        desired_by_pair = defaultdict(int)
        for interaction in InteractionHistory.objects.filter(
            is_revoked=False
        ).only('id', 'user_id', 'target_user_id'):
            desired_by_pair[(interaction.user_id, interaction.target_user_id)] += 1
        for change in changes:
            interaction = interactions[change['id']]
            pair = (interaction.user_id, interaction.target_user_id)
            if interaction.id in final_active_ids:
                desired_by_pair[pair] -= 1
            if change['before']['is_revoked'] is False:
                desired_by_pair[pair] += 1
        if any(count > 1 for count in desired_by_pair.values()):
            raise CommandError(
                'La restauration exacte recréerait plusieurs interactions actives '
                'pour une paire. Revenez d’abord à la migration matching 0005, '
                'puis relancez --restore avec le même rapport privé.'
            )

    def _write_report(self, path, report):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding='utf-8',
        )
        os.replace(temporary, path)

    def _read_report(self, path):
        try:
            report = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as error:
            raise CommandError(f'Rapport illisible : {error}') from error
        if report.get('version') != REPORT_VERSION:
            raise CommandError('Version de rapport non prise en charge.')
        return report

    @staticmethod
    def _time_value(value):
        return value.isoformat() if value is not None else None

    def _state_from_interaction(self, interaction):
        return {
            'is_revoked': interaction.is_revoked,
            'revoked_at': self._time_value(interaction.revoked_at),
            'rewound_at': self._time_value(interaction.rewound_at),
        }

    @staticmethod
    def _parse_time(value):
        if value is None:
            return None
        parsed = parse_datetime(value)
        if parsed is None:
            raise CommandError('Le rapport contient une date invalide.')
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed)
        return parsed
