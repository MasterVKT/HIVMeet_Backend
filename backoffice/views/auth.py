"""Connexion du back-office — étape 1 (mot de passe).

Aucun ``login()`` n'est appelé ici: l'utilisateur n'est authentifié qu'après la
vérification TOTP (Phase 2). Tant que cette étape n'existe pas, la page ``mfa``
refuse l'accès (fail-closed).
"""

from __future__ import annotations

import time

from django.conf import settings
from django.contrib.auth import authenticate, logout
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

from .. import audit, lockout, roles, session as bo_session
from ..access import public_view
from ..forms import LoginForm

ACCOUNT_KIND = 'login-account'
IP_KIND = 'login-ip'


def _render_login(request, form, *, error=None, status=200):
    return render(request, 'backoffice/login.html', {'form': form, 'error': error}, status=status)


@public_view
@require_http_methods(['GET', 'POST'])
def login_view(request):
    if request.method == 'GET':
        return _render_login(request, LoginForm())

    form = LoginForm(request.POST)
    if not form.is_valid():
        return _render_login(request, LoginForm(), error=_('Invalid credentials or access not permitted.'), status=400)

    email = form.cleaned_data['email'].strip().lower()
    ip = lockout.client_ip(request)
    account_limit = settings.BACKOFFICE_LOGIN_ACCOUNT_LIMIT
    ip_limit = settings.BACKOFFICE_LOGIN_IP_LIMIT
    window = settings.BACKOFFICE_LOCKOUT_WINDOW_SECONDS

    if lockout.is_locked(ACCOUNT_KIND, email, account_limit) or lockout.is_locked(IP_KIND, ip, ip_limit):
        # Pas d'audit par tentative bloquée: le verrouillage est audité une seule fois.
        return _render_login(
            request, LoginForm(), error=_('Too many attempts. Try again later.'), status=429,
        )

    user = authenticate(request, email=email, password=form.cleaned_data['password'])
    reason = None
    if user is None:
        reason = 'bad_credentials'
    elif not (user.is_active and user.is_staff):
        reason = 'not_staff'
    elif not roles.user_groups(user):
        reason = 'no_group'

    if reason:
        account_count = lockout.register_failure(ACCOUNT_KIND, email, window)
        ip_count = lockout.register_failure(IP_KIND, ip, window)
        identifier_hash = lockout.hash_identifier(email)
        audit.record(
            action='auth.login_failed', request=request,
            metadata={'reason_code': reason, 'identifier_hash': identifier_hash},
        )
        if account_count == account_limit or ip_count == ip_limit:
            audit.record(
                action='auth.locked', request=request,
                metadata={'kind': 'login', 'identifier_hash': identifier_hash},
            )
        return _render_login(request, LoginForm(), error=_('Invalid credentials or access not permitted.'))

    lockout.clear(ACCOUNT_KIND, email)
    request.session.cycle_key()
    bo_session.set_pending(request.session, user.pk, time.time())
    audit.record(action='auth.password_ok', actor=user, request=request)
    return redirect('backoffice:mfa')


@public_view
@require_http_methods(['GET', 'POST'])
def mfa_view(request):
    """Étape 2 (TOTP). Non disponible en Phase 1: refus fermé, session purgée.

    Statut 403 et non 503: Django n'enregistre pas la session sur une réponse 5xx,
    la purge de l'état « pending » serait alors perdue.
    """
    if bo_session.pending_user_id(request.session, time.time()) is None:
        return redirect('backoffice:login')
    bo_session.clear_pending(request.session)
    return render(request, 'backoffice/mfa_unavailable.html', status=403)


@public_view
@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        audit.record(action='auth.logout', actor=request.user, request=request)
    logout(request)
    return redirect('backoffice:login')
