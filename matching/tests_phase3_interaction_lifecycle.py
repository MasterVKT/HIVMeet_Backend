import json
import threading
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, transaction
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from matching.management.commands.reconcile_interaction_history import Command
from matching.models import (
    Dislike,
    InteractionActionRejected,
    InteractionHistory,
    Like,
    Match,
)


User = get_user_model()
FEATURE_AVAILABLE = {'available': True, 'reason': None}


class InteractionLifecyclePhaseThreeTests(APITestCase):
    def setUp(self):
        self.actor = self._user('actor', 'Actor')
        self.target = self._user('target', 'Target')
        self.client.force_authenticate(self.actor)

    @staticmethod
    def _user(slug, display_name):
        return User.objects.create_user(
            email=f'{slug}@example.test',
            password='testpass123',
            display_name=display_name,
            birth_date=date(1990, 1, 1),
            email_verified=True,
            is_active=True,
        )

    def _rewind(self, interaction_id):
        with patch(
            'matching.views_discovery.check_feature_availability',
            return_value=FEATURE_AVAILABLE,
        ):
            return self.client.post(
                f'/api/v1/discovery/interactions/{interaction_id}/rewind/'
            )

    def test_pass_rewind_like_rewind_creates_two_distinct_actions(self):
        passed = self.client.post(
            '/api/v1/discovery/interactions/dislike',
            {'target_user_id': str(self.target.id)},
            format='json',
        )
        self.assertEqual(passed.status_code, status.HTTP_201_CREATED)
        pass_id = passed.data['interaction_id']

        first_rewind = self._rewind(pass_id)
        self.assertEqual(first_rewind.status_code, status.HTTP_200_OK)
        self.assertFalse(first_rewind.data['already_rewound'])

        liked = self.client.post(
            '/api/v1/discovery/interactions/like',
            {'target_user_id': str(self.target.id)},
            format='json',
        )
        self.assertEqual(liked.status_code, status.HTTP_201_CREATED)
        like_id = liked.data['interaction_id']
        self.assertNotEqual(pass_id, like_id)

        old_retry = self._rewind(pass_id)
        self.assertEqual(old_retry.status_code, status.HTTP_200_OK)
        self.assertTrue(old_retry.data['already_rewound'])

        second_rewind = self._rewind(like_id)
        self.assertEqual(second_rewind.status_code, status.HTTP_200_OK)
        self.assertFalse(second_rewind.data['already_rewound'])

        interactions = list(
            InteractionHistory.objects.filter(
                user=self.actor, target_user=self.target
            ).order_by('created_at')
        )
        self.assertEqual([str(item.id) for item in interactions], [pass_id, like_id])
        self.assertTrue(all(item.is_revoked for item in interactions))
        self.assertTrue(all(item.rewound_at is not None for item in interactions))
        self.assertFalse(
            InteractionHistory.objects.filter(
                user=self.actor, target_user=self.target, is_revoked=False
            ).exists()
        )

        self.assertEqual(
            self.client.get('/api/v1/discovery/interactions/my-passes').data['count'],
            0,
        )
        self.assertEqual(
            self.client.get('/api/v1/discovery/interactions/my-likes').data['count'],
            0,
        )

    def test_same_active_action_is_idempotent_and_revoked_action_gets_new_id(self):
        first, created = InteractionHistory.create_or_reactivate(
            self.actor, self.target, InteractionHistory.DISLIKE
        )
        retry, retry_created = InteractionHistory.create_or_reactivate(
            self.actor, self.target, InteractionHistory.DISLIKE
        )
        self.assertTrue(created)
        self.assertFalse(retry_created)
        self.assertEqual(first.id, retry.id)
        self.assertEqual(first.created_at, retry.created_at)

        first.revoke()
        later, later_created = InteractionHistory.create_or_reactivate(
            self.actor, self.target, InteractionHistory.DISLIKE
        )
        self.assertTrue(later_created)
        self.assertNotEqual(first.id, later.id)
        self.assertTrue(InteractionHistory.objects.get(pk=first.pk).is_revoked)

    def test_new_type_replaces_unmatched_active_projection(self):
        passed, _ = InteractionHistory.create_or_reactivate(
            self.actor, self.target, InteractionHistory.DISLIKE
        )
        liked, created = InteractionHistory.create_or_reactivate(
            self.actor, self.target, InteractionHistory.LIKE
        )

        self.assertTrue(created)
        passed.refresh_from_db()
        self.assertTrue(passed.is_revoked)
        self.assertFalse(liked.is_revoked)
        self.assertEqual(
            InteractionHistory.objects.filter(
                user=self.actor, target_user=self.target, is_revoked=False
            ).count(),
            1,
        )

    def test_database_constraint_rejects_two_active_types_for_one_pair(self):
        InteractionHistory.objects.create(
            user=self.actor,
            target_user=self.target,
            interaction_type=InteractionHistory.DISLIKE,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            InteractionHistory.objects.create(
                user=self.actor,
                target_user=self.target,
                interaction_type=InteractionHistory.LIKE,
            )

    def test_action_after_match_is_refused_without_replacing_the_like(self):
        liked, _ = InteractionHistory.create_or_reactivate(
            self.actor, self.target, InteractionHistory.LIKE
        )
        Match.objects.create(user1=self.actor, user2=self.target)

        with self.assertRaises(InteractionActionRejected) as raised:
            InteractionHistory.create_or_reactivate(
                self.actor, self.target, InteractionHistory.DISLIKE
            )

        self.assertEqual(raised.exception.code, 'match_exists_use_unmatch')
        self.assertFalse(InteractionHistory.objects.get(pk=liked.pk).is_revoked)
        self.assertFalse(
            InteractionHistory.objects.filter(
                user=self.actor,
                target_user=self.target,
                interaction_type=InteractionHistory.DISLIKE,
            ).exists()
        )

    def test_pass_then_like_replaces_both_canonical_and_legacy_projection(self):
        passed = self.client.post(
            '/api/v1/discovery/interactions/dislike',
            {'target_user_id': str(self.target.id)},
            format='json',
        )
        self.assertEqual(passed.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Dislike.objects.filter(
            from_user=self.actor, to_user=self.target
        ).exists())

        liked = self.client.post(
            '/api/v1/discovery/interactions/like',
            {'target_user_id': str(self.target.id)},
            format='json',
        )
        self.assertEqual(liked.status_code, status.HTTP_201_CREATED)
        self.assertFalse(Dislike.objects.filter(
            from_user=self.actor, to_user=self.target
        ).exists())
        self.assertTrue(Like.objects.filter(
            from_user=self.actor, to_user=self.target
        ).exists())
        active = InteractionHistory.objects.get(
            user=self.actor, target_user=self.target, is_revoked=False
        )
        self.assertEqual(active.interaction_type, InteractionHistory.LIKE)
        self.assertEqual(
            InteractionHistory.objects.filter(
                user=self.actor, target_user=self.target, is_revoked=False
            ).count(),
            1,
        )

    def test_retry_active_like_keeps_one_interaction_and_one_quota_use(self):
        first = self.client.post(
            '/api/v1/discovery/interactions/like',
            {'target_user_id': str(self.target.id)},
            format='json',
        )
        second = self.client.post(
            '/api/v1/discovery/interactions/like',
            {'target_user_id': str(self.target.id)},
            format='json',
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            InteractionHistory.objects.filter(
                user=self.actor, target_user=self.target
            ).count(),
            1,
        )
        self.assertEqual(first.data['daily_likes_remaining'], 9)
        self.assertEqual(second.data['daily_likes_remaining'], 9)

    def test_pass_after_match_is_refused(self):
        Like.objects.create(from_user=self.actor, to_user=self.target)
        Like.objects.create(from_user=self.target, to_user=self.actor)
        InteractionHistory.objects.create(
            user=self.actor,
            target_user=self.target,
            interaction_type=InteractionHistory.LIKE,
        )
        Match.objects.create(user1=self.actor, user2=self.target)

        response = self.client.post(
            '/api/v1/discovery/interactions/dislike',
            {'target_user_id': str(self.target.id)},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['code'], 'match_exists_use_unmatch')
        self.assertTrue(Like.objects.filter(
            from_user=self.actor, to_user=self.target
        ).exists())

    def test_reconciliation_prefers_matched_like_over_a_second_active_type(self):
        liked = InteractionHistory.objects.create(
            user=self.actor,
            target_user=self.target,
            interaction_type=InteractionHistory.LIKE,
        )
        passed = InteractionHistory.objects.create(
            user=self.actor,
            target_user=self.target,
            interaction_type=InteractionHistory.DISLIKE,
            is_revoked=True,
        )
        Match.objects.create(user1=self.actor, user2=self.target)

        # The final pair constraint prevents corrupt rows in normal use.  The
        # reconciliation planner receives this in-memory legacy snapshot to
        # prove which projection an old database will retain before migration.
        passed.is_revoked = False
        changes = Command()._plan([liked, passed])

        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]['id'], str(passed.id))
        self.assertEqual(changes[0]['reason'], 'duplicate_active_pair')

    def test_super_like_is_explicit_in_history_and_can_be_rewound(self):
        Like.objects.create(
            from_user=self.actor,
            to_user=self.target,
            like_type=Like.SUPER,
        )
        super_like = InteractionHistory.objects.create(
            user=self.actor,
            target_user=self.target,
            interaction_type=InteractionHistory.SUPER_LIKE,
        )

        history = self.client.get('/api/v1/discovery/interactions/my-likes')
        self.assertEqual(history.status_code, status.HTTP_200_OK)
        self.assertEqual(history.data['results'][0]['interaction_type'], 'super_like')

        rewind = self._rewind(super_like.id)
        self.assertEqual(rewind.status_code, status.HTTP_200_OK)
        super_like.refresh_from_db()
        self.assertTrue(super_like.is_revoked)
        self.assertEqual(
            self.client.get('/api/v1/discovery/interactions/my-likes').data['count'],
            0,
        )

    def test_reconciliation_preview_apply_and_restore_are_reversible(self):
        interaction = InteractionHistory.objects.create(
            user=self.actor,
            target_user=self.target,
            interaction_type=InteractionHistory.DISLIKE,
        )
        InteractionHistory.objects.filter(pk=interaction.pk).update(
            rewound_at=timezone.now() - timedelta(seconds=1)
        )

        with TemporaryDirectory() as directory:
            preview_path = Path(directory) / 'preview.json'
            call_command(
                'reconcile_interaction_history',
                '--dry-run',
                '--report',
                str(preview_path),
            )
            preview = json.loads(preview_path.read_text(encoding='utf-8'))
            self.assertEqual(preview['summary']['rewound_active_count'], 1)
            interaction.refresh_from_db()
            self.assertFalse(interaction.is_revoked)

            report_path = Path(directory) / 'applied.json'
            call_command(
                'reconcile_interaction_history',
                '--apply',
                '--report',
                str(report_path),
            )
            interaction.refresh_from_db()
            self.assertTrue(interaction.is_revoked)

            call_command('reconcile_interaction_history', '--restore', str(report_path))
            interaction.refresh_from_db()
            self.assertFalse(interaction.is_revoked)


