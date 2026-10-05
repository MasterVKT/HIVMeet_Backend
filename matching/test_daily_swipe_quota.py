from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch

from .daily_likes_service import DailyLikesService
from .models import InteractionHistory
from .services import MatchingService
from .signals import dispatch_group_event


User = get_user_model()


class DailySwipeQuotaTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='swiper@example.com',
            password='test-pass',
            display_name='Swiper',
            birth_date=date(1990, 1, 1),
        )

    def _target(self, index):
        return User.objects.create_user(
            email=f'target-{index}@example.com',
            password='test-pass',
            display_name=f'Target {index}',
            birth_date=date(1990, 1, 1),
        )

    @patch('matching.signals.Thread')
    @patch('matching.signals.transaction.on_commit')
    def test_realtime_side_effect_starts_only_after_database_commit(
        self,
        on_commit,
        thread_class,
    ):
        dispatch_group_event('user-test', {'type': 'new_like'})

        on_commit.assert_called_once()
        thread_class.assert_not_called()

        commit_callback = on_commit.call_args.args[0]
        commit_callback()

        thread_class.assert_called_once()
        thread_class.return_value.start.assert_called_once()

    def test_every_swipe_direction_decrements_free_quota(self):
        for index, interaction_type in enumerate([
            InteractionHistory.LIKE,
            InteractionHistory.DISLIKE,
            InteractionHistory.SUPER_LIKE,
        ]):
            InteractionHistory.objects.create(
                user=self.user,
                target_user=self._target(index),
                interaction_type=interaction_type,
            )

        status = DailyLikesService.get_status_summary(self.user)
        self.assertEqual(status['daily_likes_limit'], 10)
        self.assertEqual(status['daily_likes_remaining'], 7)
        self.assertEqual(status['swipes_used_today'], 3)

    def test_status_endpoint_exposes_initial_free_quota(self):
        client = APIClient()
        client.force_authenticate(user=self.user)

        response = client.get(
            '/api/v1/discovery/interactions/status',
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['daily_likes_remaining'], 10)
        self.assertEqual(response.data['daily_likes_limit'], 10)
        self.assertEqual(response.data['swipes_used_today'], 0)
        self.assertEqual(response.data['super_likes_remaining'], 0)
        self.assertFalse(response.data['is_premium'])

    @patch('matching.signals.dispatch_group_event')
    @patch('matching.tasks.send_like_notification.delay')
    def test_free_account_cannot_send_super_likes(
        self,
        _send_notification,
        _dispatch_realtime,
    ):
        first_target = self._target(20)
        success, is_match, error, code = MatchingService.like_profile(
            self.user,
            first_target,
            is_super_like=True,
        )

        self.assertFalse(success)
        self.assertFalse(is_match)
        self.assertIsNotNone(error)
        self.assertEqual(code, 'premium_required')
        self.assertEqual(
            DailyLikesService.get_super_likes_remaining(self.user),
            0,
        )
        self.assertEqual(DailyLikesService.get_likes_remaining(self.user), 10)
        self.assertEqual(
            InteractionHistory.objects.filter(user=self.user).count(),
            0,
        )

    def test_shared_quota_rejects_every_direction_after_ten_swipes(self):
        for index in range(10):
            InteractionHistory.objects.create(
                user=self.user,
                target_user=self._target(index),
                interaction_type=InteractionHistory.DISLIKE,
            )

        extra_target = self._target(10)
        like_success, _, _, like_code = MatchingService.like_profile(
            self.user,
            extra_target,
        )
        dislike_success, _ = MatchingService.dislike_profile(
            self.user,
            extra_target,
        )

        self.assertFalse(like_success)
        self.assertEqual(like_code, 'daily_limit')
        self.assertFalse(dislike_success)
        self.assertEqual(DailyLikesService.get_likes_remaining(self.user), 0)
        self.assertEqual(
            InteractionHistory.objects.filter(user=self.user).count(),
            10,
        )

    @patch('matching.signals.dispatch_group_event')
    @patch('matching.tasks.send_like_notification.delay')
    def test_like_is_persisted_and_decrements_quota(
        self,
        _send_notification,
        _dispatch_realtime,
    ):
        target = self._target(99)

        success, is_match, error, code = MatchingService.like_profile(
            self.user,
            target,
        )

        self.assertTrue(success)
        self.assertFalse(is_match)
        self.assertIsNone(error)
        self.assertIsNone(code)
        self.assertEqual(DailyLikesService.get_likes_remaining(self.user), 9)

    @patch('matching.signals.dispatch_group_event')
    @patch('matching.tasks.send_like_notification.delay')
    def test_like_endpoint_returns_201_and_exposes_new_quota(
        self,
        _send_notification,
        _dispatch_realtime,
    ):
        target = self._target(100)
        client = APIClient()
        client.force_authenticate(user=self.user)

        response = client.post(
            '/api/v1/discovery/interactions/like',
            {'target_user_id': str(target.id)},
            format='json',
            secure=True,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['status'], 'liked')
        self.assertEqual(response.data['daily_likes_remaining'], 9)
        self.assertEqual(
            InteractionHistory.objects.filter(
                user=self.user,
                target_user=target,
                interaction_type=InteractionHistory.LIKE,
            ).count(),
            1,
        )
