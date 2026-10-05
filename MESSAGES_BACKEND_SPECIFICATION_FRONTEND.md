# Messages Backend Specification for Frontend

## 1. Vue d'ensemble
Cette specification couvre l'integralite des API backend disponibles pour la page Messages:
- Conversations
- Messages
- Presence/typing
- Appels audio/video
- Regles premium
- Erreurs et comportements deterministes

Base URL:
- `/api/v1/conversations/` pour conversations/messages
- `/api/v1/calls/` pour appels

Authentification:
- Header obligatoire: `Authorization: Bearer <access_token>`

## 2. Audit Fonctionnel (Etat Reel Backend)
| # | Fonctionnalite | Etat |
|---|---|---|
| 1 | Liste conversations | OK |
| 2 | Tri par dernier message | OK |
| 3 | Filtre status active/archived | PARTIEL (archived retourne vide, pas de stockage archive dedie) |
| 4 | Pagination conversations | OK (pagination DRF) |
| 5 | Compteur non lus | OK |
| 6 | Apercu dernier message | OK |
| 7 | Info autre utilisateur | OK |
| 8 | Recuperer messages | OK |
| 9 | Envoyer message texte | OK |
| 10 | Envoyer message media | OK (premium) |
| 11 | Pagination infinie before_message_id | OK |
| 12 | Supprimer message (soft delete) | OK |
| 13 | Marquer lu batch | OK |
| 14 | Marquer lu single | OK |
| 15 | Indicateur frappe | OK |
| 16 | Presence conversation | OK |
| 17 | Auto read a la recuperation | OK |
| 18 | Initier appel | OK |
| 19 | Repondre appel | OK |
| 20 | ICE candidates | OK |
| 21 | Terminer appel | OK |
| 22 | Journal d'appel en message | OK |
| 23 | Limite 30 min/jour premium | OK |
| 24 | Notification FCM appel entrant | OK |
| 25 | Appels premium | OK |
| 26 | Medias premium | OK |
| 27 | Historique illimite premium | OK |
| 28 | Chiffrement E2E optionnel | MANQUANT |
| 29 | WebSocket premium temps reel | MANQUANT |
| 30 | Push FCM nouveaux messages | OK |
| 31 | Push message lu | OK |
| 32 | Push appel entrant | OK |
| 33 | Polling gratuit 30s | COTE FRONT (backend compatible HTTP) |
| 34 | Filtrage contenu inapproprie | PARTIEL (sanitation HTML/markup unsafe cote serializer, moderation avancee absente) |
| 35 | Moderation images | MANQUANT |
| 36 | Signalement utilisateur/message | MANQUANT |

## 3. Endpoints Conversations
### 3.1 Lister conversations
- `GET /api/v1/conversations/`
- Query params:
  - `page` (optionnel, defaut 1)
  - `page_size` (optionnel, defaut 20, max 50)
  - `status=all|unread|archived` (optionnel, defaut `all`)
    - `all` : toutes les conversations visibles
    - `unread` : uniquement celles dont `unread_count_for_me > 0`
    - `archived` : renvoie une liste vide (archivage non persiste)
    - toute autre valeur (dont `active`) renvoie **HTTP 400**

Reponse 200:
```json
{
  "count": 5,
  "next": "http://.../api/v1/conversations/?page=2",
  "previous": null,
  "results": [
    {
      "conversation_id": "uuid",
      "id": "uuid",
      "other_user": {
        "user_id": "uuid",
        "display_name": "Marie",
        "main_photo_url": "https://...",
        "is_online": true,
        "last_active": "2026-03-27T03:00:00Z"
      },
      "last_message": {
        "message_id": "uuid",
        "content_preview": "Salut, ca va ?",
        "sender_id": "uuid",
        "sent_at": "2026-03-27T03:00:00Z",
        "is_read_by_me": false
      },
      "unread_count_for_me": 3,
      "created_at": "2026-03-20T10:00:00Z",
      "last_message_at": "2026-03-27T03:00:00Z",
      "last_activity_at": "2026-03-27T03:00:00Z"
    }
  ]
}
```

### 3.2 Compteur global de non-lus
- `GET /api/v1/conversations/unread-count/`
- Auth requise. Aucun query param.

Reponse 200:
```json
{"unread_count": 7}
```

Somme serveur de `unread_count_for_me` sur **toutes** les conversations actives
et non masquees de l'utilisateur — contrairement a une somme calculee sur la
premiere page de `GET /api/v1/conversations/`, qui plafonne a `page_size`.
A utiliser pour le badge global de l'onglet Messages.

### 3.3 Upload média
Le flux URL signée est supprimé. Les médias sont envoyés directement au backend via le multipart décrit en §4.3.

## 4. Endpoints Messages
### 4.1 Recuperer messages
- `GET /api/v1/conversations/{conversation_id}/messages/`
- Query params:
  - `page` / `page_size`
  - `limit`
  - `before_message_id`

Response 200:
```json
{
  "count": 150,
  "next": "?before_message_id=...&page_size=50",
  "previous": null,
  "results": [
    {
      "message_id": "uuid",
      "id": "uuid",
      "client_message_id": "client-123",
      "conversation_id": "uuid",
      "sender_id": "uuid",
      "content": "Bonjour!",
      "message_type": "text",
      "media_url": null,
      "media_type": null,
      "sent_at": "2026-03-27T03:00:00Z",
      "read_at_by_recipient": null,
      "is_sending": false
    }
  ],
  "has_more": true,
  "show_premium_prompt": false
}
```

