"""Aides de test du back-office."""

from __future__ import annotations

import time
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import TestCase

from backoffice import roles, session as bo_session

PASSWORD = 'Str0ng-Test-Pass!'


def make_staff(email='staff@example.test', groups=(), *, is_staff=True, is_active=True,
               is_superuser=False, password=PASSWORD):
    """Crée un utilisateur et l'ajoute aux groupes demandés (créés au besoin)."""
    roles.ensure_backoffice_groups()
    User = get_user_model()
    user = User.objects.create_user(
        email=email, password=password, display_name='Staff Tester',
        birth_date=date(1990, 1, 1), is_staff=is_staff, is_active=is_active,
        is_superuser=is_superuser, email_verified=True,
    )
    for name in groups:
        group, _ = Group.objects.get_or_create(name=name)
        user.groups.add(group)
    return user


def login_staff(client, user, *, mfa=True, idle_seconds=0, session_age_seconds=0):
    """Pose une session back-office authentifiée *sans* passer par le TOTP.

    ``mfa=False`` simule une session sans preuve MFA. ``idle_seconds`` et
    ``session_age_seconds`` vieillissent la session pour tester les expirations.
    La vraie connexion (mot de passe + TOTP) est testée de bout en bout par module.
    """
    client.force_login(user)
    if mfa:
        now = int(time.time())
        session = client.session
        session[bo_session.KEY_AUTH_AT] = now - session_age_seconds
        session[bo_session.KEY_MFA_AT] = now
        session[bo_session.KEY_LAST_SEEN] = now - idle_seconds
        session.save()
    return client


class BackofficeTestCase(TestCase):
    """Isole le cache (compteurs de verrouillage) entre les tests.

    Le français est la langue par défaut du back-office: les tests qui comparent
    des textes demandent l'anglais (msgids) via ``Accept-Language``.
    """

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)
        self.client = self.client_class(HTTP_ACCEPT_LANGUAGE='en')
