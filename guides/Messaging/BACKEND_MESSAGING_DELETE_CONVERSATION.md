# Backend requis — Suppression de conversation

**Contexte** : session d'implémentation frontend « Messagerie 100% » (voir `AUDIT_MESSAGES_PAGE.md`). Le frontend a été mis à niveau et **masque désormais volontairement l'option « Supprimer »** dans le menu long-press de `ConversationsPage` (au lieu d'afficher un SnackBar « indisponible » — UI morte trompeuse retirée). Ce fichier documente précisément ce qu'il faut implémenter côté backend pour réactiver cette option.

---

## 1. État actuel exact (vérifié dans le code backend réel)

- `messaging/urls.py` (24 lignes) : aucune route `DELETE /conversations/<uuid:id>/` — seul `DELETE /conversations/<uuid:id>/messages/<uuid:message_id>/` existe (suppression de message individuel, `views.delete_message`, ligne 18).
- `messaging/views.py::ConversationListView.get_queryset` (lignes 57-73) :
  ```python
  def get_queryset(self):
      user = self.request.user
      queryset = Match.objects.filter(
          Q(user1=user) | Q(user2=user),
          status=Match.ACTIVE,
      ).exclude(
          last_message_at__isnull=True,
      ).select_related('user1__profile', 'user2__profile').order_by('-last_message_at')

      status_filter = self.request.query_params.get('status')
      if status_filter == 'archived':
          return queryset.none()
      return queryset
  ```
  `status=archived` retourne **toujours une liste vide** (`.none()`) — c'est un stub, pas un vrai filtre.
- `matching/models.py::Match` n'a **aucun champ** de type « masqué pour cet utilisateur » ou « archivé par ». Le modèle `Match` est partagé par les deux participants (`user1`, `user2`) — il n'y a pas de notion par-utilisateur actuellement.
- Conséquence : une conversation ne peut être ni supprimée, ni masquée, ni archivée pour un seul des deux participants. C'est une contrainte de modèle de données, pas seulement une route manquante.

## 2. Problème

Le frontend a besoin d'un moyen de retirer une conversation de la liste **pour l'utilisateur qui le demande uniquement** (l'autre participant doit continuer à voir ses messages). Une suppression physique de `Match`/`Message` casserait l'historique de l'autre participant — il faut un masquage par-utilisateur, pas une suppression SQL.

## 3. Fix prescrit

### 3.1 Migration — nouveau modèle `ConversationHiddenState`

Éviter d'ajouter des champs `hidden_by_user1`/`hidden_by_user2` sur `Match` (fragile, ne scale pas si un jour les conversations ne sont plus 1:1 avec `Match`). Préférer une table dédiée :

```python
# matching/models.py (ou un nouveau fichier messaging/models.py si préféré)

class ConversationHiddenState(models.Model):
    """Masque une conversation (Match) de la liste d'un utilisateur donné,
    sans affecter l'autre participant ni supprimer l'historique des messages.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='hidden_states')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hidden_conversations')
    hidden_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'conversation_hidden_states'
        unique_together = ['match', 'user']
        indexes = [models.Index(fields=['user', 'match'])]
```

```bash
python manage.py makemigrations matching -n conversation_hidden_state
python manage.py migrate
```

### 3.2 Endpoint `DELETE /api/v1/conversations/<uuid:conversation_id>/`

```python
# messaging/views.py

@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def delete_conversation(request, conversation_id):
    """
    DELETE /api/v1/conversations/{conversation_id}/
    Masque la conversation pour l'utilisateur courant uniquement.
    """
    match = _get_active_match_for_user(request.user, conversation_id)
    if not match:
        return Response({'error': _('Conversation not found.')}, status=status.HTTP_404_NOT_FOUND)

    ConversationHiddenState.objects.get_or_create(match=match, user=request.user)
    return Response(status=status.HTTP_204_NO_CONTENT)
```

```python
# messaging/urls.py — ajouter dans urlpatterns
path('<uuid:conversation_id>/', views.delete_conversation, name='delete-conversation'),
```

**Important** : ce path générique `<uuid:conversation_id>/` doit être déclaré **après** les autres routes plus spécifiques (`<uuid:conversation_id>/messages/`, etc.) dans `urlpatterns`, sinon Django risque de matcher ce pattern trop tôt selon l'ordre — vérifier avec `python manage.py show_urls` après ajout.

### 3.3 Exclure les conversations masquées de la liste

```python
# messaging/views.py::ConversationListView.get_queryset

def get_queryset(self):
    user = self.request.user
    hidden_match_ids = ConversationHiddenState.objects.filter(
        user=user
    ).values_list('match_id', flat=True)

    queryset = Match.objects.filter(
        Q(user1=user) | Q(user2=user),
        status=Match.ACTIVE,
    ).exclude(
        last_message_at__isnull=True,
    ).exclude(
        id__in=hidden_match_ids,
    ).select_related('user1__profile', 'user2__profile').order_by('-last_message_at')

    return queryset
```

### 3.4 Réapparition automatique si un nouveau message arrive

Comportement recommandé (cohérent avec WhatsApp/Messenger) : si l'autre participant envoie un nouveau message après que l'utilisateur a masqué la conversation, elle doit réapparaître. Dans `MessageService.send_message` (`messaging/services.py`, lignes 92-161), après la création du message :

```python
# À la fin de MessageService.send_message, avant `return message, None`
ConversationHiddenState.objects.filter(match=match, user=recipient).delete()
```

Cela évite le piège classique « je supprime la conversation mais je ne reçois plus jamais les nouveaux messages de cette personne sans le savoir ».

## 4. Contrat API (pour alignement frontend, déjà implémenté côté client)

| | |
|---|---|
| Méthode | `DELETE` |
| Path | `/api/v1/conversations/{conversation_id}/` |
| Auth | JWT `Authorization: Bearer` |
| Body | aucun |
| Succès | `204 No Content` |
| Erreurs | `404` conversation introuvable ou déjà masquée/inexistante pour cet utilisateur ; `401` token manquant/expiré |

## 5. Impact frontend une fois livré

- Réactiver l'option « Supprimer » dans `ConversationsPage._showConversationOptions` (`lib/presentation/pages/conversations/conversations_page.dart`) — actuellement retirée intentionnellement.
- Ajouter une méthode `deleteConversation(conversationId)` à `MessagingApi`, `MessageRepository`/`MessageRepositoryImpl`, un nouvel événement `DeleteConversation` sur `ConversationsBloc` (optimistic removal de la liste locale + rollback si échec, même pattern que `DeleteMessageEvent` sur `ChatBloc`).
- Aucun changement nécessaire sur `ChatPage`/`ChatBloc` — l'action ne concerne que la liste des conversations.

## 6. Critères de validation

- Une conversation masquée par l'utilisateur A n'apparaît plus dans son `GET /conversations/`.
- L'utilisateur B (l'autre participant) continue de voir la conversation normalement.
- Si B envoie un nouveau message après le masquage par A, la conversation réapparaît dans la liste de A.
- La suppression d'un message individuel (`DELETE /conversations/{id}/messages/{message_id}/`) reste inchangée et fonctionnelle.
