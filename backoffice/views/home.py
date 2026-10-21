from django.shortcuts import render
from django.views import View

from .. import access, roles


class HomeView(access.BackofficeView, View):
    """Page d'accueil (tableau de bord complet: Phase 7)."""

    capability = access.DASHBOARD

    def get(self, request):
        return render(request, 'backoffice/home.html', {
            'groups': sorted(roles.user_groups(request.user)),
        })
