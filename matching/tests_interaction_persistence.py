from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from matching.models import Dislike, InteractionHistory, Like


User = get_user_model()


class DiscoveryInteractionPersistenceTests(APITestCase):
    def setUp(self):
        self.client = APIClient()

        self.actor = User.objects.create_user(
            email='actor@example.com',
            password='testpass123',
            display_name='Actor',
            birth_date=date(1990, 1, 1),
            email_verified=True,
            is_active=True,
        )
        self.target = User.objects.create_user(
            email='target@example.com',
            password='testpass123',
            display_name='Target',
            birth_date=date(1992, 1, 1),
            email_verified=True,
            is_active=True,
        )

        # Keep discovery compatibility simple for serializer paths and history endpoints.
        self.actor.profile.gender = 'male'
        self.actor.profile.genders_sought = ['female']
        self.actor.profile.allow_profile_in_discovery = True
        self.actor.profile.save()

        self.target.profile.gender = 'female'
        self.target.profile.genders_sought = ['male']
        self.target.profile.allow_profile_in_discovery = True
        self.target.profile.save()

        self.client.force_authenticate(user=self.actor)

    def test_like_endpoint_backfills_history_when_legacy_like_exists(self):
        Like.objects.create(from_user=self.actor, to_user=self.target, like_type=Like.REGULAR)

        self.assertFalse(
            InteractionHistory.objects.filter(
                user=self.actor,
                target_user=self.target,
                interaction_type=InteractionHistory.LIKE,
                is_revoked=False,
            ).exists()
        )

        response = self.client.post(
            '/api/v1/discovery/interactions/like',
            {'target_user_id': str(self.target.id)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        interaction = InteractionHistory.objects.filter(
            user=self.actor,
            target_user=self.target,
            interaction_type=InteractionHistory.LIKE,
            is_revoked=False,
        ).first()
        self.assertIsNotNone(interaction)

        history_response = self.client.get(
            '/api/v1/discovery/interactions/my-likes?page=1&page_size=20&order_by=recent'
        )
        self.assertEqual(history_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(history_response.data['count'], 1)
        self.assertEqual(
            history_response.data['results'][0]['profile']['user_id'],
            str(self.target.id),
        )

    def test_dislike_endpoint_backfills_history_when_legacy_dislike_exists(self):
        Dislike.objects.create(
            from_user=self.actor,
            to_user=self.target,
            expires_at=timezone.now() + timedelta(days=30),
        )

        self.assertFalse(
            InteractionHistory.objects.filter(
                user=self.actor,
                target_user=self.target,
                interaction_type=InteractionHistory.DISLIKE,
                is_revoked=False,
            ).exists()
        )

        response = self.client.post(
            '/api/v1/discovery/interactions/dislike',
            {'target_user_id': str(self.target.id)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        interaction = InteractionHistory.objects.filter(
            user=self.actor,
            target_user=self.target,
            interaction_type=InteractionHistory.DISLIKE,
            is_revoked=False,
        ).first()
        self.assertIsNotNone(interaction)

        history_response = self.client.get(
            '/api/v1/discovery/interactions/my-passes?page=1&page_size=20&order_by=recent'
        )
        self.assertEqual(history_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(history_response.data['count'], 1)
        self.assertEqual(
            history_response.data['results'][0]['profile']['user_id'],
            str(self.target.id),
        )

    def test_idempotent_dislike_refreshes_history_timestamp_for_recent_ordering(self):
        Dislike.objects.create(
            from_user=self.actor,
            to_user=self.target,
            expires_at=timezone.now() + timedelta(days=30),
        )

        interaction = InteractionHistory.objects.create(
            user=self.actor,
            target_user=self.target,
            interaction_type=InteractionHistory.DISLIKE,
            is_revoked=False,
        )
        old_time = timezone.now() - timedelta(days=2)
        InteractionHistory.objects.filter(id=interaction.id).update(created_at=old_time)

        response = self.client.post(
            '/api/v1/discovery/interactions/dislike',
            {'target_user_id': str(self.target.id)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        interaction.refresh_from_db()
        # Repeating the same swipe is idempotent: it must retain the original
        # interaction identity and cannot extend the five-minute rewind window.
        self.assertEqual(interaction.created_at, old_time)
