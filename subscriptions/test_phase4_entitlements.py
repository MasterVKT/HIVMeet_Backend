from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.serializers import UserSerializer
from matching.daily_likes_service import DailyLikesService
from matching.models import DailyLikeLimit, InteractionHistory, Like
from matching.services import MatchingService
from subscriptions.models import Subscription, SubscriptionPlan
from subscriptions.utils import (
    check_feature_availability,
    invalidate_premium_status_cache,
    is_premium_user,
)


class PremiumEntitlementActivationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email='phase4-user@example.test',
            password='test-password',
            display_name='Phase Four',
            birth_date=date(1990, 1, 1),
        )
        self.target = user_model.objects.create_user(
            email='phase4-target@example.test',
            password='test-password',
            display_name='Target',
            birth_date=date(1991, 1, 1),
        )
        self.plan = SubscriptionPlan.objects.create(
            plan_id='phase4-monthly',
            name='Premium monthly',
            name_en='Premium monthly',
            name_fr='Premium mensuel',
            description='Phase 4 test plan',
            description_en='Phase 4 test plan',
            description_fr='Offre de test phase 4',
            price='7.99',
            currency='EUR',
            billing_interval=SubscriptionPlan.INTERVAL_MONTH,
            unlimited_likes=True,
            can_see_likers=True,
            can_rewind=True,
            daily_super_likes_count=5,
            media_messaging_enabled=True,
            audio_video_calls_enabled=True,
        )
        now = timezone.now()
        self.subscription = Subscription.objects.create(
            subscription_id='phase4-subscription',
            user=self.user,
            plan=self.plan,
            status=Subscription.STATUS_ACTIVE,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            super_likes_remaining=5,
        )
        self.user.refresh_from_db()
        invalidate_premium_status_cache(self.user)

    def test_serialized_user_immediately_exposes_active_premium_expiry(self):
        data = UserSerializer(self.user).data

        self.assertTrue(data['is_premium'])
        self.assertIsNotNone(data['premium_until'])

    def test_all_declared_entitlements_are_available_in_same_session(self):
        self.assertTrue(is_premium_user(self.user))
        self.assertEqual(DailyLikesService.get_likes_remaining(self.user), -1)
        self.assertEqual(DailyLikesService.get_super_likes_remaining(self.user), 5)
        daily_limit, _ = DailyLikeLimit.objects.get_or_create(
            user=self.user,
            date=date.today(),
        )
        self.assertTrue(daily_limit.has_likes_remaining())
        self.assertTrue(daily_limit.has_super_likes_remaining())
        for feature in (
            'unlimited_likes',
            'see_likers',
            'rewind',
            'super_like',
            'media_messaging',
            'calls',
        ):
            with self.subTest(feature=feature):
                self.assertTrue(
                    check_feature_availability(self.user, feature)['available']
                )

    def test_rewind_restores_profile_without_refunding_consumed_swipe(self):
        Like.objects.create(from_user=self.user, to_user=self.target)
        history = InteractionHistory.objects.create(
            user=self.user,
            target_user=self.target,
            interaction_type=InteractionHistory.LIKE,
        )
        self.target.profile.likes_received = 1
        self.target.profile.save(update_fields=['likes_received'])

        self.assertEqual(DailyLikesService.count_swipes_today(self.user), 1)
        success, profile, error = MatchingService.rewind_last_action(self.user)

        self.assertTrue(success, error)
        self.assertEqual(profile['user_id'], str(self.target.id))
        history.refresh_from_db()
        self.assertTrue(history.is_revoked)
        self.assertFalse(
            Like.objects.filter(from_user=self.user, to_user=self.target).exists()
        )
        self.assertEqual(DailyLikesService.count_swipes_today(self.user), 1)
        limit = DailyLikeLimit.objects.get(user=self.user, date=date.today())
        self.assertEqual(limit.rewinds_count, 1)
        limit.rewinds_count = 4
        self.assertTrue(limit.has_rewinds_remaining())
        limit.rewinds_count = 5
        self.assertFalse(limit.has_rewinds_remaining())
        limit.save(update_fields=['rewinds_count'])
        Like.objects.create(from_user=self.user, to_user=self.target)
        InteractionHistory.objects.create(
            user=self.user,
            target_user=self.target,
            interaction_type=InteractionHistory.LIKE,
        )
        success, profile, error = MatchingService.rewind_last_action(self.user)
        self.assertFalse(success)
        self.assertIsNone(profile)
        self.assertIn('limit', error.lower())

    def test_sixth_super_like_is_rejected_even_after_prior_rewinds(self):
        for _ in range(5):
            InteractionHistory.objects.create(
                user=self.user,
                target_user=self.target,
                interaction_type=InteractionHistory.SUPER_LIKE,
                is_revoked=True,
                revoked_at=timezone.now(),
            )

        self.assertEqual(DailyLikesService.get_super_likes_remaining(self.user), 0)
        allowed, error = DailyLikesService.can_user_super_like(self.user)
        self.assertFalse(allowed)
        self.assertTrue(str(error))

    def test_expired_raw_flag_never_grants_paid_features(self):
        self.user.is_premium = True
        self.user.premium_until = timezone.now() - timedelta(seconds=1)
        self.user.save(update_fields=['is_premium', 'premium_until'])
        invalidate_premium_status_cache(self.user)

        self.assertFalse(is_premium_user(self.user))
        self.assertFalse(
            check_feature_availability(self.user, 'media_messaging')['available']
        )
        self.assertEqual(DailyLikesService.get_likes_remaining(self.user), 10)
        self.assertEqual(DailyLikesService.get_super_likes_remaining(self.user), 0)
        daily_limit, _ = DailyLikeLimit.objects.get_or_create(
            user=self.user,
            date=date.today(),
        )
        self.assertTrue(daily_limit.has_likes_remaining())
        self.assertFalse(daily_limit.has_super_likes_remaining())
