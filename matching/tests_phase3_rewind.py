from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from matching.models import DailyLikeLimit, Dislike, InteractionHistory, Like, Match


User = get_user_model()
FEATURE_AVAILABLE = {'available': True, 'reason': None}


class ExplicitInteractionRewindTests(APITestCase):
    def setUp(self):
        self.actor = User.objects.create_user(
            email='rewind-actor@example.test',
            password='testpass123',
            display_name='Actor',
            birth_date=date(1990, 1, 1),
            email_verified=True,
        )
        self.target = User.objects.create_user(
            email='rewind-target@example.test',
            password='testpass123',
            display_name='Target',
            birth_date=date(1992, 1, 1),
            email_verified=True,
        )
        self.client.force_authenticate(self.actor)

    def _create_dislike(self):
        Dislike.objects.create(
            from_user=self.actor,
            to_user=self.target,
            expires_at=timezone.now() + timedelta(days=30),
        )
        return InteractionHistory.objects.create(
            user=self.actor,
            target_user=self.target,
            interaction_type=InteractionHistory.DISLIKE,
        )

    def _rewind(self, interaction):
        return self.client.post(
            f'/api/v1/discovery/interactions/{interaction.id}/rewind/',
        )

    @patch('matching.views_discovery.check_feature_availability', return_value=FEATURE_AVAILABLE)
    def test_dislike_response_has_exact_interaction_and_rewinds_immediately(self, _feature):
        response = self.client.post(
            '/api/v1/discovery/interactions/dislike',
            {'target_user_id': str(self.target.id)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(response.data['interaction_id'])
        self.assertTrue(response.data['can_rewind'])
        self.assertIsNotNone(response.data['rewind_expires_at'])

        first = self.client.post(
            f"/api/v1/discovery/interactions/{response.data['interaction_id']}/rewind/"
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertFalse(first.data['already_rewound'])
        self.assertFalse(Dislike.objects.filter(from_user=self.actor, to_user=self.target).exists())

    @patch('matching.views_discovery.check_feature_availability', return_value=FEATURE_AVAILABLE)
    def test_retry_is_idempotent_and_consumes_one_quota(self, _feature):
        interaction = self._create_dislike()

        first = self._rewind(interaction)
        second = self._rewind(interaction)

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertTrue(second.data['already_rewound'])
        limit = DailyLikeLimit.objects.get(user=self.actor, date=timezone.localdate())
        self.assertEqual(limit.rewinds_count, 1)

    @patch('matching.views_discovery.check_feature_availability', return_value=FEATURE_AVAILABLE)
    def test_expired_interaction_does_not_mutate_projection(self, _feature):
        interaction = self._create_dislike()
        InteractionHistory.objects.filter(pk=interaction.pk).update(
            created_at=timezone.now() - timedelta(minutes=6)
        )

        response = self._rewind(interaction)

        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertEqual(response.data['code'], 'rewind_expired')
        self.assertTrue(Dislike.objects.filter(from_user=self.actor, to_user=self.target).exists())

    @patch('matching.views_discovery.check_feature_availability', return_value=FEATURE_AVAILABLE)
    def test_daily_quota_and_match_protect_existing_projection(self, _feature):
        interaction = self._create_dislike()
        DailyLikeLimit.objects.create(
            user=self.actor,
            date=timezone.localdate(),
            rewinds_count=5,
        )

        quota = self._rewind(interaction)
        self.assertEqual(quota.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertTrue(Dislike.objects.filter(from_user=self.actor, to_user=self.target).exists())

        DailyLikeLimit.objects.filter(user=self.actor).update(rewinds_count=0)
        Match.objects.create(user1=self.actor, user2=self.target)
        matched = self._rewind(interaction)
        self.assertEqual(matched.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(matched.data['code'], 'match_exists_use_unmatch')
        self.assertTrue(Dislike.objects.filter(from_user=self.actor, to_user=self.target).exists())

    @patch('matching.views_discovery.check_feature_availability', return_value=FEATURE_AVAILABLE)
    def test_like_match_is_never_rewound(self, _feature):
        Like.objects.create(from_user=self.actor, to_user=self.target)
        interaction = InteractionHistory.objects.create(
            user=self.actor,
            target_user=self.target,
            interaction_type=InteractionHistory.LIKE,
        )
        Match.objects.create(user1=self.actor, user2=self.target)

        response = self._rewind(interaction)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(Like.objects.filter(from_user=self.actor, to_user=self.target).exists())
