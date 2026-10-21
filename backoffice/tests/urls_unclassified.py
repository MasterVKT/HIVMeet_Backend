"""URLconf de test: une vue ni publique ni associée à une capacité."""

from django.http import HttpResponse
from django.urls import include, path


def forgotten_view(request):
    return HttpResponse('should never be served')


urlpatterns = [
    path('backoffice/forgotten/', forgotten_view),
    path('backoffice/', include('backoffice.urls')),
]
