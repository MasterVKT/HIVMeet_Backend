# Backend — Real-Time Messaging: rapport d'implémentation

**Date** : 2026-07-31
**En réponse à** : [BACKEND_REALTIME_MESSAGING_REQUIREMENTS.md](BACKEND_REALTIME_MESSAGING_REQUIREMENTS.md) (session frontend, 2026-07-30)
**Statut** : tous les points du rapport sont traités. 119 tests backend passent.

---

## 1. Ce qui a été livré

| Priorité | Item | Statut | Fichiers |
|---|---|---|---|
| P0 | `new_message` → groupe `user_{id}` | ✅ | `messaging/signals.py`, `notifications/consumers.py` |
| P0 | `message_read` → groupe `user_{sender_id}` | ✅ | `messaging/services.py`, `notifications/consumers.py` |
| P1 | `GET /api/v1/conversations/unread-count/` | ✅ | `messaging/views.py`, `messaging/urls.py` |
| P1 | `notification_id` FCM par message | ✅ | `messaging/tasks.py`, `messaging/signals.py` |
| P1 | `mark_as_delivered` + événement `message.delivered` | ✅ | `messaging/services.py`, les deux consumers |
| P2 | `ping`/`pong` sur `UserNotificationConsumer` | ✅ | `notifications/consumers.py` |
| P2 | `POST .../typing/` diffuse au groupe | ✅ | `messaging/services.py` |
| P2 | `incoming_call`/`call_update` → `user_{id}` | ✅ | `messaging/signals.py`, `notifications/consumers.py` |
| P2 | Refresh JWT in-band sur WS | ⛔ Non implémenté, **décision produit** | documenté |
| Doc | 4 docs obsolètes rafraîchis | ✅ | voir §4 |

---

## 2. Contrats exacts (à consommer côté Flutter)

### 2.1 `/ws/notifications/` — nouveaux événements

`new_message` (déjà parsé par `NotificationWebSocketService`, 2 clés en plus) :
```json
{
  "type": "new_message",
  "conversation_id": "uuid",
  "message_id": "uuid",
  "from_user_id": "uuid",
  "preview": "Hello",
  "unread_count": 3
}
```
`unread_count` = non-lus **de cette conversation** après le message.

`message_read` — adressé à l'**auteur** des messages lus :
```json
{
  "type": "message_read",
  "conversation_id": "uuid",
  "reader_id": "uuid",
  "message_ids": ["uuid"],
  "read_at": "2026-07-31T16:00:00+00:00"
}
```

`message_delivered` — adressé à l'**auteur** des messages livrés :
```json
{
  "type": "message_delivered",
  "conversation_id": "uuid",
  "message_ids": ["uuid"],
  "delivered_at": "2026-07-31T16:00:00+00:00"
}
```

`incoming_call` / `call_update` : mêmes objets `call` que sur le socket
conversation, avec `match_id` ajouté à `call_update`.

Client → serveur : `{"type":"ping"}` → `{"type":"pong","timestamp":...}`.
JSON invalide → frame `error` / `INVALID_JSON`. Tout autre `type` ignoré.

### 2.2 `/ws/conversations/{id}/` — nouvel événement

```json
{
  "type": "message.delivered",
  "conversation_id": "uuid",
  "message_ids": ["uuid"],
  "delivered_at": "2026-07-31T16:00:00+00:00"
}
```

### 2.3 Nouvel endpoint REST

```
GET /api/v1/conversations/unread-count/   →   200 {"unread_count": 7}
```
Somme serveur sur **toutes** les conversations actives non masquées.
`401` sans auth. Même périmètre que `GET /api/v1/conversations/`.

---

## 3. Sémantique de `delivered` retenue

Choix aligné sur WhatsApp / Signal / Telegram : **« delivered » = le message a
atteint l'appareil**, pas « l'utilisateur a ouvert ce chat ». Deux déclencheurs :

