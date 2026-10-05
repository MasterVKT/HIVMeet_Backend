# Backend requis — Le GET des messages marque « lu » avant que l'utilisateur les voie réellement

**Contexte** : session d'implémentation frontend « Messagerie 100% » (voir `AUDIT_MESSAGES_PAGE.md`, §3.4.1). Bug backend pur — le frontend ne peut pas corriger un marquage qui se produit côté serveur avant même que la réponse HTTP n'arrive au client.

---

## 1. État actuel exact (vérifié dans le code backend réel)

```python
# messaging/services.py::MessageService.get_conversation_messages, lignes 32-90
@staticmethod
def get_conversation_messages(user, match, limit=50, before_id=None):
    query = Message.objects.filter(match=match)
    query = query.filter(
        Q(sender=user, is_deleted_by_sender=False) |
        Q(sender=match.get_other_user(user), is_deleted_by_recipient=False)
    )

    if before_id:
        try:
            before_message = Message.objects.get(id=before_id, match=match)
            query = query.filter(created_at__lt=before_message.created_at)
        except Message.DoesNotExist:
            pass

    if not user.is_premium:
        query = query.order_by('-created_at')[:50]
    else:
        query = query.order_by('-created_at')

    messages = list(query[:limit])

    # Auto-mark received unread messages as read
    unread_ids = [
        msg.id for msg in messages
        if msg.sender != user and msg.status in [Message.SENT, Message.DELIVERED]
    ]
    if unread_ids:
        read_at = timezone.now()
        latest_read_message_id = unread_ids[0]
        Message.objects.filter(id__in=unread_ids).update(status=Message.READ, read_at=read_at)
        match.reset_unread(user)
        for msg in messages:
            if msg.id in unread_ids:
                msg.status = Message.READ
                msg.read_at = read_at
        try:
            send_read_notification.delay(...)
        except Exception as exc:
            logger.warning(f"Failed to queue read notification: {exc}")

    return messages
```

Ce `GET /conversations/{id}/messages/` — appelé par `ChatBloc._onLoadConversation` **dès l'ouverture du chat**, et par `ChatBloc._onLoadMoreMessages` **à chaque scroll vers le haut** — marque **immédiatement** tous les messages reçus comme `READ` dès qu'ils sont retournés par l'API, indépendamment de :
- si l'utilisateur a réellement vu le contenu à l'écran (le chat peut charger 50 messages alors que seuls les 5 derniers sont visibles avant tout scroll),
- si l'app est au premier plan ou en arrière-plan (un pré-chargement silencieux marquerait aussi comme lu),
- de la sémantique déjà correctement implémentée par `mark_messages_as_read`/`mark_single_message_as_read` (`messaging/services.py`, lignes 202-261), qui existent précisément pour un marquage explicite piloté par le client.

## 2. Problème

Le concept de « lu » perd son sens : un message peut être marqué `READ` alors que l'utilisateur n'a fait qu'ouvrir la conversation sans même que le message soit entré dans le viewport (cas fréquent avec l'historique paginé). Cela génère aussi un accusé de lecture FCM push (`send_read_notification.delay`) prématuré envoyé au véritable expéditeur, qui croit à tort que son message a été lu.

Le frontend a déjà toute la logique nécessaire pour un marquage explicite et correct :
- `ChatBloc.MarkUnreadMessagesAsRead` (déclenché à l'ouverture du chat après le premier rendu, ET quand l'utilisateur scrolle jusqu'en bas — voir `chat_page.dart::_onScroll`/`initState`) → appelle `MarkMessageAsReadParams` sur le dernier message non-lu de l'interlocuteur.
- Ce flux existant est actuellement **redondant** avec l'auto-mark du GET (les deux marquent, mais le GET le fait trop tôt).

## 3. Fix prescrit

**Retirer l'auto-mark du GET** et laisser le marquage explicite (déjà appelé par le frontend) être l'unique source de vérité :

```python
# messaging/services.py::MessageService.get_conversation_messages

@staticmethod
def get_conversation_messages(user, match, limit=50, before_id=None):
    """
    Get messages for a conversation with pagination.

    Ne marque plus automatiquement les messages comme lus — laisser
    `mark_messages_as_read`/`mark_single_message_as_read` (appelés
    explicitement par le client quand l'utilisateur a réellement vu les
    messages) être l'unique source de vérité pour les accusés de lecture.
    """
    query = Message.objects.filter(match=match)
    query = query.filter(
        Q(sender=user, is_deleted_by_sender=False) |
        Q(sender=match.get_other_user(user), is_deleted_by_recipient=False)
    )

    if before_id:
        try:
            before_message = Message.objects.get(id=before_id, match=match)
            query = query.filter(created_at__lt=before_message.created_at)
        except Message.DoesNotExist:
            pass

    if not user.is_premium:
        query = query.order_by('-created_at')[:50]
    else:
        query = query.order_by('-created_at')

    return list(query[:limit])
```

Toute la section « Auto-mark received unread messages as read » (et son import implicite de `send_read_notification`, à vérifier s'il devient inutilisé ailleurs dans le fichier avant de retirer l'import) est supprimée.

## 4. Vérification requise avant de merger

S'assurer que le frontend appelle bien systématiquement un marquage explicite dans tous les cas d'usage réels :
- Ouverture d'un chat avec des messages non lus → `MarkUnreadMessagesAsRead` est bien déclenché post-frame (`chat_page.dart::initState`, déjà en place).
- Réception d'un nouveau message pendant que le chat est ouvert et scrollé en bas → `MarkUnreadMessagesAsRead` redéclenché (déjà en place, voir listener `BlocConsumer` dans `chat_page.dart`).
- Scroll manuel jusqu'en bas après avoir remonté dans l'historique → `_onScroll` redéclenche `MarkUnreadMessagesAsRead` (déjà en place).

Ces trois chemins existent déjà côté frontend (aucune modification frontend requise pour ce fix) — la seule chose à retirer est l'auto-mark côté GET qui rendait ce marquage explicite redondant/prématuré.

## 5. Impact sur le compteur non-lu et les notifications

- `match.reset_unread(user)` ne sera plus appelé au GET — uniquement via les endpoints de marquage explicite. Le badge non-lu (`unread_count_for_me`) restera correct car le frontend appelle déjà `MarkUnreadMessagesAsRead`/`MarkConversationAsRead` dans tous les cas pertinents (voir §4).
- `send_read_notification` (push FCM « votre message a été lu ») ne partira plus au simple chargement de la liste — seulement quand l'utilisateur a réellement interagi avec la conversation. C'est le comportement correct attendu par l'expéditeur.

## 6. Critères de validation

- `GET /conversations/{id}/messages/` ne modifie plus jamais `status`/`read_at` d'aucun message — vérifiable par un test qui charge les messages puis vérifie qu'aucun `READ` n'a été appliqué sans appel explicite à `mark-as-read`.
- Le badge non-lu et les accusés de lecture temps réel (voir `BACKEND_READ_RECEIPT_WS_BROADCAST.md`) continuent de fonctionner via les endpoints de marquage explicite déjà appelés par le frontend.
- Pas de régression sur la pagination des messages (`before_message_id`, `has_more`) — ce fix ne touche que la section auto-mark, pas la logique de requête/pagination.
