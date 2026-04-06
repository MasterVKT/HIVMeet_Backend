from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from matching.daily_likes_service import DailyLikesService
from matching.models import InteractionHistory, Like
from matching.services import MatchingService, RecommendationService


User = get_user_model()


class DiscoveryFilterDeterministicTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _create_user_with_profile(
        self,
        email,
        display_name,
        birth_year,
        gender,
        *,
        genders_sought=None,
        relationship_types_sought=None,
        age_min=18,
        age_max=99,
        distance_max_km=100,
        latitude=48.8566,
        longitude=2.3522,
        email_verified=True,
        is_active=True,
        is_verified=False,
        online_minutes_ago=1,
    ):
        user = User.objects.create_user(
            email=email,
            password="testpass123",
            display_name=display_name,
            birth_date=date(birth_year, 1, 1),
        )
        user.email_verified = email_verified
        user.is_active = is_active
        user.is_verified = is_verified
        user.last_active = timezone.now() - timedelta(minutes=online_minutes_ago)
        user.save(update_fields=["email_verified", "is_active", "is_verified", "last_active"])

        profile = user.profile
        profile.gender = gender
        profile.genders_sought = genders_sought if genders_sought is not None else []
        profile.relationship_types_sought = (
            relationship_types_sought if relationship_types_sought is not None else []
        )
        profile.age_min_preference = age_min
        profile.age_max_preference = age_max
        profile.distance_max_km = distance_max_km
        profile.latitude = latitude
        profile.longitude = longitude
        profile.is_hidden = False
        profile.allow_profile_in_discovery = True
        profile.bio = "bio"
        profile.city = "Paris"
        profile.country = "France"
        profile.save()
        return user

    def test_age_filter_inclusive_boundaries(self):
        seeker = self._create_user_with_profile(
            "seeker.age@test.com",
            "Seeker Age",
            1994,
            "male",
            genders_sought=["female"],
            age_min=25,
            age_max=35,
        )
        in_min = self._create_user_with_profile(
            "min.age@test.com",
            "Min Age",
            timezone.now().year - 25,
            "female",
            genders_sought=["male"],
        )
        in_max = self._create_user_with_profile(
            "max.age@test.com",
            "Max Age",
            timezone.now().year - 35,
            "female",
            genders_sought=["male"],
        )
        below = self._create_user_with_profile(
            "below.age@test.com",
            "Below Age",
            timezone.now().year - 24,
            "female",
            genders_sought=["male"],
        )
        above = self._create_user_with_profile(
            "above.age@test.com",
            "Above Age",
            timezone.now().year - 36,
            "female",
            genders_sought=["male"],
        )

        result_ids = {p.user_id for p in RecommendationService.get_recommendations(seeker, limit=100)}

        self.assertIn(in_min.id, result_ids)
        self.assertIn(in_max.id, result_ids)
        self.assertNotIn(below.id, result_ids)
        self.assertNotIn(above.id, result_ids)

    def test_gender_filter_and_mutual_gender_compatibility(self):
        seeker = self._create_user_with_profile(
            "seeker.gender@test.com",
            "Seeker Gender",
            1992,
            "male",
            genders_sought=["female"],
        )
        compatible = self._create_user_with_profile(
            "compatible.gender@test.com",
            "Compatible",
            1993,
            "female",
            genders_sought=["male"],
        )
        not_mutual = self._create_user_with_profile(
            "notmutual.gender@test.com",
            "Not Mutual",
            1991,
            "female",
            genders_sought=["female"],
        )

        result_ids = {p.user_id for p in RecommendationService.get_recommendations(seeker, limit=100)}

        self.assertIn(compatible.id, result_ids)
        self.assertNotIn(not_mutual.id, result_ids)

    def test_distance_filter_includes_boundary_and_excludes_outside(self):
        seeker = self._create_user_with_profile(
            "seeker.distance@test.com",
            "Seeker Distance",
            1990,
            "male",
            genders_sought=["female"],
            distance_max_km=50,
            latitude=48.8566,
            longitude=2.3522,
        )
        near = self._create_user_with_profile(
            "near.distance@test.com",
            "Near",
            1992,
            "female",
            genders_sought=["male"],
            latitude=48.9,
            longitude=2.35,
        )
        far = self._create_user_with_profile(
            "far.distance@test.com",
            "Far",
            1992,
            "female",
            genders_sought=["male"],
            latitude=49.7,
            longitude=2.35,
        )

        result_ids = {p.user_id for p in RecommendationService.get_recommendations(seeker, limit=100)}

        self.assertIn(near.id, result_ids)
        self.assertNotIn(far.id, result_ids)

    def test_relationship_types_filter_open_list_and_overlap(self):
        seeker = self._create_user_with_profile(
            "seeker.relationship@test.com",
            "Seeker Relationship",
            1991,
            "male",
            genders_sought=["female"],
            relationship_types_sought=["long_term"],
        )
        overlap = self._create_user_with_profile(
            "overlap.relationship@test.com",
            "Overlap",
            1990,
            "female",
            genders_sought=["male"],
            relationship_types_sought=["long_term", "casual"],
        )
        open_target = self._create_user_with_profile(
            "open.relationship@test.com",
            "Open",
            1990,
            "female",
            genders_sought=["male"],
            relationship_types_sought=[],
        )
        no_overlap = self._create_user_with_profile(
            "nooverlap.relationship@test.com",
            "No Overlap",
            1990,
            "female",
            genders_sought=["male"],
            relationship_types_sought=["friendship"],
        )

        result_ids = {p.user_id for p in RecommendationService.get_recommendations(seeker, limit=100)}

        self.assertIn(overlap.id, result_ids)
        self.assertIn(open_target.id, result_ids)
        self.assertNotIn(no_overlap.id, result_ids)

    def test_verified_and_online_filters_combination(self):
        seeker = self._create_user_with_profile(
            "seeker.flags@test.com",
            "Seeker Flags",
            1990,
            "male",
            genders_sought=["female"],
        )
        seeker.profile.verified_only = True
        seeker.profile.online_only = True
        seeker.profile.save(update_fields=["verified_only", "online_only"])

        included = self._create_user_with_profile(
            "included.flags@test.com",
            "Included",
            1990,
            "female",
            genders_sought=["male"],
            is_verified=True,
            online_minutes_ago=1,
        )
        not_verified = self._create_user_with_profile(
            "notverified.flags@test.com",
            "Not Verified",
            1990,
            "female",
            genders_sought=["male"],
            is_verified=False,
            online_minutes_ago=1,
        )
        offline = self._create_user_with_profile(
            "offline.flags@test.com",
            "Offline",
            1990,
            "female",
            genders_sought=["male"],
            is_verified=True,
            online_minutes_ago=15,
        )

        result_ids = {p.user_id for p in RecommendationService.get_recommendations(seeker, limit=100)}

        self.assertIn(included.id, result_ids)
        self.assertNotIn(not_verified.id, result_ids)
        self.assertNotIn(offline.id, result_ids)

    def test_exclusions_self_blocked_and_interacted(self):
        seeker = self._create_user_with_profile(
            "seeker.exclude@test.com",
            "Seeker Exclude",
            1990,
            "male",
            genders_sought=["female"],
        )
        blocked_by_seeker = self._create_user_with_profile(
            "blockedbyseeker.exclude@test.com",
            "Blocked By Seeker",
            1990,
            "female",
            genders_sought=["male"],
        )
        blocks_seeker = self._create_user_with_profile(
            "blocksseeker.exclude@test.com",
            "Blocks Seeker",
            1990,
            "female",
            genders_sought=["male"],
        )
        interacted = self._create_user_with_profile(
            "interacted.exclude@test.com",
            "Interacted",
            1990,
            "female",
            genders_sought=["male"],
        )
        visible = self._create_user_with_profile(
            "visible.exclude@test.com",
            "Visible",
            1990,
            "female",
            genders_sought=["male"],
        )

        seeker.blocked_users.add(blocked_by_seeker)
        blocks_seeker.blocked_users.add(seeker)
        InteractionHistory.create_or_reactivate(
            user=seeker,
            target_user=interacted,
            interaction_type=InteractionHistory.DISLIKE,
        )

        result_ids = {p.user_id for p in RecommendationService.get_recommendations(seeker, limit=100)}

        self.assertNotIn(seeker.id, result_ids)
        self.assertNotIn(blocked_by_seeker.id, result_ids)
        self.assertNotIn(blocks_seeker.id, result_ids)
        self.assertNotIn(interacted.id, result_ids)
        self.assertIn(visible.id, result_ids)

    def test_filters_endpoint_validates_and_normalizes_all_keyword(self):
        user = self._create_user_with_profile(
            "filters.endpoint@test.com",
            "Filters Endpoint",
            1990,
            "male",
            genders_sought=["female"],
            relationship_types_sought=["long_term"],
        )
        self.client.force_authenticate(user=user)

        response = self.client.put(
            "/api/v1/discovery/filters",
            {
                "age_min": 24,
                "age_max": 40,
                "distance_max_km": 60,
                "genders": ["ALL"],
                "relationship_types": ["all"],
                "verified_only": True,
                "online_only": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["filters"]["genders"], [])
        self.assertEqual(response.data["filters"]["relationship_types"], [])

        user.profile.refresh_from_db()
        self.assertEqual(user.profile.genders_sought, [])
        self.assertEqual(user.profile.relationship_types_sought, [])

    def test_filters_endpoint_rejects_invalid_enum_values(self):
        user = self._create_user_with_profile(
            "filters.invalid@test.com",
            "Filters Invalid",
            1990,
            "male",
            genders_sought=["female"],
        )
        self.client.force_authenticate(user=user)

        response = self.client.put(
            "/api/v1/discovery/filters",
            {
                "genders": ["invalid_gender"],
                "relationship_types": ["unknown_type"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("details", response.data)
        self.assertIn("genders", response.data["details"])
        self.assertIn("relationship_types", response.data["details"])


class DailyLikesDeterministicTests(TestCase):
    def _create_user(self, email, birth_year, is_premium=False):
        user = User.objects.create_user(
            email=email,
            password="testpass123",
            display_name=email.split("@")[0],
            birth_date=date(birth_year, 1, 1),
        )
        user.email_verified = True
        user.is_active = True
        user.is_premium = is_premium
        user.save(update_fields=["email_verified", "is_active", "is_premium"])

        profile = user.profile
        profile.gender = "male" if "male" in email else "female"
        profile.genders_sought = []
        profile.relationship_types_sought = []
        profile.save()
        return user

    def test_free_user_super_like_limit_is_one_per_day(self):
        free_user = self._create_user("male.free@test.com", 1990, is_premium=False)
        target = self._create_user("female.free.target@test.com", 1991, is_premium=False)

        can_super_like, _ = DailyLikesService.can_user_super_like(free_user)
        self.assertTrue(can_super_like)

        success, _, _, _ = MatchingService.like_profile(
            from_user=free_user,
            to_user=target,
            is_super_like=True,
        )
        self.assertTrue(success)

        self.assertEqual(DailyLikesService.get_super_likes_remaining(free_user), 0)
        can_super_like, _ = DailyLikesService.can_user_super_like(free_user)
        self.assertFalse(can_super_like)

    def test_premium_user_super_like_limit_is_five_per_day(self):
        premium_user = self._create_user("male.premium@test.com", 1990, is_premium=True)

        targets = [
            self._create_user(f"female.premium.target{i}@test.com", 1991 + i, is_premium=False)
            for i in range(5)
        ]

        for target in targets:
            success, _, _, _ = MatchingService.like_profile(
                from_user=premium_user,
                to_user=target,
                is_super_like=True,
            )
            self.assertTrue(success)

        self.assertEqual(DailyLikesService.get_super_likes_remaining(premium_user), 0)
        can_super_like, _ = DailyLikesService.can_user_super_like(premium_user)
        self.assertFalse(can_super_like)

    def test_daily_likes_reset_on_new_utc_day(self):
        user = self._create_user("male.reset@test.com", 1990, is_premium=False)
        target = self._create_user("female.reset.target@test.com", 1991, is_premium=False)

        success, _, _, _ = MatchingService.like_profile(
            from_user=user,
            to_user=target,
            is_super_like=False,
        )
        self.assertTrue(success)

        self.assertEqual(DailyLikesService.get_likes_remaining(user), 9)

        like = user.likes_sent.first()
        interaction = InteractionHistory.objects.filter(
            user=user,
            target_user=target,
            interaction_type=InteractionHistory.LIKE,
            is_revoked=False,
        ).first()
        yesterday = timezone.now() - timedelta(days=1)

        Like.objects.filter(id=like.id).update(created_at=yesterday)
        InteractionHistory.objects.filter(id=interaction.id).update(created_at=yesterday)

        self.assertEqual(DailyLikesService.count_likes_today(user), 0)
        self.assertEqual(DailyLikesService.get_likes_remaining(user), 10)