1. connexion à `/ws/notifications/` → balaie **toutes** les conversations actives
   (l'appareil est en ligne) ;
2. connexion à `/ws/conversations/{id}/` → limité à cette conversation.

Garanties :
- un message `delivered` **reste compté comme non lu** — les compteurs et le
  badge ne bougent pas ;
- l'`UPDATE` est conditionné à `status = 'sent'` (compare-and-set) : un message
  lu entre-temps ne repasse jamais à `delivered` ;
- l'`UPDATE` est en masse, donc `post_save` ne se redéclenche pas ;
- opération idempotente : après le premier balayage la requête ne ramène plus
  rien, une reconnexion en backoff reste peu coûteuse.

---

## 4. Correction de bug non demandée dans le rapport

`handle_call_update` (`messaging/signals.py`) se déclenchait sur **chaque**
`post_save` de `Call`. Or `CallService.add_ice_candidate` sauvegarde la même
ligne à chaque candidat ICE pendant que l'appel sonne → `incoming_call` était
rediffusé à chaque candidat, **faisant re-sonner le callee en boucle**.

Le bug existait déjà sur le groupe conversation ; l'ajout du groupe `user_{id}`
l'aurait rendu bien plus visible. Garde ajoutée : une sauvegarde dont
`update_fields` exclut explicitement `status` ne peut pas être une transition
d'état et n'émet donc aucun événement. Couvert par
`test_handle_call_update_ignores_saves_that_cannot_change_status`.

---

## 5. Décision : pas de refresh JWT in-band

Le rapport le classait « optionnel / non bloquant » ; le frontend récupère déjà
un token frais à chaque tentative de connexion. Ré-authentifier une socket déjà
ouverte ajoute de la surface d'attaque pour zéro gain fonctionnel sur une app
santé. Conséquence assumée : une session de plus de 60 minutes subit **une**
reconnexion due à l'expiration du token. Documenté dans
`docs/MESSAGES_BACKEND_WEBSOCKET_FRONTEND.md` §7.4.

Allonger `ACCESS_TOKEN_LIFETIME` a été écarté : cela dégraderait la sécurité de
toute l'authentification, pas seulement du WebSocket.

---

## 6. ⚠️ Points d'attention pour le frontend

### 6.1 `message.delivered` est ignoré aujourd'hui

`ChatWebSocketService._parseEventType` (`lib/core/services/chat_websocket_service.dart:266-283`)
ne connaît pas `message.delivered` → retombe sur `WsEventType.unknown`, donc
l'événement est **silencieusement jeté**. Aucun crash, mais l'état ✓✓ gris
n'apparaîtra en direct qu'après ajout d'un `case 'message.delivered'` + du
`case WsEventType.messageDelivered` dans `ChatBloc`
(`lib/presentation/blocs/chat/chat_bloc.dart:512-556`).

En attendant, le `status: "delivered"` remonte correctement par REST : l'état
est visible après un refetch, pas en temps réel.

### 6.2 `UnreadCubit` n'utilise pas encore l'endpoint dédié

`lib/presentation/blocs/unread/unread_cubit.dart:66-83` somme toujours la
page 1 de `GET /api/v1/conversations/`. L'endpoint exact existe désormais —
le commentaire du fichier référence d'ailleurs déjà la demande P1. Remplacer
l'appel par `GET /api/v1/conversations/unread-count/` supprime l'approximation
au-delà de 20 conversations.

### 6.3 Fenêtre de déduplication de 2 s — perte de messages rapides

`RealtimeEventBus._dedupeKeyFor` (`lib/core/realtime/realtime_event_bus.dart:65-70`)
déduplique sur `newMessage:$conversationId` dans une fenêtre de 2 s. **Deux
messages envoyés dans la même conversation à moins de 2 s d'intervalle
produisent un seul événement** : le second est avalé.

Sans impact sur `UnreadCubit` (refresh serveur débouncé, donc correct), mais
`ConversationsBloc` peut manquer un patch optimiste. Le backend expose
maintenant `message_id` sur les deux canaux (WS et FCM), la clé peut donc être
resserrée en `newMessage:$conversationId:$messageId`, ce qui élimine le
problème tout en gardant la déduplication WS ↔ FCM.

### 6.4 `notification_id` FCM change de valeur

Avant : `msg_<sender_uuid>` — identique pour **tous** les messages d'un même
expéditeur. `NotificationService._buildAppNotification`
(`lib/data/services/notification_service.dart:216-236`) l'utilise comme
`AppNotification.id`, donc les notifications d'un même expéditeur se
collisionnaient. Après : `msg_<message_id>`, unique par message.

Pas de changement de code requis, mais tout cache ou déduplication frontend
qui supposait la stabilité de cet identifiant par expéditeur doit être revu.

### 6.5 Aucun consommateur pour `incoming_call` / `call_update`

`NotificationWebSocketService._onRawMessage` ignore ces `type` (branche
`default`). C'est sans conséquence tant que l'UI d'appel est un
`// TODO: Implémenter les appels WebRTC`, mais le canal est prêt côté backend
le jour où l'écran WebRTC sera construit.

### 6.6 Non-anomalie confirmée : `status=active`

Le rapport signalait `MESSAGES_BACKEND_SPECIFICATION_FRONTEND.md` §3.1 qui
documentait `status=active|archived`. Vérification faite :
`ConversationFilter` (`lib/domain/entities/message.dart:13-21`) n'émet que
`all|unread|archived` — le frontend n'a **jamais** envoyé `active`. C'était une
dérive purement documentaire, corrigée.

---

## 7. Documentation mise à jour

| Fichier | Nature |
|---|---|
| `docs/MESSAGES_BACKEND_WEBSOCKET_FRONTEND.md` | §4.3 `message.delivered`, §4.10/4.11 événements d'appel, **§7 canal `/ws/notifications/` complet** (auth, événements, ping, durée du token, dédup FCM) |
| `docs/FRONTEND_MESSAGING_API.md` | §4.1bis `unread-count`, `message.delivered`, **§5bis canal notifications** |
| `docs/API_DOCUMENTATION.md` | endpoint `unread-count` (source de vérité du contrat) |
| `MESSAGES_BACKEND_CONTRACT_FRONTEND.md` | §2.5/§2.6 corrigés (`unread_count_for_me`, `read_at` conditionnel), §2.6bis, §5.4 complété, §5.4bis canal notifications |
| `MESSAGES_BACKEND_SPECIFICATION_FRONTEND.md` | §3.1 `status` corrigé (`all\|unread\|archived`, `active` → 400), §3.2 nouvel endpoint, §10 limitations |
| `ENDPOINTS_COMPLETE_DOCUMENTATION.md` | section Messagerie **entièrement réécrite** (enveloppes de pagination, `unread_count_for_me`, corps réel de mark-as-read, section WebSocket) |
| `docs/MESSAGING_BACKEND_STATE.md` | dette #4 marquée résolue, #5 et #8 annotées |

---

## 8. Couverture de test

**119 tests passent** (`messaging`, `notifications`, `matching`,
`authentication`, `resources`).

Ajouts :
- `messaging/tests.py` — endpoint `unread-count` (5 tests : somme multi-conversations,
  zéro, exclusion des masquées, isolation entre participants, 401) ;
  `mark_incoming_as_delivered` (6 tests : sélectivité, compteurs préservés,
  balayage global, idempotence, transition vers `read`, diffusion) ;
  diffusion `typing` REST (3 tests) ; garde sur les événements d'appel (2 tests).
- `messaging/test_remediation.py` — `DeliveryReceiptWebSocketTests` : sockets
  réels via `WebsocketCommunicator` (connexion conversation, connexion
  notifications, réception de l'accusé par l'auteur, ping/pong, refus sans token).
- `notifications/tests.py` — `TestUserNotificationConsumerEvents` : contrat JSON
  de chaque événement + `receive()`.

Tests existants adaptés (le passage de 1 à 2 `group_send` cassait les
`assert_called_once_with`) : accusés de lecture, signal de message, signal d'appel.

### Échecs pré-existants (hors périmètre, non introduits ici)
- `subscriptions.tests` — 13 erreurs `null value in column "birth_date"` +
  1 `assertEqual(9.99, Decimal('9.99'))`. Fichier identique à `HEAD`, jamais
  touché ici.
- `profiles` — `ImportError` de découverte : `profiles/tests.py` **et**
  `profiles/tests/` coexistent. Empêche `manage.py test` sans argument.

---

## 9. Vérification manuelle suggérée

```bash
# 1. Badge global
curl -H "Authorization: Bearer $JWT" http://localhost:8000/api/v1/conversations/unread-count/

# 2. Temps réel : ouvrir le socket notifications du destinataire,
#    envoyer un message depuis l'autre compte, observer new_message
wscat -c "ws://localhost:8000/ws/notifications/?token=$JWT"

# 3. Delivered : le socket ci-dessus étant ouvert côté destinataire,
#    l'auteur doit recevoir message_delivered sur son propre socket notifications
```

Redis doit tourner (`CHANNEL_LAYERS` → `channels_redis`), sinon toutes les
diffusions sont silencieusement ignorées — par conception, la persistance et
les réponses REST ne sont jamais bloquées par une panne du channel layer.
