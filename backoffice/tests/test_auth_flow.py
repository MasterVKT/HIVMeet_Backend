"""Étape 1 de connexion (mot de passe), verrouillage, CSRF, déconnexion."""

import json

from django.test import Client, override_settings
from django.urls import reverse

from backoffice import roles, session as bo_session
from backoffice.models import StaffAuditLog

from .helpers import PASSWORD, BackofficeTestCase, login_staff, make_staff

GENERIC = 'Invalid credentials or access not permitted.'


class LoginPageTests(BackofficeTestCase):
    def test_login_page_renders(self):
        response = self.client.get(reverse('backoffice:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="password"')

    def test_root_redirects_into_backoffice(self):
        response = self.client.get('/')
        self.assertRedirects(response, '/backoffice/', fetch_redirect_response=False)

    def test_anonymous_home_redirects_to_login(self):
        response = self.client.get(reverse('backoffice:home'))
        self.assertRedirects(response, reverse('backoffice:login'), fetch_redirect_response=False)

    def test_malformed_form_is_rejected_generically(self):
        response = self.client.post(reverse('backoffice:login'), {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.context['error'], GENERIC)


class PasswordStepTests(BackofficeTestCase):
    def post(self, email, password, client=None):
        return (client or self.client).post(
            reverse('backoffice:login'), {'email': email, 'password': password},
        )

    def assert_generic_refusal(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['error'], GENERIC)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertNotIn(bo_session.KEY_PENDING_UID, self.client.session)

    def test_wrong_password_is_generic_and_audited(self):
        make_staff(groups=[roles.GROUP_ADMIN])
        self.assert_generic_refusal(self.post('staff@example.test', 'wrong'))
        entry = StaffAuditLog.objects.get(action='auth.login_failed')
        self.assertEqual(entry.metadata['reason_code'], 'bad_credentials')

    def test_unknown_email_gets_the_same_response_as_wrong_password(self):
        make_staff(groups=[roles.GROUP_ADMIN])
        known = self.post('staff@example.test', 'wrong')
        unknown = self.post('nobody@example.test', 'wrong')
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.context['error'], unknown.context['error'])

    def test_non_staff_with_valid_password_is_refused(self):
        make_staff(email='user@example.test', is_staff=False)
        self.assert_generic_refusal(self.post('user@example.test', PASSWORD))
        self.assertEqual(StaffAuditLog.objects.get().metadata['reason_code'], 'not_staff')

    def test_inactive_staff_is_refused(self):
        make_staff(groups=[roles.GROUP_ADMIN], is_active=False)
        self.assert_generic_refusal(self.post('staff@example.test', PASSWORD))

    def test_staff_without_group_is_refused(self):
        make_staff()
        self.assert_generic_refusal(self.post('staff@example.test', PASSWORD))
        self.assertEqual(StaffAuditLog.objects.get().metadata['reason_code'], 'no_group')

    def test_superuser_without_group_is_refused(self):
        make_staff(is_superuser=True)
        self.assert_generic_refusal(self.post('staff@example.test', PASSWORD))

    def test_valid_password_is_pending_not_authenticated(self):
        user = make_staff(groups=[roles.GROUP_MODERATOR])
        response = self.post('STAFF@example.test ', PASSWORD)
        self.assertRedirects(response, reverse('backoffice:mfa'), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(self.client.session[bo_session.KEY_PENDING_UID], str(user.pk))
        entry = StaffAuditLog.objects.get(action='auth.password_ok')
        self.assertEqual(entry.actor, user)
        # Fail-closed: sans étape TOTP (Phase 2) aucune page protégée n'est atteignable.
        home = self.client.get(reverse('backoffice:home'))
        self.assertRedirects(home, reverse('backoffice:login'), fetch_redirect_response=False)

    def test_password_step_rotates_the_session_key(self):
        make_staff(groups=[roles.GROUP_ADMIN])
        session = self.client.session
        session['probe'] = 1
        session.save()
        before = session.session_key
        self.post('staff@example.test', PASSWORD)
        self.assertNotEqual(before, self.client.session.session_key)

    def test_mfa_step_is_unavailable_and_clears_pending(self):
        make_staff(groups=[roles.GROUP_ADMIN])
        self.post('staff@example.test', PASSWORD)
        response = self.client.get(reverse('backoffice:mfa'))
        # 403 (pas 5xx): Django ne sauvegarde pas la session sur une réponse 5xx.
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertNotIn(bo_session.KEY_PENDING_UID, self.client.session)
        again = self.client.get(reverse('backoffice:mfa'))
        self.assertRedirects(again, reverse('backoffice:login'), fetch_redirect_response=False)

    def test_mfa_without_pending_redirects_to_login(self):
        response = self.client.get(reverse('backoffice:mfa'))
        self.assertRedirects(response, reverse('backoffice:login'), fetch_redirect_response=False)

    def test_failure_audit_never_contains_the_email_or_password(self):
        make_staff(groups=[roles.GROUP_ADMIN])
        self.post('staff@example.test', 'wrong-password-123')
        dump = json.dumps(list(StaffAuditLog.objects.values(
            'action', 'actor_ref', 'target_type', 'target_id', 'reason', 'metadata', 'ip_hash',
        )), default=str)
        self.assertNotIn('staff@example.test', dump)
        self.assertNotIn('wrong-password-123', dump)
        self.assertNotIn('127.0.0.1', dump)


class LockoutTests(BackofficeTestCase):
    def attempt(self, email, password):
        return self.client.post(reverse('backoffice:login'), {'email': email, 'password': password})

    def test_account_lockout_blocks_even_the_correct_password(self):
        make_staff(groups=[roles.GROUP_ADMIN])
        for _ in range(5):
            self.assertEqual(self.attempt('staff@example.test', 'wrong').status_code, 200)
        blocked = self.attempt('staff@example.test', PASSWORD)
        self.assertEqual(blocked.status_code, 429)
        self.assertNotIn(bo_session.KEY_PENDING_UID, self.client.session)
        # Verrouillage audité une seule fois, pas à chaque tentative bloquée.
        self.attempt('staff@example.test', PASSWORD)
        self.assertEqual(StaffAuditLog.objects.filter(action='auth.locked').count(), 1)

    def test_lockout_does_not_depend_on_the_account_existing(self):
        for _ in range(5):
            self.attempt('ghost@example.test', 'wrong')
        self.assertEqual(self.attempt('ghost@example.test', 'wrong').status_code, 429)

    @override_settings(BACKOFFICE_LOGIN_IP_LIMIT=3)
    def test_ip_lockout_across_different_accounts(self):
        make_staff(groups=[roles.GROUP_ADMIN])
        for index in range(3):
            self.attempt(f'ghost{index}@example.test', 'wrong')
        self.assertEqual(self.attempt('staff@example.test', PASSWORD).status_code, 429)

    def test_password_success_resets_the_account_counter(self):
        make_staff(groups=[roles.GROUP_ADMIN])
        for _ in range(4):
            self.attempt('staff@example.test', 'wrong')
        self.assertEqual(self.attempt('staff@example.test', PASSWORD).status_code, 302)
        for _ in range(4):
            self.attempt('staff@example.test', 'wrong')
        self.assertEqual(self.attempt('staff@example.test', PASSWORD).status_code, 302)


class CsrfAndLogoutTests(BackofficeTestCase):
    def test_login_post_without_csrf_token_is_rejected(self):
        strict = Client(enforce_csrf_checks=True)
        response = strict.post(reverse('backoffice:login'), {'email': 'a@b.test', 'password': 'x'})
        self.assertEqual(response.status_code, 403)

    def test_logout_requires_post(self):
        self.assertEqual(self.client.get(reverse('backoffice:logout')).status_code, 405)

    def test_logout_ends_the_session_and_is_audited(self):
        user = make_staff(groups=[roles.GROUP_ADMIN])
        login_staff(self.client, user)
        response = self.client.post(reverse('backoffice:logout'))
        self.assertRedirects(response, reverse('backoffice:login'), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTrue(StaffAuditLog.objects.filter(action='auth.logout', actor=user).exists())
