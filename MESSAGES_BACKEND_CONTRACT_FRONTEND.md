# Messages Backend Contract Frontend

> **Média privé (phase KYC 2)** : `media_url` et `media_download_url` sont la
> route API authentifiée de téléchargement, jamais une URL signée, bucket ou
> `/media/...`. `media_thumbnail_url` est `null` tant qu'une rendition
> autorisée n'existe pas. Une requête authentifiée sans KYC actif reçoit
> `403 kyc_required`; le client doit utiliser son transport authentifié.

## 1. Enums
### MessageType
- `text`
- `image`
- `video`
- `audio`
- `call_log`

### MessageStatus
- `sending`
- `sent`
- `delivered`
- `read`
- `failed`

### CallType
- `audio`
- `video`

### CallStatus
- `initiated`
- `ringing`
- `answered`
- `ended`
- `declined`
- `missed`
- `failed`

### CallEndReason
- `declined`
- `ended_by_caller`
- `ended_by_callee`
- `no_answer`
- `connection_failed`
- `duration_limit_reached`

## 2. JSON Contracts

## 2.1 GET /api/v1/conversations/
Response:
```json
{
  "count": "integer",
  "next": "string|null",
  "previous": "string|null",
  "results": [
    {
      "conversation_id": "uuid",
      "id": "uuid",
      "other_user": {
        "user_id": "uuid",
        "display_name": "string",
        "main_photo_url": "string|null",
        "is_online": "boolean",
        "last_active": "datetime"
      },
      "last_message": {
        "message_id": "uuid",
        "content_preview": "string",
        "sender_id": "uuid",
        "sent_at": "datetime",
        "is_read_by_me": "boolean"
      },
      "unread_count_for_me": "integer>=0",
      "created_at": "datetime",
      "last_message_at": "datetime|null",
      "last_activity_at": "datetime|null"
    }
  ]
}
```

## 2.2 GET /api/v1/conversations/{conversation_id}/messages/
Response:
```json
{
  "count": "integer",
  "next": "string|null",
  "previous": "string|null",
  "results": [
    {
      "message_id": "uuid",
      "id": "uuid",
      "client_message_id": "string",
      "conversation_id": "uuid",
      "sender_id": "uuid",
      "is_mine": "boolean",
      "content": "string",
      "message_type": "MessageType",
      "media_url": "authenticated-api-url|null",
      "media_type": "image|video|audio|null",
      "media_thumbnail_url": "null",
      "status": "MessageStatus",
      "sent_at": "datetime",
      "created_at": "datetime",
      "delivered_at": "datetime|null",
      "read_at": "datetime|null",
      "read_at_by_recipient": "datetime|null",
      "is_sending": "boolean"
    }
  ],
  "has_more": "boolean",
  "show_premium_prompt": "boolean"
}
```

## 2.3 POST /api/v1/conversations/{conversation_id}/messages/
Request:
```json
{
  "client_message_id": "string(max=100, required)",
  "content": "string(max=1000, required for text)",
  "type": "text"
}
```

Response 201:
```json
{
  "message_id": "uuid",
  "id": "uuid",
  "client_message_id": "string",
  "conversation_id": "uuid",
  "sender_id": "uuid",
  "is_mine": true,
  "content": "string",
  "message_type": "MessageType",
  "media_url": "authenticated-api-url|null",
  "media_type": "image|video|audio|null",
  "status": "MessageStatus",
  "sent_at": "datetime",
  "is_sending": false
}
```

Errors:
- `400` validation
- `400` si un payload média est envoyé sur cet endpoint
- `404` conversation inconnue

Sanitation:
- Le backend retire les balises HTML du champ `content`.
- Les marqueurs de script/markup dangereux sont rejetes avec `400`.

## 2.4 POST /api/v1/conversations/{conversation_id}/messages/media/
Content-Type: multipart/form-data
- `media_file`: file required
- `media_type`: image|video|audio
- `text`: optional
- `client_message_id`: optional

Response 201: meme schema que Message.

## 2.5 PUT /api/v1/conversations/{conversation_id}/messages/mark-as-read/
Request:
```json
{
  "last_read_message_id": "uuid(optional)"
}
```

