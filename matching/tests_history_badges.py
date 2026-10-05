"""Phase 5 contracts for histories and participant-specific match badges."""

from datetime import date

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from matching.models import InteractionHistory, Match


User = get_user_model()


class HistoryAndBadgeContractTests(APITestCase):
    def setUp(self):
        self.owner = self._user('owner', 'Owner')
        self.lea = self._user('lea', 'Léa')
        self.zoe = self._user('zoe', 'Zoé')
        self.client.force_authenticate(self.owner)

    def _user(self, slug, display_name):
        return User.objects.create_user(
            email=f'{slug}@example.test',
            password='testpass123',
            display_name=display_name,
            birth_date=date(1990, 1, 1),
            email_verified=True,
            is_active=True,
        )

    def _interaction(self, target, interaction_type=InteractionHistory.LIKE):
        return InteractionHistory.objects.create(
            user=self.owner,
            target_user=target,
            interaction_type=interaction_type,
        )

    def _match(self, other):
        return Match.objects.create(user1=self.owner, user2=other)

    def test_history_search_is_accent_insensitive_and_match_filter_is_explicit(self):
        lea_like = self._interaction(self.lea)
        self._interaction(self.zoe)
        match = self._match(self.zoe)

        search = self.client.get(
            '/api/v1/discovery/interactions/my-likes', {'q': 'lea'}
        )
        self.assertEqual(search.status_code, status.HTTP_200_OK)
        self.assertEqual(search.data['count'], 1)
        self.assertEqual(search.data['results'][0]['id'], str(lea_like.id))

        matched = self.client.get(
            '/api/v1/discovery/interactions/my-likes',
            {'match_state': 'matched'},
        )
        self.assertEqual(matched.status_code, status.HTTP_200_OK)
        self.assertEqual(matched.data['count'], 1)
        self.assertEqual(matched.data['results'][0]['match_id'], str(match.id))
        self.assertFalse(matched.data['results'][0]['can_revoke'])

        unmatched = self.client.get(
            '/api/v1/discovery/interactions/my-likes',
            {'match_state': 'unmatched'},
        )
        self.assertEqual(unmatched.status_code, status.HTTP_200_OK)
        self.assertEqual(unmatched.data['count'], 1)
        self.assertEqual(unmatched.data['results'][0]['id'], str(lea_like.id))
        self.assertTrue(unmatched.data['results'][0]['can_revoke'])

    def test_bulk_revoke_is_atomic_when_one_selected_like_has_an_active_match(self):
        revocable = self._interaction(self.lea)
        protected = self._interaction(self.zoe)
        self._match(self.zoe)

        response = self.client.post(
            '/api/v1/discovery/interactions/revoke-bulk',
            {
                'history_type': 'likes',
                'interaction_ids': [str(revocable.id), str(protected.id)],
                'select_all': False,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['error'], 'bulk_revoke_not_possible')
        self.assertEqual(len(response.data['reasons']), 1)
        self.assertEqual(response.data['reasons'][0]['interaction_id'], str(protected.id))
        self.assertEqual(
            response.data['reasons'][0]['profile_user_id'], str(self.zoe.id)
        )
        revocable.refresh_from_db()
        protected.refresh_from_db()
        self.assertFalse(revocable.is_revoked)
        self.assertFalse(protected.is_revoked)

    def test_select_all_bulk_revoke_applies_the_active_query_server_side(self):
        lea_like = self._interaction(self.lea)
        zoe_like = self._interaction(self.zoe)

        response = self.client.post(
            '/api/v1/discovery/interactions/revoke-bulk',
            {
                'history_type': 'likes',
                'select_all': True,
                'q': 'lea',
                'match_state': 'all',
                'include_revoked': False,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['revoked_count'], 1)
        lea_like.refresh_from_db()
        zoe_like.refresh_from_db()
        self.assertTrue(lea_like.is_revoked)
        self.assertFalse(zoe_like.is_revoked)

    def test_select_all_excludes_likes_that_require_match_deletion(self):
        revocable = self._interaction(self.lea)
        protected = self._interaction(self.zoe)
        self._match(self.zoe)

        listing = self.client.get('/api/v1/discovery/interactions/my-likes')
        self.assertEqual(listing.data['count'], 2)
        self.assertEqual(listing.data['selectable_count'], 1)

        response = self.client.post(
            '/api/v1/discovery/interactions/revoke-bulk',
            {'history_type': 'likes', 'select_all': True},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['revoked_count'], 1)
        revocable.refresh_from_db()
        protected.refresh_from_db()
        self.assertTrue(revocable.is_revoked)
        self.assertFalse(protected.is_revoked)

    def test_match_seen_state_and_badge_are_independent_per_participant(self):
        match = self._match(self.lea)

        owner_count = self.client.get('/api/v1/matches/unseen-count/')
        self.assertEqual(owner_count.status_code, status.HTTP_200_OK)
        self.assertEqual(owner_count.data['unseen_count'], 1)

        self.client.force_authenticate(self.zoe)
        denied = self.client.put(
            '/api/v1/matches/seen/',
            {'match_ids': [str(match.id)]},
            format='json',
        )
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_authenticate(self.owner)

        seen = self.client.put(
            '/api/v1/matches/seen/',
            {'match_ids': [str(match.id)]},
            format='json',
        )
        self.assertEqual(seen.status_code, status.HTTP_200_OK)
        self.assertEqual(seen.data['seen_count'], 1)
        self.assertEqual(seen.data['unseen_count'], 0)

        self.client.force_authenticate(self.lea)
        other_count = self.client.get('/api/v1/matches/unseen-count/')
        self.assertEqual(other_count.status_code, status.HTTP_200_OK)
        self.assertEqual(other_count.data['unseen_count'], 1)

        listing = self.client.get('/api/v1/matches/')
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertTrue(listing.data['results'][0]['is_new'])

        match.refresh_from_db()
        self.assertIsNotNone(match.user1_seen_at)
        self.assertIsNone(match.user2_seen_at)
