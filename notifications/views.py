"""
REST views for notifications app.

Endpoints :
  GET     /api/v1/notifications/               — liste paginée
  GET     /api/v1/notifications/unread-count/  — compteur non-lus
  PUT     /api/v1/notifications/<pk>/read/     — marquer une notif lue
  PUT     /api/v1/notifications/read-all/      — tout marquer lu
  DELETE  /api/v1/notifications/<pk>/delete/   — supprimer une notif
  DELETE  /api/v1/notifications/delete-all/     — supprimer toutes les notifs
"""
import logging

from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer

logger = logging.getLogger('hivmeet.notifications')


class NotificationListView(generics.ListAPIView):
    """
    GET /api/v1/notifications/
    Liste paginée des notifications de l'utilisateur connecté.
    Filtre optionnel : ?unread=true
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user)
        if self.request.query_params.get('unread') == 'true':
            qs = qs.filter(is_read=False)
        return qs


class UnreadCountView(generics.GenericAPIView):
    """
    GET /api/v1/notifications/unread-count/
    Retourne le nombre de notifications non lues.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        count = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()
        return Response({'unread_count': count})


class MarkReadView(generics.GenericAPIView):
    """
    PUT /api/v1/notifications/<pk>/read/
    Marque une notification spécifique comme lue.
    404 si la notification n'appartient pas à l'utilisateur.
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def put(self, request, pk=None, *args, **kwargs):
        notif = get_object_or_404(Notification, pk=pk, user=request.user)
        notif.is_read = True
        notif.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notif).data)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def mark_all_read(request):
    """
    PUT /api/v1/notifications/read-all/
    Marque toutes les notifications de l'utilisateur comme lues.
    Retourne le nombre de notifications mises à jour.
    """
    count = Notification.objects.filter(
        user=request.user, is_read=False
    ).update(is_read=True)
    return Response({'marked_read': count}, status=status.HTTP_200_OK)


class NotificationDeleteView(generics.DestroyAPIView):
    """
    DELETE /api/v1/notifications/<pk>/delete/
    Supprime une notification spécifique.
    404 si la notification n'appartient pas à l'utilisateur.
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        notif = get_object_or_404(
            Notification, pk=self.kwargs.get('pk'), user=request.user
        )
        notif.delete()
        return Response(
            {'deleted': str(self.kwargs.get('pk'))},
            status=status.HTTP_200_OK,
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_all_notifications(request):
    """
    DELETE /api/v1/notifications/delete-all/
    Supprime toutes les notifications de l'utilisateur.
    Retourne le nombre de notifications supprimées.
    """
    count, _ = Notification.objects.filter(user=request.user).delete()
    return Response(
        {'deleted_count': count},
        status=status.HTTP_200_OK,
    )
