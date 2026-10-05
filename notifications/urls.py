"""
URL patterns for notifications app.

Monté sous /api/v1/notifications/ dans hivmeet_backend/api_urls.py.
"""
from django.urls import path

from . import views
from profiles.kyc import protect_view_with_active_kyc

urlpatterns = [
    # Liste paginée (+ filtre ?unread=true)
    path('', protect_view_with_active_kyc(views.NotificationListView.as_view()), name='notification-list'),

    # Compteur de non-lus
    path('unread-count/', protect_view_with_active_kyc(views.UnreadCountView.as_view()), name='notification-unread-count'),

    # Tout marquer lu (AVANT <pk>/read/ pour éviter que "read-all" matche un <pk>)
    path('read-all/', protect_view_with_active_kyc(views.mark_all_read), name='notification-read-all'),

    # Tout supprimer (AVANT <pk>/... pour éviter que "delete-all" matche un <pk>)
    path('delete-all/', protect_view_with_active_kyc(views.delete_all_notifications), name='notification-delete-all'),

    # Marquer une notification comme lue
    path('<uuid:pk>/read/', protect_view_with_active_kyc(views.MarkReadView.as_view()), name='notification-mark-read'),

    # Supprimer une notification spécifique
    path('<uuid:pk>/delete/', protect_view_with_active_kyc(views.NotificationDeleteView.as_view()), name='notification-delete'),
]
