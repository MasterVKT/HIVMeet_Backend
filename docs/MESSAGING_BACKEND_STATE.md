# État de la messagerie backend — HIVMeet

> **Date** : 2026-06-22  
> **Branche** : `master` (commit `b0fd90b`)  
> **Portée** : app `messaging/` + dépendances directes (`matching.models.Match`, `notifications/`, `subscriptions/`)

---

## Sommaire

1. [Architecture générale](#1-architecture-générale)
2. [Modèle de données](#2-modèle-de-données)
3. [Endpoints REST](#3-endpoints-rest)
4. [Serializers et validation](#4-serializers-et-validation)
5. [Couche service](#5-couche-service)
6. [Temps réel — WebSocket](#6-temps-réel--websocket)
7. [Notifications et tâches asynchrones](#7-notifications-et-tâches-asynchrones)
8. [Sécurité et gating premium](#8-sécurité-et-gating-premium)
9. [Tests](#9-tests)
10. [Lacunes et limites connues](#10-lacunes-et-limites-connues)

---

## 1. Architecture générale

### Stack technique

| Composant | Rôle |
|-----------|------|
| **Django REST Framework** | API HTTP (conversations, messages, appels) |
| **Django Channels (ASGI)** | WebSocket temps réel |
| **Redis** | Channel layer (WS) + cache (typing indicators, présence) |
| **Celery** | Tâches push notification (FCM) asynchrones |
| **Firebase Cloud Messaging** | Push mobile (Android + iOS) via `firebase_admin.messaging` |
| **PostgreSQL** | Persistance (messages, appels, typing indicators) |

### Pattern global

```
Flutter (HTTP/WS)
    │
    ├─ HTTP ──► Views (thin controllers)
    │               └─► MessageService / CallService
    │                       └─► Models (Message, Call, TypingIndicator)
    │                               └─► Signal post_save
    │                                       ├─► Celery task → FCM push
    │                                       ├─► Notification DB (app notifications)
    │                                       └─► channel_layer.group_send → WS clients
    │
    └─ WS ───► ConversationConsumer (AsyncWebsocketConsumer)
                    └─► MessageService.send_message (même flux ci-dessus)
```

**Principe** : un seul chemin de création de message (`MessageService.send_message`), que l'origine soit HTTP ou WebSocket. Le signal `post_save` garantit que tout message persisté déclenche automatiquement push FCM + broadcast WebSocket.

### Montage des URLs

```
/api/v1/
    conversations/       → messaging.urls          (conversations, messages)
    calls/               → messaging.urls_calls     (gestion appels)

ws/
    conversations/<uuid>/  → ConversationConsumer
    notifications/         → UserNotificationConsumer (app notifications)
```

---

## 2. Modèle de données

### 2.1 `Message` — `messaging/models.py`

Modèle central. Table `messages`.

| Champ | Type | Description |
|-------|------|-------------|
| `id` | `UUIDField` (PK) | Identifiant serveur |
| `client_message_id` | `CharField(100)` | ID généré par le client — déduplication |
| `match` | `ForeignKey(Match)` | Conversation parente (cascade) |
| `sender` | `ForeignKey(User)` | Expéditeur |
| `message_type` | `CharField(10)` | `text` / `image` / `video` / `audio` / `call_log` |
| `content` | `TextField(max=1000)` | Contenu texte |
| `media_url` | `URLField(500)` | URL publique du média (premium) |
| `media_thumbnail_url` | `URLField(500)` | Vignette |
| `media_file_path` | `CharField(500)` | Chemin GCS/stockage |
| `status` | `CharField(10)` | `sending` / `sent` / `delivered` / `read` / `failed` |
| `created_at` | `DateTimeField` | Horodatage création (auto) |
| `delivered_at` | `DateTimeField` (nullable) | Horodatage livraison |
| `read_at` | `DateTimeField` (nullable) | Horodatage lecture |
| `is_deleted_by_sender` | `BooleanField` | Soft delete côté expéditeur |
| `is_deleted_by_recipient` | `BooleanField` | Soft delete côté destinataire |

**Méthodes** :
- `get_recipient()` — retourne l'autre participant du match
- `mark_as_delivered()` — `sent → delivered`, enregistre `delivered_at`
- `mark_as_read()` — `* → read`, enregistre `read_at`, reset unread du match
- `delete_for_user(user)` — positionne le flag soft-delete approprié

**Index DB** :
```
(match, -created_at)        — chargement conversation
(sender, -created_at)       — historique par user
(status)                    — requêtes non lus
(client_message_id)         — déduplication
```

---

### 2.2 `MessageReaction` — `messaging/models.py`

> ⚠️ Déclaré **"future feature"** — modèle présent, **aucun endpoint ni service** implémenté.

| Champ | Type |
|-------|------|
| `id` | UUID PK |
| `message` | FK(Message) |
| `user` | FK(User) |
| `emoji` | CharField(10) |
| `created_at` | DateTimeField |

Contrainte : `unique_together = ['message', 'user']`.

---

### 2.3 `Call` — `messaging/models.py`

Gestion des appels audio/vidéo WebRTC. Table `calls`.

| Champ | Type | Description |
|-------|------|-------------|
| `id` | UUID PK | |
| `match` | FK(Match) | Conversation parente |
| `caller` | FK(User) | Initiateur |
| `callee` | FK(User) | Destinataire |
| `call_type` | `audio` / `video` | |
| `status` | CharField | `initiated` / `ringing` / `answered` / `ended` / `declined` / `missed` / `failed` |
| `offer_sdp` | TextField | SDP WebRTC de l'offre |
| `answer_sdp` | TextField | SDP WebRTC de la réponse |
| `ice_candidates` | JSONField (list) | Candidats ICE accumulés |
| `initiated_at` | DateTimeField | auto |
| `answered_at` | DateTimeField (nullable) | |
| `ended_at` | DateTimeField (nullable) | |
| `duration_seconds` | PositiveIntegerField | Calculé à la fin |
| `end_reason` | CharField(50) | Raison de fin |

**Méthodes** :
- `calculate_duration()` — calcule `duration_seconds` depuis `answered_at`→`ended_at`
- `end_call(reason)` — transition vers statut terminal + `calculate_duration` + crée un `Message(type=call_log)`
- `_get_call_log_message()` — texte i18n résumant l'appel (durée, déclin, manqué, échec)
- `check_call_limit(user)` *(classmethod)* — vérifie premium + quota 30 min/jour cumulé

**Index DB** : `(match, -initiated_at)`, `(caller, -initiated_at)`, `(callee, -initiated_at)`, `(status)`.

---

### 2.4 `TypingIndicator` — `messaging/models.py`

| Champ | Type |
|-------|------|
| `id` | UUID PK |
| `match` | FK(Match) |
| `user` | FK(User) |
| `is_typing` | BooleanField |
| `updated_at` | DateTimeField (auto_now) |

Contrainte : `unique_together = ['match', 'user']`.  
En pratique, le statut live est **doublonné en cache Redis** (TTL 10 s) — la table sert de persistance de secours.

---

### 2.5 Champs messaging sur `Match` (app `matching`)

L'état de la conversation est porté directement sur le modèle `Match` :

| Champ | Type | Rôle |
|-------|------|------|
| `last_message_at` | DateTimeField (nullable) | Tri des conversations |
| `last_message_preview` | CharField(100) | Aperçu dernier message |
| `user1_unread_count` | PositiveIntegerField | Compteur non lus user1 |
| `user2_unread_count` | PositiveIntegerField | Compteur non lus user2 |

**Helpers** :
- `get_other_user(user)` — retourne l'autre participant
- `get_unread_count(user)` — lit le bon compteur
- `increment_unread(for_user)` — +1 pour le destinataire
- `reset_unread(for_user)` — remet à 0 après lecture
- `get_match_between(u1, u2)` *(classmethod)* — requête OR bidirectionnelle, status=ACTIVE

---

## 3. Endpoints REST

Tous protégés par `IsAuthenticated`. Auth via Bearer JWT.  
Préfixe : `/api/v1/`

### 3.1 Conversations

#### `GET /conversations/`

Liste des conversations de l'utilisateur connecté.

- Filtre : matches `ACTIVE` où l'utilisateur est `user1` ou `user2`, avec `last_message_at` non null.
- Tri : `-last_message_at`.
- Paramètre `?status=archived` → retourne une liste vide (archivage **non implémenté**).
- `select_related('user1__profile', 'user2__profile')`.

**Réponse** (200) :
```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "conversation_id": "uuid",
      "id": "uuid",
      "other_user": {
        "user_id": "uuid",
        "display_name": "string",
        "main_photo_url": "string|null",
        "is_online": true,
        "last_active": "datetime"
      },
      "last_message": {
        "message_id": "uuid",
        "content_preview": "string",
        "sender_id": "uuid",
        "sent_at": "datetime",
        "is_read_by_me": true
      },
      "unread_count_for_me": 2,
      "created_at": "datetime",
      "last_message_at": "datetime",
      "last_activity_at": "datetime"
    }
  ]
}
```

`is_online` = `(now - other_user.last_active).total_seconds() < 300`.

---

#### `GET /conversations/{conversation_id}/messages/`

Historique paginé par curseur.

**Query params** :

| Param | Défaut | Description |
|-------|--------|-------------|
| `before_message_id` | — | UUID — charge les messages antérieurs à cet ID |
| `limit` / `page_size` | 50 | Nombre de messages retournés |
| `page` | 1 | Pagination page (calcul `previous` link uniquement) |

**Comportement** :
- Exclut les messages supprimés côté user.
- **Non-premium** : historique plafonné aux 50 messages les plus récents (indépendamment du curseur).
- **Lecture sans effet de bord** : le GET ne modifie jamais le statut ni les compteurs. Le client appelle explicitement l'endpoint de marquage comme lu quand le message a été affiché.

**Réponse** (200) :
```json
{
  "count": 120,
  "next": "?before_message_id=uuid&page_size=50",
  "previous": null,
  "results": [ /* MessageSerializer */ ],
  "has_more": true,
  "show_premium_prompt": false
}
```

---

#### `POST /conversations/{conversation_id}/messages/`

Envoyer un message texte uniquement.

**Corps** :
```json
{
  "client_message_id": "string (requis, max 100)",
  "content": "string (requis si type=text, max 1000)",
  "type": "text"
}
```

**Comportement** :
- Vérifie que le match est ACTIVE et appartient au user.
- **Déduplication** : si `client_message_id` existe déjà pour ce match, retourne le message existant (idempotent).
- Les payloads média et `media_file_path_on_storage` sont rejetés : l'envoi média passe exclusivement par l'endpoint multipart.
- MAJ `last_message_at` + `last_message_preview` + `increment_unread(recipient)` sur le Match.
- Le signal `post_save` déclenche push FCM + broadcast WS.

**Réponse** : 201 + `MessageSerializer`, ou 400/403.

---

#### `POST /conversations/{conversation_id}/messages/media/`

Upload direct d'un fichier média (Premium uniquement).

- Gate `media_messaging` via `check_feature_availability`.
- Parser `MultiPartParser` + `FormParser`.
- Champ `media_file` requis, taille max 10 MB.
- Champ optionnel `text` (max 500), `media_type` (image/video/audio), `client_message_id`.
- Persiste le fichier avec le stockage Django configuré, puis crée le message avec le chemin et l'URL fournis par ce stockage.
- Supprime le blob si la création du message échoue ou si une course de déduplication retourne le message existant.

**Réponse** : 201 + `MessageSerializer` avec `media_url` renseigné.

---

#### `PUT /conversations/{conversation_id}/messages/mark-as-read/`

Marque en batch les messages reçus comme lus jusqu'à un message donné.

**Corps** : `last_read_message_id` (UUID, optionnel — si absent, tous les messages reçus sont marqués).

**Réponse** (200) : `{"messages_marked": N}`.

Déclenche `send_read_notification.delay(...)` si `N > 0`.

---

#### `PUT /conversations/{conversation_id}/messages/{message_id}/read/`

Marque un message individuel comme lu.

- Vérifie que l'appelant est le destinataire (pas l'expéditeur).
- Vérifie appartenance au match.
- Transitions autorisées : `sent`/`delivered` → `read`.

**Réponse** (200) : `{"message": "...", "read_at": "datetime"}`.

---

#### `DELETE /conversations/{conversation_id}/messages/{message_id}/`

Soft delete d'un message pour l'utilisateur courant.

- Accès : user doit être `user1` ou `user2` du match.
- Positionne `is_deleted_by_sender` ou `is_deleted_by_recipient`.
- Le message reste en base et visible par l'autre participant.

**Réponse** : 204 No Content.

---

#### `POST /conversations/{conversation_id}/typing/`

Met à jour l'indicateur de frappe.

**Corps** : `{"is_typing": true|false}`.

- Appelle `MessageService.update_typing_indicator` → DB + cache Redis (TTL 10 s si typing, suppression si stop).

**Réponse** (200) : `{"is_typing": true|false}`.

---

#### `GET /conversations/{conversation_id}/presence/`

Retourne le statut de présence de l'autre participant.

**Réponse** (200) :
```json
{
  "participant": {
    "user_id": "uuid",
    "is_online": true,
    "last_active": "datetime",
    "is_typing": false
  }
}
```

`is_online` = `last_active < 300s`. `is_typing` = vérifie le cache Redis.

---

### 3.2 Appels

Montés sous `/api/v1/calls/`. Gate premium vérifié par `Call.check_call_limit`.

#### `POST /calls/initiate`

Initier un appel audio/vidéo.

**Corps** :
```json
{
  "target_user_id": "uuid",
  "call_type": "audio|video",
  "offer_sdp": "string"
}
```

**Contrôles** :
1. `Call.check_call_limit(caller)` → premium requis + quota 30 min/jour.
2. Match ACTIVE entre caller et target.
3. Pas d'appel en cours sur ce match (`status IN [initiated, ringing, answered]`).
4. Crée `Call(status=ringing)`.
5. Déclenche `send_call_notification.delay(callee_id, caller_id, call_type, match_id)`.

**Réponse** (201) : `{"call_id": "uuid", "status": "ringing", "message": "..."}`.

---

#### `POST /calls/{call_id}/answer`

Répondre à un appel entrant.

**Corps** : `{"answer_sdp": "string"}`.

- Uniquement accessible par le `callee`.
- Transition : `ringing → answered`, enregistre `answered_at` + `answer_sdp`.

**Réponse** (200) : `{"call_id": "uuid", "status": "answered", "message": "..."}`.

---

#### `POST /calls/{call_id}/ice-candidate`

Ajouter un candidat ICE (négociation WebRTC).

**Corps** : `{"candidate": {dict WebRTC}}`.

- Accessible par caller ou callee.
- État requis : `ringing` ou `answered`.
- Ajoute `{"from_user_id", "candidate", "timestamp"}` à `Call.ice_candidates` (JSONField).

**Réponse** : 204 No Content.

---

#### `POST /calls/{call_id}/terminate`

Terminer un appel.

**Corps** : `{"reason": "declined|ended_by_caller|ended_by_callee|no_answer|connection_failed|duration_limit_reached"}`.

**Transitions** selon reason :

| Reason | Statut final |
|--------|-------------|
| `declined` | `declined` |
| `no_answer` (+ status=ringing) | `missed` |
| `connection_failed` / `duration_limit_reached` | `failed` |
| autres | `ended` |

- Calcule `duration_seconds` si `answered_at` renseigné et statut = `ended`.
- Crée un `Message(type=call_log)` résumant l'appel.

**Réponse** (200) : `{"call_id", "status", "duration_seconds", "message"}`.

---

#### `POST /conversations/calls/initiate-premium/`

Variante avec gate explicite `check_feature_availability(user, 'calls')`. Retourne un `CallSerializer` complet au lieu de la réponse minimaliste.

---

## 4. Serializers et validation

### `MessageSerializer`

Aliases de champs pour compatibilité frontend Flutter :

| Champ API | Source modèle |
|-----------|--------------|
| `message_id` | `id` |
| `conversation_id` | `match.id` |
| `sender_id` | `sender.id` |
| `sent_at` | `created_at` |
| `read_at_by_recipient` | `read_at` |

Champs calculés : `is_sending` (`status == SENDING`), `media_type` (retourne type si image/video/audio, sinon null), `is_mine` (compare `sender` au user de la requête).

---

### `ConversationSerializer`

Champs calculés :
- `other_user` — id, display_name, main_photo_url (photo principale du profil), is_online, last_active.
- `last_message` — preview 100 chars (ou "[Media]"), sender_id, sent_at, is_read_by_me.
- `unread_count_for_me` — via `Match.get_unread_count(request.user)`.

---

### `SendMessageSerializer`

**Validation contenu texte** :

1. Rejet si pattern dangereux détecté (regex insensible à la casse) :
   - `javascript\s*:`
   - `data:text/html`
   - `<\s*script`
   → 400 "Content contains unsupported or unsafe markup."

2. `strip_tags()` sur la valeur — supprime tout balisage HTML résiduel.

3. Validation cross-fields :
   - `type=text` + content vide → 400 "Content is required for text messages."
   - `type=image|video|audio` + media_file_path absent → 400 "Media file path is required."

---

### `SendMediaMessageSerializer`

Validation `media_file` : taille max 10 MB.

---

### Call serializers

| Serializer | Champs |
|-----------|--------|
| `InitiateCallSerializer` | `target_user_id (UUID)`, `call_type`, `offer_sdp` |
| `AnswerCallSerializer` | `answer_sdp` |
| `IceCandidateSerializer` | `candidate (DictField)` |
| `EndCallSerializer` | `reason (ChoiceField)` |
| `CallSerializer` | lecture complète + `caller_info`/`callee_info` |

---

## 5. Couche service

### `MessageService` — `messaging/services.py`

#### `get_conversation_messages(user, match, limit, before_id)`

1. Filtre soft-delete de chaque côté.
2. Pagination curseur sur `before_id` (filtre `created_at < before_message.created_at`).
3. Plafond 50 messages si non-premium (avant le curseur).
4. Lecture stricte sans effet de bord : ce GET ne modifie ni `status`, ni
   `read_at`, ni le compteur non lu, ni les notifications.

#### `send_message(sender, match, content, message_type, media_file_path, client_message_id)`

1. Vérifie `sender ∈ {match.user1, match.user2}`.
2. Vérifie `match.status == ACTIVE`.
3. **Déduplication** : si `client_message_id` existe → retourne l'existant sans créer.
4. Gate premium pour types média.
5. Crée `Message(status=SENT)`.
6. MAJ `match.last_message_at`, `match.last_message_preview`, `increment_unread(recipient)`.
7. Retourne `(message, None)` ou `(None, error_str)`.

#### `delete_message(user, message)`

Soft delete côté user. Retourne `False` si user n'est ni sender ni recipient.

#### `update_typing_indicator(user, match, is_typing)`

- `is_typing=True` → `update_or_create(TypingIndicator)` + `cache.set(key, True, 10)`.
- `is_typing=False` → supprime DB + `cache.delete(key)`.

#### `mark_messages_as_read(user, match, last_read_message_id)`

Marque en batch les messages de l'autre user jusqu'au message spécifié (ou
tous). Déclenche `send_read_notification.delay` et diffuse un événement
WebSocket `message.read` best-effort avec les IDs et l'horodatage persistés.

#### `mark_single_message_as_read(user, message)`

Vérifie que user est le destinataire. Transitions `sent`/`delivered` → `read`.
Déclenche `send_read_notification.delay` et le même événement WebSocket
`message.read` best-effort.

#### `create_media_message(sender, match, media_file, media_type, text, client_message_id)`

Calcule `media_file_path` et `media_url` depuis `MEDIA_URL`, délègue à `send_message`, puis met à jour `media_url` sur le message créé.

#### `get_typing_users(match, exclude_user)`

Interroge le cache Redis (`typing_{match_id}_{user_id}`) pour chaque participant. Retourne la liste des users en train de taper.

---

### `CallService` — `messaging/services.py`

#### `initiate_call(caller, match, call_type, offer_sdp)`

1. `Call.check_call_limit(caller)` → doit être premium, quota 30 min/jour.
2. Vérifie appartenance match + ACTIVE.
3. Vérifie absence d'appel actif (`status IN [initiated, ringing, answered]`).
4. Crée `Call(status=RINGING)`.
5. `send_call_notification.delay(callee_id, caller_id, call_type, match_id)`.
6. Retourne `(call, None)` ou `(None, error_str)`.

#### `answer_call(call, answer_sdp)`

Transition `ringing → answered`, enregistre `answered_at` + `answer_sdp`. Retourne `False` si état ≠ `ringing`.

#### `add_ice_candidate(call, candidate, from_user)`

Vérifie état (`ringing`/`answered`) et appartenance. Append `{from_user_id, candidate, timestamp}` dans `Call.ice_candidates`. Retourne `bool`.

#### `end_call(call, reason, ended_by)`

Détermine statut final selon reason. Calcule `duration_seconds`. Crée `Message(type=call_log)` résumant l'appel.

---

## 6. Temps réel — WebSocket

### Routing ASGI (`hivmeet_backend/asgi.py`)

```
ws/conversations/<uuid:conversation_id>/  →  ConversationConsumer
ws/notifications/                         →  UserNotificationConsumer
```

Stack : `ProtocolTypeRouter` → `AuthMiddlewareStack` → `URLRouter`.

### `ConversationConsumer` — `messaging/consumers.py`

**Authentification** (méthode `_authenticate_user`) :
1. Header `Authorization: Bearer <jwt>` — prioritaire.
2. Fallback : query string `?token=<jwt>` (clients incapables de setter les headers WS).
3. Décode via `rest_framework_simplejwt.tokens.AccessToken`, récupère `User` par `user_id`.
4. Ferme avec code `4000` si token invalide, `4001` si conversation non trouvée.

**Connexion** :
1. Authentifie le user.
2. Vérifie match ACTIVE via `_get_active_match()`.
3. Rejoint le groupe `conversation_{conversation_id}`.
4. Accepte la connexion.
5. Définit présence "online" en cache Redis (TTL 1h).
6. Broadcast `presence_update(status=online)` au groupe.

**Déconnexion** :
1. Quitte le groupe.
2. Efface présence du cache.
3. Broadcast `presence_update(status=offline)`.

---

### Messages entrants (côté client → serveur)

| Type WS entrant | Action |
|-----------------|--------|
| `message.send` | Appelle `MessageService.send_message` (signal post_save diffuse au groupe) |
| `typing.start` | Cache Redis TTL 10s + broadcast `typing_indicator(status=typing)` |
| `typing.stop` | Efface cache + broadcast `typing_indicator(status=stopped)` |
| `ping` | Répond `pong` avec timestamp |
| `ice.candidate` | Broadcast `ice_candidate` au groupe (sans persister via DB ici) |
| `offer` | Broadcast `webrtc_offer` au groupe |
| `answer` | Broadcast `webrtc_answer` au groupe |

---

### Messages sortants (channel layer → client)

| Handler du consumer | Type WS envoyé | Origine |
|--------------------|----------------|---------|
| `message_created` | `message.created` | Signal `post_save(Message)` |
| `message_read` | `message.read` | Marquage explicite REST d'un ou plusieurs messages |
| `typing_indicator` | `typing.indicator` | WS `typing.start/stop` |
| `presence_update` | `presence.update` | connect/disconnect |
| `ice_candidate` | `ice.candidate` | WS `ice.candidate` |
| `webrtc_offer` | `webrtc.offer` | WS `offer` |
| `webrtc_answer` | `webrtc.answer` | WS `answer` |
| `incoming_call` | `incoming_call` | Signal `post_save(Call)` status=ringing |
| `call_update` | `call_update` | Signal `post_save(Call)` status∈{answered,ended,declined} |

**Anti-echo** : les handlers de présence/typing/ice/webrtc filtrent l'événement
s'il provient du user lui-même (`if event['user_id'] == str(self.user.id):
return`). `message.read` est volontairement transmis à tous les clients de la
conversation, afin de synchroniser les éventuels seconds appareils du lecteur.

---

## 7. Notifications et tâches asynchrones

### Signals — `messaging/signals.py`

#### `handle_new_message` (post_save Message, created=True)

Skip si `message_type == call_log`.

1. **Push FCM** : `send_message_notification.delay(recipient_id, sender_id, preview, match_id)`.
2. **Notification DB** : crée `Notification(type='new_message', ...)` dans l'app `notifications` (résistant à l'exception).
3. **Broadcast WS** : `channel_layer.group_send(conversation_{match_id}, {type: message_created, ...})` via `async_to_sync`. Protégé par context manager `channel_layer_context` — si Redis est indisponible, log warning + continue.

#### `handle_call_update` (post_save Call)

- Status `ringing` → `group_send(type=incoming_call, call={id, caller_id, caller_name, call_type, match_id})`.
- Status `answered`/`ended`/`declined` → `group_send(type=call_update, call={id, status, end_reason})`.

---

### Tasks Celery — `messaging/tasks.py`

#### `send_message_notification(recipient_id, sender_id, message_preview, match_id)`

- Respecte `recipient.notification_settings['new_message_notifications']`.
- Construit payload via `notifications.payloads.message_payload(...)`.
- Envoie via `notifications.fcm.send_fcm_to_user(recipient, notification=..., data=...)`.

#### `send_call_notification(callee_id, caller_id, call_type, match_id)`

- Construit `Notification` + `data` avec `type=incoming_call`, `notification_type=INCOMING_CALL`.
- Configuré haute priorité : `AndroidConfig(priority='high', ttl=30)` + `APNSConfig(sound='ringtone.caf', content_available=True)`.
- Envoie via `send_fcm_to_user`.

#### `send_read_notification(recipient_id, reader_id, match_id, message_id)`

- Respecte `recipient.notification_settings['message_read_notifications']`.
- `notification_type=MESSAGE_READ`.
- Envoie via `send_fcm_to_user`.

> La tâche `send_match_notification` est intentionnellement dans `matching/tasks.py` (commentaire "avoid duplication").

---

## 8. Sécurité et gating premium

### Authentification

Tous les endpoints HTTP : `permission_classes = [IsAuthenticated]`.  
WebSocket : JWT dans header ou query string (voir §6).

### Contrôle d'accès aux conversations

Chaque endpoint vérifie que le match existe et que le user en est participant (helper `_get_active_match_for_user`). Un match non ACTIVE retourne 404.

### Features premium (app `subscriptions`)

| Feature | Gate | Endpoints concernés |
|---------|------|---------------------|
| Messages média | `media_messaging` | `POST .../messages/media/` uniquement |
| Appels audio/vidéo | `calls` + quota 30 min/jour | tous les endpoints `calls/` |
| Historique > 50 messages | premium flag | `GET .../messages/` (plafond levé pour premium) |

### Rate limiting

Défini dans `hivmeet_backend/security.py` :
```python
'conversations/.*/messages': (60, 60)  # 60 requêtes / 60 secondes
```

### Sanitization XSS

`SendMessageSerializer.validate_content` :
1. Rejet si pattern dangereux (`javascript:`, `data:text/html`, `<script`).
2. `strip_tags()` sur tout balisage HTML restant.

---

## 9. Tests

### `messaging/tests.py` — `MessagingApiDeterministicTests`

Suite de ~22 tests unitaires/intégration API (`APITestCase`). Fixtures : 3 users, 1 match ACTIVE.

| Test | Ce qui est vérifié |
|------|--------------------|
| `test_conversation_list_includes_unread_and_last_message` | count, unread_count_for_me, last_message, other_user dans la liste |
| `test_send_message_creates_message_and_increments_unread` | 201, création DB, incrémentation unread user2 |
| `test_send_message_deduplicates_by_client_message_id` | 2 appels → 1 seul message, même message_id retourné |
| `test_get_messages_does_not_mark_received_messages_as_read` | GET sans effet de bord sur le statut et les compteurs |
| `test_mark_single_message_as_read_endpoint` | PUT unitaire → status=read |
| `test_mark_messages_as_read_batch_endpoint` | PUT batch → 2 messages marqués, notif déclenchée |
| `test_delete_message_soft_delete_sender` | 204, is_deleted_by_sender=True |
| `test_typing_and_presence_flow` | POST typing + GET presence → is_typing=True |
| `test_json_message_endpoint_rejects_legacy_media_payload` | le JSON média hérité est rejeté avec 400 |
| `test_decommissioned_signed_upload_endpoint_returns_404` | l'endpoint URL signée supprimé retourne 404 |
| `test_multipart_media_upload_persists_file_and_returns_its_url` | fichier réellement persisté et URL renvoyée |
| `test_premium_user_can_send_media_message` | 201, message_type=image, media_url présente |
| `test_premium_user_can_initiate_call` | 201, Call créé, send_call_notification.delay appelée |
| `test_call_answer_ice_and_terminate_flow` | Flow complet : initiate → answer → ice-candidate → terminate → call_log créé |
| `test_non_premium_cannot_initiate_call` | 403 |
| `test_send_message_rejects_unsafe_markup` | 400 sur `<script>` dans content |
| `test_send_message_strips_safe_html_from_text_content` | 201, contenu strip_tags correctement |
| `test_send_message_notification_task_uses_tokens` | send_fcm_to_user appelé avec bon recipient |
| `test_send_read_notification_task_uses_tokens` | idem pour read |
| `test_send_call_notification_task_uses_tokens` | idem pour call |
| `test_handle_new_message_signal_dispatches_socket_and_notification` | delay + group_send avec payload exact |
| `test_handle_call_update_signal_dispatches_socket_event` | group_send incoming_call avec payload exact |
| `test_mark_single_message_as_read_endpoint` | Persistance, FCM et payload `message_read` exact |
| `test_mark_messages_as_read_batch_endpoint` | IDs, horodatage et broadcast batch exacts |
| `test_mark_messages_as_read_succeeds_when_channel_layer_is_unavailable` | Persistance REST intacte sans channel layer |
| `test_mark_messages_as_read_succeeds_when_receipt_broadcast_fails` | Persistance REST intacte si `group_send` échoue |

### `tests/test_websocket_messaging.py`

Tests WebSocket séparés, incluant le broadcast `message.read` vers tous les
clients connectés de la conversation.

---

## 10. Lacunes et limites connues

| # | Problème | Fichier | Impact |
|---|---------|---------|--------|
| 1 | **Archivage conversations non implémenté** | `views.py:ConversationListView` | `?status=archived` retourne une liste vide, pas d'archivage réel |
| 2 | **`MessageReaction` sans API** | `models.py` | Modèle présent mais aucun endpoint, serializer ni service |
| ~~4~~ | ~~**`mark_as_delivered` non câblé**~~ — **résolu le 2026-07-31** | `services.py` + les deux consumers | `MessageService.mark_incoming_as_delivered()` bascule `sent → delivered` à la connexion du socket conversation (cette conversation) ou du socket notifications (toutes les conversations actives), puis diffuse `message.delivered` / `message_delivered` |
| 5 | **Double chemin ICE candidates** | `consumers.py` + `views.py` | Les ICE candidates passent par WS (broadcast group) ET peuvent passer par REST (`/ice-candidate`), sans coordination explicite. Depuis le 2026-07-31, une sauvegarde d'ICE ne redéclenche plus `incoming_call`/`call_update` (garde sur `update_fields` dans `handle_call_update`) |
| 6 | **TODO push notification dans `send_message`** | `services.py:L155` | Commentaire `# TODO: Send push notification` — en réalité couvert par le signal `post_save`, mais trompeur |
| 8 | **TypingIndicator DB redondant avec cache** | `models.py` + `services.py` | Double write (DB + Redis) ; la table n'est pas purgée des indicateurs expirés. Depuis le 2026-07-31, `update_typing_indicator` diffuse aussi `typing_indicator` au groupe conversation, mettant l'endpoint REST à parité avec la voie WS |
| 9 | **`Call.status = INITIATED` non utilisé** | `models.py` | État déclaré mais `CallService.initiate_call` crée directement en `RINGING` |

---

*Rapport généré sur base d'exploration statique du code source. Vérification croisée recommandée avec `docs/API_DOCUMENTATION.md` et `docs/FRONTEND_MESSAGING_API.md` avant toute intégration frontend.*