class InteractionConcurrencyPhaseThreeTests(TransactionTestCase):
    """Exercise the pair locks with independent database connections."""

    reset_sequences = True

    def setUp(self):
        self.actor = User.objects.create_user(
            email='concurrent-actor@example.test',
            password='testpass123',
            display_name='Concurrent actor',
            birth_date=date(1990, 1, 1),
            email_verified=True,
            is_active=True,
        )
        self.target = User.objects.create_user(
            email='concurrent-target@example.test',
            password='testpass123',
            display_name='Concurrent target',
            birth_date=date(1991, 1, 1),
            email_verified=True,
            is_active=True,
        )

    def test_concurrent_different_actions_leave_one_active_projection(self):
        start = threading.Barrier(2)
        results = []
        errors = []
        result_lock = threading.Lock()

        def record(interaction_type):
            close_old_connections()
            try:
                start.wait(timeout=5)
                interaction, created = InteractionHistory.create_or_reactivate(
                    self.actor,
                    self.target,
                    interaction_type,
                )
                with result_lock:
                    results.append((interaction.id, created))
            except Exception as error:  # Assertion below keeps thread errors visible.
                with result_lock:
                    errors.append(error)
            finally:
                close_old_connections()

        threads = [
            threading.Thread(target=record, args=(InteractionHistory.LIKE,)),
            threading.Thread(target=record, args=(InteractionHistory.DISLIKE,)),
        ]
        for worker in threads:
            worker.start()
        for worker in threads:
            worker.join(timeout=10)

        self.assertFalse(any(worker.is_alive() for worker in threads))
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(
            InteractionHistory.objects.filter(
                user=self.actor,
                target_user=self.target,
                is_revoked=False,
            ).count(),
            1,
        )
        self.assertEqual(
            InteractionHistory.objects.filter(
                user=self.actor,
                target_user=self.target,
            ).count(),
            2,
        )
