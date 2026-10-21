"""URLconf racine du processus back-office (aucune route de l'API, aucun admin)."""

from django.urls import include, path
from django.views.generic import RedirectView

from backoffice.access import public_view

urlpatterns = [
    path(
        '',
        public_view(RedirectView.as_view(pattern_name='backoffice:home', permanent=False)),
    ),
    path('backoffice/', include('backoffice.urls')),
]
