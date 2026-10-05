# Backend requis — Diffusion WebSocket des accusés de lecture (read receipts)

**Contexte** : session d'implémentation frontend « Messagerie 100% » (voir `AUDIT_MESSAGES_PAGE.md`, §3.4.9 et F32). Le frontend a été mis à jour pour distinguer visuellement les statuts `sending`/`sent`/`delivered`/`read` dans `MessageBubble` (icônes différentes), mais **le statut `read` de l'expéditeur ne se met à jour en temps réel que si le backend diffuse l'événement** — sinon l'expéditeur ne voit `done_all` violet qu'après avoir rechargé/rouvert la conversation.

---

## 1. État actuel exact (vérifié dans le code backend réel)

Trois points de marquage « lu » existent côté backend :

```python
# messaging/services.py, lignes 202-235
@staticmethod
def mark_messages_as_read(user, match, last_read_message_id=None) -> int:
    ...
    updated_count = query.update(status=Message.READ, read_at=timezone.now())
    if updated_count:
        match.reset_unread(user)
        if latest_message:
            send_read_notification.delay(...)   # <-- FCM push uniquement
    return updated_count
```

```python
# messaging/services.py, lignes 237-261
@staticmethod
def mark_single_message_as_read(user, message) -> bool:
    ...
    if message.status in [Message.SENT, Message.DELIVERED]:
        message.status = Message.READ
        message.read_at = timezone.now()
        message.save(update_fields=['status', 'read_at'])
        message.match.reset_unread(user)
        send_read_notification.delay(...)   # <-- FCM push uniquement
    return True
```

```python
# messaging/services.py, lignes 63-88 (get_conversation_messages, auto-mark au GET)
# Voir BACKEND_AUTO_MARK_READ_ON_GET.md pour ce point spécifique — ce fichier-ci
# se concentre uniquement sur l'absence de diffusion WS, pas sur le auto-mark.
```

**Aucun des trois chemins n'appelle `channel_layer.group_send`** vers le groupe `conversation_{id}` (contrairement à `MessageService.send_message`, dont le `post_save` signal `handle_new_message` diffuse bien `message.created` — voir `messaging/signals.py`). Le seul mécanisme de notification est `send_read_notification.delay(...)` (Celery → FCM push), qui :
1. N'atteint que l'appareil du **destinataire du push** (celui dont le message a été lu), jamais l'expéditeur qui a le chat ouvert et attend un accusé de lecture temps réel.
2. Passe par Celery, dont le broker est actuellement `memory://` en développement (voir section « Autres observations » ci-dessous) — perte silencieuse au redémarrage.

`ConversationConsumer` (`messaging/consumers.py`) ne définit aucun handler de groupe nommé `message_read` ou équivalent — seuls `message_created`, `typing_indicator`, `presence_update`, `ice_candidate`, `webrtc_offer`, `webrtc_answer`, `incoming_call`, `call_update` existent (lignes 324-418).

## 2. Problème

Quand l'utilisateur A a un chat ouvert et que l'utilisateur B lit ses messages (côté B, via `mark_messages_as_read`/`mark_single_message_as_read`), A ne voit **jamais** son message passer de `done` (gris) à `done_all` (violet) sans recharger manuellement la conversation. C'est le principal defect UX des accusés de lecture — la fonctionnalité existe en base de données mais n'est pas « live ».

## 3. Fix prescrit

### 3.1 Diffuser un événement `message.read` au groupe

```python
# messaging/services.py — ajouter en haut du fichier
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def _broadcast_read_receipt(match, reader, message_ids):
    """Diffuse un accusé de lecture au groupe WS de la conversation.
    Best-effort: une erreur ici ne doit jamais faire échouer le marquage
    (cohérent avec le pattern déjà utilisé pour channel_layer ailleurs dans
    le projet — voir channel_layer_context() dans consumers.py)."""
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            f'conversation_{match.id}',
            {
                'type': 'message_read',
                'reader_id': str(reader.id),
                'message_ids': [str(mid) for mid in message_ids],
                'read_at': timezone.now().isoformat(),
            },
        )
    except Exception as exc:
        logger.warning(f"Failed to broadcast read receipt: {exc}")
```

Puis appeler cette fonction dans les deux méthodes de marquage :

```python
# MessageService.mark_messages_as_read — après match.reset_unread(user)
if updated_count:
    match.reset_unread(user)
    read_ids = list(query.values_list('id', flat=True))  # capturer AVANT le .update() ci-dessus si l'ORM invalide le queryset après update — vérifier l'ordre exact selon la version Django utilisée
    _broadcast_read_receipt(match, user, read_ids)
    if latest_message:
        send_read_notification.delay(...)
```

```python
# MessageService.mark_single_message_as_read — après message.match.reset_unread(user)
if message.status in [Message.SENT, Message.DELIVERED]:
    message.status = Message.READ
    message.read_at = timezone.now()
    message.save(update_fields=['status', 'read_at'])
    message.match.reset_unread(user)
    _broadcast_read_receipt(message.match, user, [message.id])
    send_read_notification.delay(...)
```

**Attention à l'ordre d'exécution** : `query.update(...)` (bulk update) ne renvoie que le nombre de lignes affectées, pas les IDs. Il faut soit capturer `list(query.values_list('id', flat=True))` **avant** l'appel à `.update()`, soit refaire une requête après. Vérifier l'implémentation exacte de `mark_messages_as_read` au moment de la modification.

### 3.2 Handler consumer

```python
# messaging/consumers.py::ConversationConsumer — ajouter à côté de message_created (ligne 324)

async def message_read(self, event):
    """Handle read receipt event from group."""
    await self.send(text_data=json.dumps({
        'type': 'message.read',
        'reader_id': event['reader_id'],
        'message_ids': event['message_ids'],
        'read_at': event['read_at'],
    }))
```

Pas besoin de filtrer « ne pas renvoyer à soi-même » ici (contrairement à `typing_indicator`/`presence_update`) : l'expéditeur ET le lecteur peuvent légitimement vouloir recevoir cet événement (le lecteur pour confirmer son propre marquage sur un second appareil, l'expéditeur pour voir l'accusé de lecture).

## 4. Impact frontend (déjà préparé pour recevoir cet événement)

- `ChatWebSocketService` (`lib/core/services/chat_websocket_service.dart`) : ajouter `messageRead` à `WsEventType` et le cas correspondant dans `_parseEventType` (`'message.read' → WsEventType.messageRead`).
- `ChatBloc` : ajouter un événement interne `_WebSocketMessageRead { readerId, messageIds, readAt }`, un handler qui, si `readerId != currentUserId` (l'autre a lu MES messages), met à jour `status: MessageStatus.read` sur les messages dont l'`id` est dans `messageIds` et `isMine == true`.
- `MessageBubble` n'a besoin d'aucune modification — l'icône `done_all` violet (déjà implémentée pour F14) s'affichera automatiquement dès que `message.status == MessageStatus.read`.

## 5. Critères de validation

- Ouvrir le même chat sur deux appareils (A envoie, B reçoit et a le chat ouvert) → dès que B affiche le message (auto-mark ou scroll), A voit son icône passer à `done_all` violet en moins d'une seconde, sans recharger.
- Le comportement FCM push existant (notification « message lu » quand le destinataire n'a PAS l'app ouverte) reste inchangé — ce fix ajoute un canal, n'en retire aucun.
- Si Redis/channel layer est indisponible, `_broadcast_read_receipt` échoue silencieusement (log warning) sans faire échouer `mark_messages_as_read`/`mark_single_message_as_read` (le marquage en base doit toujours réussir même si la diffusion temps réel échoue).