Note deterministe:
- La récupération est sans effet de bord ; marquer comme lu explicitement quand le message est visible.
- Gratuit: fenetre max 50 messages.
- Premium: historique non limite.

### 4.2 Envoyer message texte via endpoint principal
- `POST /api/v1/conversations/{conversation_id}/messages/`

Request texte:
```json
{
  "client_message_id": "client-123",
  "content": "Bonjour!",
  "type": "text"
}
```

Response 201:
```json
{
  "message_id": "uuid",
  "client_message_id": "client-123",
  "conversation_id": "uuid",
  "sender_id": "uuid",
  "content": "Bonjour!",
  "message_type": "text",
  "sent_at": "2026-03-27T03:00:00Z",
  "is_sending": false
}
```

Regles:
- Dedoublonnage strict par `client_message_id`.
- Media reserve premium (`403` si non premium).

### 4.3 Envoyer media (multipart)
- `POST /api/v1/conversations/{conversation_id}/messages/media/`
- `multipart/form-data`
  - `media_file`
  - `media_type`: image|video|audio
  - `text` (optionnel)
  - `client_message_id` (optionnel)

### 4.4 Marquer lu batch
- `PUT /api/v1/conversations/{conversation_id}/messages/mark-as-read/`

Request:
```json
{
  "last_read_message_id": "uuid"
}
```

Response 200:
```json
{
  "messages_marked": 12
}
```

### 4.5 Marquer lu single
- `PUT /api/v1/conversations/{conversation_id}/messages/{message_id}/read/`

Response 200:
```json
{
  "message": "Message marked as read",
  "read_at": "2026-03-27T03:10:00Z"
}
```

### 4.6 Supprimer message (soft delete)
- `DELETE /api/v1/conversations/{conversation_id}/messages/{message_id}/`
- Response: `204 No Content`

## 5. Presence et Typing
### 5.1 Typing
- `POST /api/v1/conversations/{conversation_id}/typing/`

Request:
```json
{
  "is_typing": true
}
```

Response 200:
```json
{
  "is_typing": true
}
```

Details:
- TTL backend: 10 secondes
- Si `is_typing=false`, suppression immediate

### 5.2 Presence
- `GET /api/v1/conversations/{conversation_id}/presence/`

Response 200:
```json
{
  "participant": {
    "user_id": "uuid",
    "is_online": true,
    "last_active": "2026-03-27T03:12:00Z",
    "is_typing": true
  }
}
```

## 6. Endpoints Appels
### 6.1 Initier
- `POST /api/v1/calls/initiate`

Request:
```json
{
  "target_user_id": "uuid",
  "call_type": "audio",
  "offer_sdp": "..."
}
```

Response 201:
```json
{
  "call_id": "uuid",
  "status": "ringing",
  "message": "Call initiated. Waiting for response."
}
```

### 6.2 Repondre
- `POST /api/v1/calls/{call_id}/answer`

Request:
```json
{
  "answer_sdp": "..."
}
```

### 6.3 ICE candidate
- `POST /api/v1/calls/{call_id}/ice-candidate`

Request:
```json
{
  "candidate": {"candidate": "...", "sdpMLineIndex": 0}
}
```

### 6.4 Terminer
- `POST /api/v1/calls/{call_id}/terminate`

Request:
```json
{
  "reason": "ended_by_caller"
}
```

Response 200:
```json
{
  "call_id": "uuid",
  "status": "ended",
  "duration_seconds": 95,
  "message": "Call ended."
}
```

## 7. Modeles Flutter (Reference)
```dart
class Message {
  final String messageId;
  final String conversationId;
  final String senderId;
  final String content;
  final MessageType messageType; // text,image,video,audio,call_log
  final String? mediaUrl;
  final String? mediaType;
  final DateTime sentAt;
  final DateTime? readAtByRecipient;
  final bool isSending;
}

class Conversation {
  final String conversationId;
  final UserInfo otherUser;
  final LastMessage? lastMessage;
  final int unreadCountForMe;
  final DateTime createdAt;
  final DateTime? lastActivityAt;
  final bool isArchived; // derive frontend (pas de champ persiste)
}
```

## 8. Erreurs API
- `400` validation/etat invalide
- `401` non authentifie
- `403` premium requis / action non autorisee
- `404` conversation/message/utilisateur/appel introuvable
- `500` erreur interne

Format pratique:
```json
{
  "error": "...",
  "details": {}
}
```

## 9. Scenarios Frontend
1. Ouvrir inbox:
   - GET conversations
2. Ouvrir thread:
   - GET messages
    - marquer explicitement les messages affichés comme lus
3. Envoyer message:
   - POST messages avec `client_message_id`
4. Typing indicator:
   - POST typing true/false
   - polling/refresh presence
5. Media upload:
    - POST multipart `messages/media/`

## 10. Limitations connues
- Archivage conversation non persiste au niveau modele Match (`status=archived` renvoie une liste vide).
- Push FCM nouveaux messages, lecture et appel entrant relies aux flux metier backend.
- Pas de chiffrement E2E.
- Pas de moderation contenu/image.
- Pas de endpoint report dans ce module.
- `MessageReaction` existe en modele mais n'expose ni endpoint ni serializer.
- Le JWT du WebSocket n'est valide qu'a la connexion : pas de refresh in-band,
  le client doit se reconnecter avec un token frais (cf.
  `docs/MESSAGES_BACKEND_WEBSOCKET_FRONTEND.md` §7.4).
- `Call.status = initiated` est declare mais jamais utilise : `CallService.initiate_call`
  cree directement en `ringing`.
