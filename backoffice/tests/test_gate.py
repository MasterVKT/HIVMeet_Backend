"""Barrière d'accès: capacités, MFA/expiration de session, deny by default, en-têtes."""

import time

from django.test import override_settings
from django.urls import reverse

from backoffice import access, roles, session as bo_session
from backoffice.models import StaffAuditLog

from .helpers import BackofficeTestCase, login_staff, make_staff

A, M, S = roles.GROUP_ADMIN, roles.GROUP_MODERATOR, roles.GROUP_SUPPORT
R, K = roles.GROUP_KYC_REVIEWER, roles.GROUP_KYC_SUPERVISOR

# Matrice attendue, écrite *indépendamment* du code (copie du plan approuvé).
EXPECTED = {
    access.DASHBOARD: {A, M, S, R, K},
    access.USERS_VIEW: {A, M, S},
    access.USERS_VIEW_PII: {A},
    access.USERS_DEACTIVATE: {A, M},
    access.USERS_REACTIVATE: {A},
    access.STAFF_MANAGE: {A},
    access.REPORTS_MANAGE: {A, M},
    access.MODERATION_FEED: {A, M},
    access.MODERATION_PHOTOS: {A, M},
    access.CMS_EDIT: {A, M},
    access.PAYMENTS_VIEW: {A, S},
    access.PAYMENTS_RECONCILE: {A, S},
    access.PAYMENTS_FULFIL_DEFERRED: {A},
    access.GDPR_VIEW: {A, S},
    access.GDPR_ACT: {A},
    access.AUDIT_VIEW: {A},
    access.KYC_REVIEW: {R, K},
    access.KYC_SUPERVISE: {K},
}


class CapabilityMatrixTests(BackofficeTestCase):
    def test_matrix_covers_exactly_the_expected_capabilities(self):
        self.assertEqual(set(access.CAPABILITY_GROUPS), set(EXPECTED))

    def test_each_group_gets_exactly_its_capabilities(self):
        for group in roles.ALL_GROUPS:
            user = make_staff(email=f'{group}@example.test', groups=[group])
            for capability, allowed in EXPECTED.items():
                with self.subTest(group=group, capability=capability):
                    self.assertEqual(access.has_capability(user, capability), group in allowed)

    def test_superuser_without_group_has_no_implicit_access(self):
        user = make_staff(is_superuser=True)
        for capability in EXPECTED:
            with self.subTest(capability=capability):
                self.assertFalse(access.has_capability(user, capability))

    def test_inactive_or_non_staff_member_of_a_group_has_nothing(self):
        for kwargs in ({'is_active': False}, {'is_staff': False}):
            user = make_staff(email=f'x{len(kwargs)}{list(kwargs)[0]}@example.test', groups=[A], **kwargs)
            self.assertFalse(access.has_capability(user, access.DASHBOARD))

    def test_unknown_capability_is_denied(self):
        user = make_staff(groups=[A])
        self.assertFalse(access.has_capability(user, 'does.not.exist'))


