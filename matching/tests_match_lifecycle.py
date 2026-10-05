from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from matching.models import InteractionHistory, Like, Match
from matching.services import MatchingService


User = get_user_model()


class MatchLifecycleContractTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email='owner@example.test',
            password='testpass123',
            display_name='Owner',
            birth_date=date(1990, 1, 1),
            email_verified=True,
            is_active=True,
        )
        self.other = User.objects.create_user(
            email='other@example.test',
            password='testpass123',
            display_name='Other',
            birth_date=date(1992, 1, 1),
            email_verified=True,
            is_active=True,
        )
        self.stranger = User.objects.create_user(
            email='stranger@example.test',
            password='testpass123',
            display_name='Stranger',
            birth_date=date(1991, 1, 1),
            email_verified=True,
            is_active=True,
        )
        self.client.force_authenticate(self.owner)

    def _create_match(self, status_value=Match.ACTIVE):
        return Match.objects.create(
            user1=self.owner,
            user2=self.other,
            status=status_value,
        )

    def test_unmatch_is_idempotent_and_notifies_both_participants(self):
        match = self._create_match()

        with patch('matching.views_matches.dispatch_group_event') as dispatch:
            response = self.client.delete(f'/api/v1/matches/{match.id}')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        match.refresh_from_db()
        self.assertEqual(match.status, Match.DELETED)
        self.assertEqual(dispatch.call_count, 2)
        self.assertEqual(
            {call.args[0] for call in dispatch.call_args_list},
            {f'user_{self.owner.id}', f'user_{self.other.id}'},
        )

        closed_conversation = self.client.get(
            f'/api/v1/conversations/{match.id}/messages/'
        )
        self.assertEqual(closed_conversation.status_code, status.HTTP_404_NOT_FOUND)

        retry = self.client.delete(f'/api/v1/matches/{match.id}')
        self.assertEqual(retry.status_code, status.HTTP_204_NO_CONTENT)

    def test_unmatch_does_not_disclose_or_modify_another_users_match(self):
        match = self._create_match()
        self.client.force_authenticate(self.stranger)

        response = self.client.delete(f'/api/v1/matches/{match.id}')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        match.refresh_from_db()
        self.assertEqual(match.status, Match.ACTIVE)

    def test_active_match_participant_can_open_hidden_profile_with_user_id(self):
        self._create_match()
        self.other.profile.is_hidden = True
        self.other.profile.allow_profile_in_discovery = False
        self.other.profile.save(
            update_fields=['is_hidden', 'allow_profile_in_discovery']
        )

        response = self.client.get(f'/api/v1/user-profiles/{self.other.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user_id'], str(self.other.id))

        self.client.force_authenticate(self.stranger)
        denied = self.client.get(f'/api/v1/user-profiles/{self.other.id}/')
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)

    def test_matched_like_cannot_be_revoked(self):
        self._create_match()
        interaction = InteractionHistory.objects.create(
            user=self.owner,
            target_user=self.other,
            interaction_type=InteractionHistory.LIKE,
        )

        response = self.client.post(
            f'/api/v1/discovery/interactions/{interaction.id}/revoke'
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['code'], 'cannot_revoke_match')
        interaction.refresh_from_db()
        self.assertFalse(interaction.is_revoked)

    def test_rewind_refuses_to_delete_an_active_match(self):
        match = self._create_match()
        like = Like.objects.create(from_user=self.owner, to_user=self.other)
        InteractionHistory.objects.create(
            user=self.owner,
            target_user=self.other,
            interaction_type=InteractionHistory.LIKE,
        )

        available = {'available': True, 'reason': None}
        with patch(
            'matching.views_discovery.check_feature_availability',
            return_value=available,
        ), patch(
            'subscriptions.utils.check_feature_availability',
            return_value=available,
        ):
            response = self.client.post('/api/v1/discovery/interactions/rewind')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['code'], 'match_exists_use_unmatch')
        self.assertTrue(Like.objects.filter(id=like.id).exists())
        match.refresh_from_db()
        self.assertEqual(match.status, Match.ACTIVE)

    def test_deleted_match_is_never_reactivated_by_existing_mutual_likes(self):
        match = self._create_match(status_value=Match.DELETED)
        Like.objects.create(from_user=self.owner, to_user=self.other)
        Like.objects.create(from_user=self.other, to_user=self.owner)

        success, is_match, _, _ = MatchingService.like_profile(
            self.owner,
            self.other,
        )

        self.assertTrue(success)
        self.assertFalse(is_match)
        match.refresh_from_db()
        self.assertEqual(match.status, Match.DELETED)