Response:
```json
{
  "messages_marked": "integer>=0",
  "unread_count_for_me": "integer>=0",
  "read_at": "datetime"
}
```
`read_at` n'est present que si `messages_marked > 0`.
`unread_count_for_me` est le compteur du match recalcule apres l'operation.

## 2.6 PUT /api/v1/conversations/{conversation_id}/messages/{message_id}/read/
Response:
```json
{
  "message": "string",
  "messages_marked": "integer>=0",
  "unread_count_for_me": "integer>=0",
  "read_at": "datetime"
}
```
`read_at` n'est present que si `messages_marked > 0`.

## 2.6bis GET /api/v1/conversations/unread-count/
Response:
```json
{
  "unread_count": "integer>=0"
}
```
Somme serveur sur toutes les conversations actives non masquees.

## 2.7 DELETE /api/v1/conversations/{conversation_id}/messages/{message_id}/
Response:
- `204 No Content`

## 2.8 POST /api/v1/conversations/{conversation_id}/typing/
Request:
```json
{
  "is_typing": "boolean"
}
```
Response:
```json
{
  "is_typing": "boolean"
}
```

## 2.9 GET /api/v1/conversations/{conversation_id}/presence/
Response:
```json
{
  "participant": {
    "user_id": "uuid",
    "is_online": "boolean",
    "last_active": "datetime",
    "is_typing": "boolean"
  }
}
```

## 2.10 Endpoint URL signée supprimé
`POST /api/v1/conversations/generate-media-upload-url/` n'est plus supporté et retourne `404`. Les médias utilisent exclusivement le multipart §2.4.

## 2.11 POST /api/v1/calls/initiate
Request:
```json
{
  "target_user_id": "uuid",
  "call_type": "CallType",
  "offer_sdp": "string"
}
```

Response:
```json
{
  "call_id": "uuid",
  "status": "CallStatus",
  "message": "string"
}
```

## 2.12 POST /api/v1/calls/{call_id}/answer
Request:
```json
{
  "answer_sdp": "string"
}
```

Response:
```json
{
  "call_id": "uuid",
  "status": "CallStatus",
  "message": "string"
}

## 2.13 POST /api/v1/calls/{call_id}/ice-candidate
Request:
```json
{
  "candidate": {
    "candidate": "string",
    "sdpMid": "string|null",
    "sdpMLineIndex": "integer|null"
  }
}
```

Response:
- `204 No Content`
```

## 2.13 POST /api/v1/calls/{call_id}/ice-candidate
Request:
```json
{
  "candidate": "object"
}
```

Response:
- `204 No Content`

## 2.14 POST /api/v1/calls/{call_id}/terminate
Request:
```json
{
  "reason": "CallEndReason"
}
```

Response:
```json
{
  "call_id": "uuid",
  "status": "CallStatus",
  "duration_seconds": "integer>=0",
  "message": "string"
}
```

## 3. Cas limites deterministes
- Deduplication: meme `client_message_id` retourne le meme message (pas de doublon).
- Lecture GET sans effet de bord : le client appelle l'endpoint de marquage comme lu lorsque le message est visible.
- Soft delete: suppression par utilisateur masque uniquement pour lui.
- Gratuit: historique borne a 50 messages.
- Premium: media et appels autorises.
- Limite appels premium: 30 minutes/jour.

## 4. Erreurs standard
Format recommande:
```json
{
  "error": "string",
  "details": {}
}
```

Codes:
- `200`, `201`, `204`
- `400`, `401`, `403`, `404`, `500`

## 5. Contrat WebSocket (aligne implementation)

Reference detaillee: `docs/MESSAGES_BACKEND_WEBSOCKET_FRONTEND.md`.

### 5.1 Endpoint et auth

- Production: `wss://api.hivmeet.com/ws/conversations/{conversation_id}/`
- Local: `ws://localhost:8000/ws/conversations/{conversation_id}/`
- Auth supportee:
  - Header `Authorization: Bearer <jwt_access_token>`
  - Fallback query string `?token=<jwt_access_token>`

Codes de fermeture (echec connexion):
- `4000`: token absent/invalide
- `4001`: utilisateur non autorise sur la conversation (ou conversation invalide)
- `4999`: erreur interne serveur