class GateViewTests(BackofficeTestCase):
    def test_every_group_reaches_home(self):
        for group in roles.ALL_GROUPS:
            with self.subTest(group=group):
                user = make_staff(email=f'{group}@example.test', groups=[group])
                client = self.client_class()
                login_staff(client, user)
                self.assertEqual(client.get(reverse('backoffice:home')).status_code, 200)

    def test_staff_without_group_is_forbidden_and_audited(self):
        user = make_staff()
        login_staff(self.client, user)
        response = self.client.get(reverse('backoffice:home'))
        self.assertEqual(response.status_code, 403)
        entry = StaffAuditLog.objects.get(action='access.denied')
        self.assertEqual(entry.actor, user)
        self.assertEqual(entry.metadata['capability'], access.DASHBOARD)

    def test_superuser_without_group_is_forbidden_with_a_forged_session(self):
        login_staff(self.client, make_staff(is_superuser=True))
        self.assertEqual(self.client.get(reverse('backoffice:home')).status_code, 403)

    def test_non_staff_with_a_forged_session_is_forbidden(self):
        login_staff(self.client, make_staff(groups=[A], is_staff=False))
        self.assertEqual(self.client.get(reverse('backoffice:home')).status_code, 403)

    def test_inactive_user_session_is_anonymous(self):
        user = make_staff(groups=[A])
        login_staff(self.client, user)
        user.is_active = False
        user.save(update_fields=['is_active'])
        response = self.client.get(reverse('backoffice:home'))
        self.assertRedirects(response, reverse('backoffice:login'), fetch_redirect_response=False)

    def test_session_without_mfa_proof_is_logged_out(self):
        login_staff(self.client, make_staff(groups=[A]), mfa=False)
        response = self.client.get(reverse('backoffice:home'))
        self.assertRedirects(response, reverse('backoffice:login'), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)
        entry = StaffAuditLog.objects.get(action='access.denied')
        self.assertEqual(entry.metadata['reason_code'], 'mfa_required')

    def test_idle_timeout_logs_out(self):
        login_staff(self.client, make_staff(groups=[A]), idle_seconds=901)
        response = self.client.get(reverse('backoffice:home'))
        self.assertRedirects(response, reverse('backoffice:login'), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTrue(StaffAuditLog.objects.filter(action='auth.session_expired').exists())

    def test_absolute_session_cap_logs_out_even_when_active(self):
        login_staff(self.client, make_staff(groups=[A]), session_age_seconds=28801)
        response = self.client.get(reverse('backoffice:home'))
        self.assertRedirects(response, reverse('backoffice:login'), fetch_redirect_response=False)
        self.assertTrue(StaffAuditLog.objects.filter(action='auth.session_expired').exists())

    def test_activity_refreshes_the_idle_clock(self):
        login_staff(self.client, make_staff(groups=[A]), idle_seconds=800)
        self.assertEqual(self.client.get(reverse('backoffice:home')).status_code, 200)
        self.assertLess(time.time() - self.client.session[bo_session.KEY_LAST_SEEN], 5)

    def test_step_up_freshness_window(self):
        now = 10_000
        session = {bo_session.KEY_MFA_AT: now - 299}
        self.assertTrue(bo_session.step_up_fresh(session, now))
        session[bo_session.KEY_MFA_AT] = now - 301
        self.assertFalse(bo_session.step_up_fresh(session, now))
        self.assertFalse(bo_session.step_up_fresh({}, now))


@override_settings(ROOT_URLCONF='backoffice.tests.urls_unclassified')
class DenyByDefaultTests(BackofficeTestCase):
    def test_unclassified_view_is_refused_for_anonymous(self):
        self.assertEqual(self.client.get('/backoffice/forgotten/').status_code, 403)

    def test_unclassified_view_is_refused_even_for_a_full_admin(self):
        login_staff(self.client, make_staff(groups=[A]))
        response = self.client.get('/backoffice/forgotten/')
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, 'should never be served', status_code=403)


class SecurityHeaderTests(BackofficeTestCase):
    def assert_hardened(self, response):
        csp = response['Content-Security-Policy']
        for directive in ("default-src 'self'", "script-src 'self'", "style-src 'self'",
                          "frame-ancestors 'none'", "base-uri 'none'", "form-action 'self'"):
            self.assertIn(directive, csp)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response['Referrer-Policy'], 'same-origin')
        self.assertIn('noindex', response['X-Robots-Tag'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['X-Frame-Options'], 'DENY')

    def test_headers_on_login_denied_and_mfa_pages(self):
        self.assert_hardened(self.client.get(reverse('backoffice:login')))
        login_staff(self.client, make_staff(groups=[]))
        self.assert_hardened(self.client.get(reverse('backoffice:home')))
        self.assert_hardened(self.client.get(reverse('backoffice:logout')))

    def test_pages_have_no_inline_script_or_style(self):
        user = make_staff(groups=[A])
        pages = [self.client.get(reverse('backoffice:login'))]
        client = self.client_class()
        login_staff(client, user)
        pages.append(client.get(reverse('backoffice:home')))
        for page in pages:
            html = page.content.decode()
            self.assertNotIn('<script', html)
            self.assertNotIn('<style', html)
            self.assertNotIn(' style=', html)
            self.assertNotIn('onclick=', html)
            self.assertNotIn('http://', html.replace('http://www.w3.org', ''))
            self.assertNotIn('https://', html)

    def test_session_and_csrf_cookies_are_scoped_and_strict(self):
        response = self.client.get(reverse('backoffice:login'))
        csrf = response.cookies['bo_csrftoken']
        self.assertEqual(csrf['samesite'], 'Strict')
        self.assertEqual(csrf['path'], '/backoffice/')
        self.assertTrue(csrf['httponly'])
        user = make_staff(groups=[A])
        response = self.client.post(reverse('backoffice:login'), {
            'email': user.email, 'password': 'Str0ng-Test-Pass!',
        })
        session_cookie = response.cookies['bo_sessionid']
        self.assertEqual(session_cookie['samesite'], 'Strict')
        self.assertEqual(session_cookie['path'], '/backoffice/')
        self.assertTrue(session_cookie['httponly'])
