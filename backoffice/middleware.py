"""Barrière centrale du back-office et en-têtes de sécurité.

Ce middleware n'est activé que par ``backoffice.conf.settings`` (il n'existe pas
dans le ``MIDDLEWARE`` de l'API). Il applique *deny by default*: une vue qui
n'est ni ``public_view`` ni associée à une capacité est refusée.
"""

from __future__ import annotations

import time

from django.contrib.auth import logout
from django.shortcuts import redirect, render

from . import access, audit, session as bo_session

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
)


class BackofficeSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return self.secure(response)

    @staticmethod
    def secure(response):
        response['Content-Security-Policy'] = CONTENT_SECURITY_POLICY
        response['Cache-Control'] = 'no-store'
        response['Pragma'] = 'no-cache'
        response['Referrer-Policy'] = 'same-origin'
        response['X-Robots-Tag'] = 'noindex, nofollow'
        response['X-Content-Type-Options'] = 'nosniff'
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        policy = access.view_policy(view_func)
        if policy == access.PUBLIC:
            return None
        if policy is None:
            return self._denied(request, 'unclassified_view')

        now = time.time()
        gate = access.evaluate_gate(request, policy, now=now)
        if gate is access.Gate.OK:
            bo_session.touch(request.session, now)
            return None
        if gate is access.Gate.ANONYMOUS:
            return redirect('backoffice:login')
        if gate is access.Gate.FORBIDDEN:
            return self._denied(request, 'forbidden', capability=policy)

        # Session expirée ou sans preuve MFA: déconnexion complète, retour connexion.
        user = request.user
        audit.record(
            action='auth.session_expired' if gate is access.Gate.SESSION_EXPIRED else 'access.denied',
            actor=user, request=request,
            metadata={'reason_code': gate.value, 'capability': policy},
        )
        logout(request)
        return redirect('backoffice:login')

    def _denied(self, request, reason_code, capability=''):
        user = request.user
        if user.is_authenticated:
            audit.record(
                action='access.denied', actor=user, request=request,
                metadata={'reason_code': reason_code, 'path': request.path, 'capability': capability},
            )
        return render(request, 'backoffice/denied.html', status=403)