### 5.2 Envelope client

Le backend attend un JSON plat, sans wrapper `data` obligatoire.

Exemple:

```json
{
  "type": "message.send",
  "content": "Hello",
  "client_message_id": "4d1d8a35-c8f8-42bd-8d73-3808f90e95f1"
}
```

### 5.3 Evenements client -> serveur

- `message.send`
  - champs: `content` (requis, non vide apres trim), `client_message_id` (optionnel, recommande)
  - dedup: meme `(conversation, sender, client_message_id)` retourne le message existant
- `typing.start`
- `typing.stop`
- `ping` (reponse serveur: `pong`)
- `ice.candidate`
  - champs: `candidate`, `sdpMid`, `sdpMLineIndex`
- `offer`
  - champs: `call_id` (optionnel), `offer`
- `answer`
  - champs: `call_id` (optionnel), `answer`

### 5.4 Evenements serveur -> client

- `message.created`
  - champs: `message_id`, `conversation_id`, `sender_id`, `content`, `message_type`, `media_url`, `media_type`, `media_thumbnail_url`, `sent_at`, `client_message_id`
- `message.read`
  - champs: `reader_id`, `message_ids`, `read_at`
- `message.delivered`
  - champs: `conversation_id`, `message_ids`, `delivered_at`
- `incoming_call`
  - champs: `call` (`id`, `caller_id`, `caller_name`, `call_type`, `match_id`)
- `call_update`
  - champs: `call` (`id`, `status`, `end_reason`, `match_id`)
- `typing.indicator`
  - champs: `user_id`, `status` (`typing` | `stopped`)
- `presence.update`
  - champs: `user_id`, `status` (`online` | `offline`), `timestamp`
- `pong`
  - champs: `timestamp`
- `ice.candidate`
  - champs: `from_user_id`, `candidate`, `sdpMid`, `sdpMLineIndex`
- `webrtc.offer`
  - champs: `from_user_id`, `call_id`, `offer`
- `webrtc.answer`
  - champs: `from_user_id`, `call_id`, `answer`
- `error`
  - champs: `message`, `code`

Codes d'erreur WebSocket emis:
- `INVALID_JSON`
- `INTERNAL_ERROR`
- `EMPTY_MESSAGE`
- `CREATION_FAILED`
- `SEND_FAILED`

### 5.4bis Canal notifications utilisateur `/ws/notifications/`

Socket unique par session (pas par conversation), groupe serveur `user_{user_id}`.
Meme auth que 5.1, code de fermeture `4000` si token absent/invalide.
Porte tout ce qui doit atteindre l'utilisateur hors de la conversation ouverte.

Serveur -> client:
- `new_match` : `match_id`, `matched_user_id`
- `like` / `super_like` : `notification_id` (UUID de la ressource REST),
  `from_user_id` (vide si non-premium), `like_id`, `is_super`
- `new_message` : `conversation_id`, `message_id`, `from_user_id`, `preview`, `unread_count`
- `message_read` : `conversation_id`, `reader_id`, `message_ids`, `read_at`
- `message_delivered` : `conversation_id`, `message_ids`, `delivered_at`
- `incoming_call` : `call`
- `call_update` : `call`

Client -> serveur: `{"type": "ping"}` -> `{"type": "pong", "timestamp": ...}`.
Tout autre `type` est ignore silencieusement.

`new_message` arrive aussi par push FCM : dedupliquer sur `message_id`
(`notification_id` FCM = `msg_<message_id>`).

Pour un like ou super-like, FCM et WebSocket transportent exactement le même
`notification_id` UUID que `GET /api/v1/notifications/`. Les actions
`PUT /notifications/<id>/read/` et `DELETE /notifications/<id>/delete/`
doivent utiliser cet UUID, jamais un identifiant synthétique.

Details complets: `docs/MESSAGES_BACKEND_WEBSOCKET_FRONTEND.md` §7.

### 5.5 Regle de coherence documentaire

- Le present fichier donne la vue d'ensemble API messages.
- Le fichier `docs/MESSAGES_BACKEND_WEBSOCKET_FRONTEND.md` est la reference WebSocket detaillee et doit rester strictement coherent avec cette section.
