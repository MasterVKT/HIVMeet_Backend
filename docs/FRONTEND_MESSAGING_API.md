# HIVMeet Messaging — Frontend Integration Contract

**Audience**: Frontend AI agent / Flutter developers
**Authority**: This document is generated from the implemented backend. It supersedes any prior version of `FRONTEND_MESSAGING_API.md`.
**WebSocket contract**: `docs/MESSAGES_BACKEND_WEBSOCKET_FRONTEND.md` also valid; this document folds in all WS details so you only need this file.
**Last updated**: 2026-10-02
**Status**: Remédiation livrée — validation staging requise avant production

---

## 1. Authentication

Every REST endpoint requires:
```
Authorization: Bearer <jwt_access_token>
```

Obtain the JWT from `POST /api/v1/auth/firebase-exchange/`. All 401 responses mean the token is missing or expired — refresh and retry.

---

## 2. Base URL Conventions

```
REST:      https://api.hivmeet.com/api/v1/
WebSocket: wss://api.hivmeet.com/ws/conversations/{conversation_id}/
Local WS:  ws://localhost:8000/ws/conversations/{conversation_id}/
```

`conversation_id` is the **Match UUID** (not a separate Conversation model). It appears as `conversation_id` in all responses and must be passed as the UUID in the URL path.

---

## 3. Error Envelope

All error responses use:
```json
{
  "error": "Human-readable message",
  "details": { "field_name": ["validation error"] }
}
```
`details` is present only for 400 validation errors. For 401/403/404/429/500, only `error` is present.

---

## 4. REST Endpoints

### Phase 2 additions: message actions, read alerts and hiding

- `PATCH /api/v1/conversations/{conversation_id}/messages/{message_id}/`
  accepts `{"content":"text"}` and returns the canonical message with
  `edited_at`. It is limited to the Premium author of one intact text message
  during the first fifteen minutes after creation. Stable errors are
  `premium_required`, `edit_not_author`, `message_not_editable`, and
  `edit_window_expired`; the original message is unchanged on every error.
- A successful edit refreshes the conversation preview and sends
  `message.updated` after commit to the conversation WebSocket. Its payload is
  `{type, conversation_id, message_id, content, edited_at}`.
- `PUT /api/v1/conversations/{conversation_id}/restore/` is idempotent and
  returns `204`. It removes only the caller's hidden state. Hiding is also
  idempotent; only a subsequent incoming message restores the recipient's
  hidden state automatically.
- Read ticks remain available to all users. When the author has an active
  Premium subscription and has not explicitly set
  `message_read_notifications` to `false`, a read batch creates one persistent
  `message_read` notification. REST, FCM and the personal WebSocket reuse its
  UUID; the payload contains reader and batch metadata, never message content.

### Phase 2 additions: hiding, media and message deletion

- `DELETE /api/v1/conversations/{conversation_id}/` hides the conversation for
  the authenticated participant only. It is idempotent. A subsequent incoming
  message restores it only for that recipient.
- For an attachment, `media_url` and `media_download_url` designate the same
  authenticated API route. They are not signed URLs, bucket URLs or
  `/media/...` paths. `media_thumbnail_url` is `null` until an authorised
  thumbnail rendition exists. The client must fetch/render this route through
  its authenticated transport and must purge its temporary/cache copy on KYC
  loss, logout or message deletion.
- `POST /api/v1/conversations/{conversation_id}/messages/delete/` accepts:

```json
{"message_ids": ["uuid"], "scope": "for_me"}
```

  `for_me` removes selected sent or received messages only from the caller's
  history. `for_everyone` is atomic, requires an active Premium subscription,
  applies only to messages authored by the caller in the preceding 15 minutes,
  preserves a deletion marker, clears media storage, and returns a localized
  stable error code (`premium_required`, `global_delete_not_allowed`, etc.) on
  failure. No selected message changes when validation fails.
- New-message notifications use the persisted notification UUID in REST, FCM
  and `/ws/notifications/`. Deduplicate transitional legacy entries by
  `(type=new_message, message_id)`.

#### Phase 2 deployment and rollback

- Deploy backend migration `messaging.0004_message_global_deletion` before a
  client that sends `scope: "for_everyone"`. It is additive: existing message
  rows start with `is_deleted_for_everyone=false` and remain readable.
- The deployed development database has `0002_conversation_hidden_state` and
  `0004_message_global_deletion` applied. `0002` is the per-user hide state;
  `0004` adds the chronological global-deletion marker.
- A schema rollback is `python manage.py migrate messaging 0003_message_idempotency_and_unread_index` after the compatible application code
  is rolled back. It removes marker columns only; deleted media and cleared
  message contents are intentionally not reconstructed.
- No feature flag is needed for Phase 2: all new routes and fields are
  additive, and clients retain support for legacy relative media URLs and
  `message_<message_id>` notification identifiers during rollout. Deploy the
  backend before the compatible mobile client.
- The embedded media plugins require Android API 24+ and iOS 13+.

### 4.1 List Conversations

```
GET /api/v1/conversations/
```

**Auth**: required
**Query params**:

| Param | Valeurs | Défaut | Description |
|-------|---------|---------|-------------|
| `page` | entier >= 1 | `1` | Page à retourner |
| `page_size` | entier (1–50) | `20` | Nombre d'éléments par page |
| `status` | `all`, `unread`, `archived` | `all` | `unread` retourne uniquement les conversations dont le compteur de non lus est strictement positif pour l'utilisateur authentifié. `archived` retourne actuellement une liste vide (archivage non implémenté). Toute autre valeur répond `400` avec `{error, details}`. |

**Response 200**:
```json
{
  "count": 12,
  "next": "http://api.hivmeet.com/api/v1/conversations/?page=2",
  "previous": null,
  "results": [
    {
      "conversation_id": "uuid",
      "id": "uuid",
      "other_user": {
        "user_id": "uuid",
        "display_name": "Jane Doe",
        "main_photo_url": "https://...",
        "is_online": true,
        "last_active": "2026-05-21T14:00:00+00:00"
      },
      "last_message": {
        "message_id": "uuid",
        "content_preview": "Hello!",
        "sender_id": "uuid",
        "sent_at": "2026-05-21T14:00:00+00:00",
        "is_read_by_me": false
      },
      "unread_count_for_me": 2,
      "created_at": "2026-05-01T10:00:00+00:00",
      "last_message_at": "2026-05-21T14:00:00+00:00",
      "last_activity_at": "2026-05-21T14:00:00+00:00"
    }
  ]
}
```

**Notes**:
- `last_activity_at` equals `last_message_at` (alias field).
- Conversations with no messages yet are excluded.
- Ordered by `last_message_at` descending (most recent first).
- `is_online = true` when `last_active` is within the past 5 minutes.

---

### 4.1bis Global Unread Count

```
GET /api/v1/conversations/unread-count/
```

**Auth**: required
**Query params**: none

**Response 200**:
```json
{
  "unread_count": 7
}
```

Server-side sum of `unread_count_for_me` across **all** active, non-hidden
conversations. Use this for the global Messages-tab badge: summing the first
page of §4.1 caps at `page_size` and under-reports for users with unread
messages beyond page 1.

Refresh it on `new_message` / `message_read` events and on app resume.

---

### 4.2 Get Messages

```
GET /api/v1/conversations/{conversation_id}/messages/
```

**Auth**: required
**Query params**:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `before_message_id` | UUID | — | Cursor: return messages older than this |
| `limit` | int | 50 | Max messages to return |
| `page_size` | int | 50 | Alias for `limit` |

**Response 200**:
```json
{
  "count": 120,
  "next": "?before_message_id=<oldest-id>&limit=50",
  "previous": null,
  "results": [],
  "has_more": true,
  "show_premium_prompt": false
}
```

**Notes**:
- Each response is bounded to 50 messages. `show_premium_prompt=true` signals
  that the client may display the existing premium-history prompt.
- `next` is a relative query-string fragment, not an absolute URL.
- `next` is `null` on the last page reachable from the current cursor. Invalid
  `limit`, `page_size`, or `before_message_id` values return `400` with the
  standard `{error, details}` envelope.
- Fetching messages is read-only. Call the explicit mark-as-read endpoint once
  a received message has actually been displayed; this persists the receipt,
  notifies the sender, and broadcasts the `message.read` WebSocket event after
  commit.

---

### 4.3 Message Object Shape

All endpoints that return a message use this shape:

```json
{
  "message_id": "uuid",
  "id": "uuid",
  "client_message_id": "4d1d8a35-c8f8-42bd-8d73-3808f90e95f1",
  "conversation_id": "uuid",
  "sender_id": "uuid",
  "is_mine": true,
  "content": "Hello!",
  "message_type": "text",
  "media_url": null,
  "media_type": null,
  "media_thumbnail_url": null,
  "status": "sent",
  "sent_at": "2026-05-21T14:00:00+00:00",
  "created_at": "2026-05-21T14:00:00+00:00",
  "delivered_at": null,
  "read_at": null,
  "read_at_by_recipient": null,
  "is_sending": false
}
```

| Field | Type | Notes |
|-------|------|-------|
| `message_id` | UUID | Canonical server ID; same as `id` |
| `id` | UUID | Alias for `message_id` |
| `client_message_id` | string | Echo of the dedup key you provided |
| `conversation_id` | UUID | Match UUID |
| `sender_id` | UUID | Sender's user UUID |
| `is_mine` | bool | `true` if sent by the authenticated user |
| `content` | string | Text content; empty for pure media |
| `message_type` | enum | `text`, `image`, `video`, `audio`, `call_log` |
| `media_url` | string\|null | Authenticated API media route; never a storage URL |
| `media_type` | string\|null | `image`/`video`/`audio`, null for text |
| `media_thumbnail_url` | string\|null | Always `null` pending an authorised rendition; never a storage URL |
| `status` | enum | `sending`, `sent`, `delivered`, `read` |
| `sent_at` | ISO 8601 | Alias for `created_at` |
| `created_at` | ISO 8601 | Server creation timestamp |
| `delivered_at` | ISO 8601\|null | Delivery timestamp |
| `read_at` | ISO 8601\|null | Read timestamp |
| `read_at_by_recipient` | ISO 8601\|null | Alias for `read_at` |
| `is_sending` | bool | `true` only when `status == "sending"` |

---

### 4.4 Send Text Message

```
POST /api/v1/conversations/{conversation_id}/messages/
Content-Type: application/json
```

> **IMPORTANT — field name asymmetry**: the input field for message type is **`type`** (not `message_type`). The output object and all WS events use `message_type`. This is by design. Do not confuse the two.

**Request body**:
```json
{
  "client_message_id": "4d1d8a35-c8f8-42bd-8d73-3808f90e95f1",
  "type": "text",
  "content": "Hello!"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `client_message_id` | string | **yes** | Dedup key — resubmit same id = idempotent, returns existing message |
| `type` | enum | no (default `text`) | `text` only |
| `content` | string | if `type=text` | Max 1000 chars; HTML stripped; unsafe markup (script/data URI) rejected |

**Response 201**: Message object (§4.3)

**Response 400**: Validation error — content empty, unsafe markup, or media payload sent to this endpoint
**Response 404**: Conversation not found

**Deduplication**: If `client_message_id` matches an existing message in this conversation from this sender, the existing message is returned (idempotent, no duplicate created).

---

### 4.5 Mark Messages as Read (Bulk)

```
PUT /api/v1/conversations/{conversation_id}/messages/mark-as-read/
Content-Type: application/json
```

```json
{ "last_read_message_id": "uuid" }
```

`last_read_message_id` is optional. When omitted or null, **all** unread incoming messages are marked as read. When provided, it must identify an incoming message in this conversation; the server marks unread incoming messages up to and including its `(created_at, id)` position. A foreign, outgoing, or incoherent cursor returns `400` without disclosing where it belongs.

**Response 200**:
```json
{
  "messages_marked": 5,
  "unread_count_for_me": 0,
  "read_at": "2026-07-26T14:05:00+00:00"
}
```

---

### 4.6 Mark Single Message as Read

```
PUT /api/v1/conversations/{conversation_id}/messages/{message_id}/read/
```

No request body required.

**Response 200**:
```json
{
  "message": "Message marked as read",
  "messages_marked": 1,
  "unread_count_for_me": 0,
  "read_at": "2026-07-26T14:05:00+00:00"
}
```

**Response 403**: You are the sender (cannot mark own message as read)
**Response 404**: Message not found

---

### 4.7 Delete Message (Soft Delete)

```
DELETE /api/v1/conversations/{conversation_id}/messages/{message_id}/
```

**Response 204**: No content (success)
**Response 403**: You are not a participant
**Response 404**: Message not found

Soft delete — message is hidden for the deleting user only. The other participant still sees it.

---

### 4.8 Typing Indicator

```
POST /api/v1/conversations/{conversation_id}/typing/
Content-Type: application/json
```

```json
{ "is_typing": true }
```

`is_typing: false` clears the indicator. Also broadcast over WS to other participant.

**Response 200**:
```json
{ "is_typing": true }
```

---

### 4.9 Conversation Presence

```
GET /api/v1/conversations/{conversation_id}/presence/
```

**Response 200**:
```json
{
  "participant": {
    "user_id": "uuid",
    "is_online": true,
    "last_active": "2026-05-21T14:00:00+00:00",
    "is_typing": false
  }
}
```

`is_online = true` when `last_active` is within the past 5 minutes.

---

### 4.10 Send Media Message — Premium (Multipart only)

```
POST /api/v1/conversations/{conversation_id}/messages/media/
Content-Type: multipart/form-data
```

**Premium required** (subscription must have `media_messaging_enabled`). Non-premium → 402.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `media_file` | file | yes | Max 10 MB |
| `media_type` | enum | no (default `image`) | `image`, `video`, `audio` |
| `text` | string | no | Caption, max 500 chars |
| `client_message_id` | string | no | Dedup key |

**Response 201**: Message object (§4.3). The file is stored by the backend; no signed-upload endpoint exists.

---

### 4.11 Download One Message Attachment

```
GET /api/v1/conversations/{conversation_id}/messages/{message_id}/media/
```

**Auth**: required. An active KYC is required before the participant check.
The endpoint streams the protected file and never exposes its storage URL;
`401` is unauthenticated, `403 kyc_required` is authenticated without active
KYC, and a participant/access/file failure remains the privacy-safe `404`.

The initial request has no `Range` header and returns `200` with
`Accept-Ranges: bytes`, `Content-Length` and a safe `Content-Disposition`
filename. A resumed request sends one range such as `Range: bytes=12345-` and
returns `206` with `Content-Range`. An invalid or unavailable range returns
`416`; a non-participant, removed conversation, globally deleted message or
missing file returns the existing privacy-safe `404` response. A locked
Free-Free conversation returns its existing `403` access response.

The backend development server rejects direct `/media/messages/` paths (and
the sensitive KYC/profile-media prefixes). The production ingress/storage
configuration must enforce the same prohibition; there is no legacy
direct-media fallback.

Clients keep the resulting file in their private application storage. They may
offer an explicit open or system-share action after completion, but must not
write it to the device gallery or public Downloads directory automatically.

---

### 4.12 Calls

> **No trailing slash on call URLs**: `POST /api/v1/calls/initiate` not `/calls/initiate/`.

#### Initiate Call

```
POST /api/v1/calls/initiate
Content-Type: application/json
```

```json
{
  "target_user_id": "uuid",
  "call_type": "audio",
  "offer_sdp": "v=0\r\no=..."
}
```

`call_type`: `audio` or `video`

**Response 201**:
```json
{
  "call_id": "uuid",
  "status": "ringing",
  "message": "Call initiated. Waiting for response."
}
```

**Response 403**: Non-premium user or daily 30-min limit reached
**Response 404**: Target user not found, or no active match

#### Initiate Premium Call (Explicit Gate)

```
POST /api/v1/calls/initiate-premium/
```

Same request body. Adds an explicit subscription check (`audio_video_calls_enabled`). On success returns the full **Call Object** (§4.12 Call Object Shape).

#### Answer Call

```
POST /api/v1/calls/{call_id}/answer
Content-Type: application/json
```

Only the callee may answer.

```json
{ "answer_sdp": "v=0\r\no=..." }
```

**Response 200**:
```json
{ "call_id": "uuid", "status": "answered", "message": "Call connected." }
```

#### Add ICE Candidate

```
POST /api/v1/calls/{call_id}/ice-candidate
Content-Type: application/json
```

Both caller and callee may submit candidates.

```json
{
  "candidate": {
    "candidate": "candidate:...",
    "sdpMid": "0",
    "sdpMLineIndex": 0
  }
}
```

**Response 204**: No content

#### Terminate Call

```
POST /api/v1/calls/{call_id}/terminate
Content-Type: application/json
```

Both caller and callee may terminate.

```json
{ "reason": "ended_by_caller" }
```

Valid `reason` values: `declined`, `ended_by_caller`, `ended_by_callee`, `no_answer`, `connection_failed`, `duration_limit_reached`

**Response 200**:
```json
{
  "call_id": "uuid",
  "status": "ended",
  "duration_seconds": 142,
  "message": "Call ended."
}
```

#### Call Object Shape

```json
{
  "id": "uuid",
  "call_type": "audio",
  "status": "ended",
  "caller_info": { "user_id": "uuid", "display_name": "Alice" },
  "callee_info": { "user_id": "uuid", "display_name": "Bob" },
  "initiated_at": "2026-05-21T14:00:00+00:00",
  "answered_at": "2026-05-21T14:00:10+00:00",
  "ended_at": "2026-05-21T14:02:32+00:00",
  "duration_seconds": 142,
  "end_reason": "ended_by_caller"
}
```

Call `status` values: `ringing`, `answered`, `ended`, `declined`

---

## 5. WebSocket — Real-Time Messaging

### 5.1 Connection

```
wss://api.hivmeet.com/ws/conversations/{conversation_id}/
```

**Authentication** — two methods (use whichever WebSocket client supports):
1. Header: `Authorization: Bearer <jwt_access_token>`
2. Query string: `?token=<jwt_access_token>` (Flutter / browser fallback)

**Close codes**:

| Code | Meaning |
|------|---------|
| 4000 | Token missing or invalid |
| 4001 | User not a participant, or conversation not found/not active |
| 4999 | Internal server error |

### 5.2 Real-Time Delivery Guarantee

Both write paths deliver `message.created` to all connected WS participants **only after the database transaction commits**:

- **REST POST** → `MessageService.send_message` → `post_save` signal → `transaction.on_commit()` → `channel_layer.group_send(conversation_{id}, message_created)`.
- **WS `message.send`** → same service → same signal → same broadcast.

The sender **also** receives the `message.created` echo (to get the server-assigned `message_id` and reconcile optimistic state).

### 5.3 Client → Server Events

#### Send Text Message
```json
{
  "type": "message.send",
  "content": "Hello via WebSocket",
  "client_message_id": "4d1d8a35-c8f8-42bd-8d73-3808f90e95f1"
}
```
- `content` required, non-empty after trim.
- `client_message_id` optional but strongly recommended for dedup and optimistic reconciliation.
- Text only via WS. For image/video/audio, use REST §4.11.

#### Typing Start / Stop
```json
{ "type": "typing.start" }
{ "type": "typing.stop" }
```

#### Ping
```json
{ "type": "ping" }
```

#### WebRTC ICE Candidate
```json
{
  "type": "ice.candidate",
  "candidate": "candidate:...",
  "sdpMid": "0",
  "sdpMLineIndex": 0
}
```

#### WebRTC Offer
```json
{
  "type": "offer",
  "call_id": "uuid-optional",
  "offer": { "type": "offer", "sdp": "v=0..." }
}
```

#### WebRTC Answer
```json
{
  "type": "answer",
  "call_id": "uuid-optional",
  "answer": { "type": "answer", "sdp": "v=0..." }
}
```

### 5.4 Server → Client Events

#### message.created
Received by all participants when any message is persisted (via REST or WS).
```json
{
  "type": "message.created",
  "message_id": "uuid",
  "conversation_id": "uuid",
  "sender_id": "uuid",
  "content": "Hello!",
  "message_type": "text",
  "media_url": null,
  "media_type": null,
  "media_thumbnail_url": null,
  "sent_at": "2026-05-21T14:05:50+00:00",
  "client_message_id": "4d1d8a35-c8f8-42bd-8d73-3808f90e95f1"
}
```

Note: output field is `message_type` (not `type`).

#### message.updated
Sent after a committed server-authorized edit to both participants.
```json
{
  "type": "message.updated",
  "conversation_id": "uuid",
  "message_id": "uuid",
  "content": "Edited text",
  "edited_at": "2026-09-25T14:00:00+00:00"
}
```

#### typing.indicator
```json
{
  "type": "typing.indicator",
  "user_id": "uuid",
  "status": "typing"
}
```
`status`: `"typing"` or `"stopped"`. Sender does not receive their own typing events.

#### presence.update
```json
{
  "type": "presence.update",
  "user_id": "uuid",
  "status": "online",
  "timestamp": "2026-05-21T14:05:49+00:00"
}
```
`status`: `"online"` or `"offline"`. Self-events suppressed.

#### pong
```json
{ "type": "pong", "timestamp": "2026-05-21T14:05:50+00:00" }
```

#### ice.candidate (forwarded)
```json
{
  "type": "ice.candidate",
  "from_user_id": "uuid",
  "candidate": "candidate:...",
  "sdpMid": "0",
  "sdpMLineIndex": 0
}
```

#### webrtc.offer (forwarded)
```json
{
  "type": "webrtc.offer",
  "from_user_id": "uuid",
  "call_id": "uuid-or-null",
  "offer": { "type": "offer", "sdp": "v=0..." }
}
```

#### webrtc.answer (forwarded)
```json
{
  "type": "webrtc.answer",
  "from_user_id": "uuid",
  "call_id": "uuid-or-null",
  "answer": { "type": "answer", "sdp": "v=0..." }
}
```

#### incoming_call
Sent to all participants when a call enters ringing state. The caller does not receive this event.
```json
{
  "type": "incoming_call",
  "call": {
    "id": "uuid",
    "caller_id": "uuid",
    "caller_name": "Alice",
    "call_type": "audio",
    "match_id": "uuid"
  }
}
```

#### call_update
Sent to all participants when call status changes to answered, ended, or declined.
```json
{
  "type": "call_update",
  "call": {
    "id": "uuid",
    "status": "ended",
    "end_reason": "ended_by_caller"
  }
}
```
`end_reason` is non-null only when `status == "ended"`.

#### error
```json
{
  "type": "error",
  "message": "Message cannot be empty",
  "code": "EMPTY_MESSAGE"
}
```
Known codes: `INVALID_JSON`, `INTERNAL_ERROR`, `EMPTY_MESSAGE`, `CREATION_FAILED`, `SEND_FAILED`.

#### message.delivered
Emitted when the recipient's device comes online and their incoming messages
move `sent` → `delivered`.
```json
{
  "type": "message.delivered",
  "conversation_id": "uuid",
  "message_ids": ["uuid"],
  "delivered_at": "2026-07-31T14:05:50+00:00"
}
```
Triggered server-side when the recipient connects to
`/ws/conversations/{id}/` (that conversation) or to `/ws/notifications/`
(all active conversations). `delivered` still counts as unread, so unread
counters are unaffected.

---

## 5bis. WebSocket — User Notification Channel

```
WS /ws/notifications/
```

A **second socket, one per session** (not per conversation), carrying
everything that must reach the user outside the currently open conversation.
Server group is `user_{user_id}`. Same auth as §5.1 (`Authorization: Bearer`
header or `?token=` fallback); close code `4000` on missing/invalid token.

Without this channel, a user sitting on the conversation list receives no
WebSocket signal at all for an incoming message.

### Server → Client Events

| `type` | Payload keys |
|--------|--------------|
| `new_match` | `match_id`, `matched_user_id` |
| `like` / `super_like` | `notification_id` (REST Notification UUID), `from_user_id` (empty when recipient is not premium), `like_id`, `is_super` |
| `new_message` | `conversation_id`, `message_id`, `from_user_id`, `preview`, `unread_count` |
| `message_read` receipt | `conversation_id`, `reader_id`, `message_ids`, `read_at` |
| `message_read` alert (`notification_id` present) | `notification_id`, `conversation_id`, `reader_id`, `reader_name`, `representative_message_id`, `message_count`, `read_at` |
| `message_delivered` | `conversation_id`, `message_ids`, `delivered_at` |
| `incoming_call` | `call` object |
| `call_update` | `call` object |
| `pong` | `timestamp` |
| `error` | `message`, `code` |

For likes and super-likes, `notification_id` is identical in WebSocket, FCM,
and `GET /api/v1/notifications/`. Use it for the read/delete REST routes;
synthetic IDs such as `like_<user_id>` are legacy-only and must not be sent.

```json
{
  "type": "new_message",
  "conversation_id": "uuid",
  "message_id": "uuid",
  "from_user_id": "uuid",
  "preview": "Hello!",
  "unread_count": 3
}
```

`unread_count` is the recipient's unread count **for that conversation** after
this message. For the global badge use
`GET /api/v1/conversations/unread-count/`.

`message_read` and `message_delivered` are addressed to the **author** of the
messages, so their ticks update from anywhere in the app.

### Client → Server Events

Only `ping` is supported: `{"type": "ping"}` → `{"type": "pong", "timestamp": ...}`.
Malformed JSON is answered with an `error` frame (`INVALID_JSON`); any other
`type` is ignored silently.

### Token lifetime

The JWT is validated **only at connect** — there is no in-band refresh, by
design. With `ACCESS_TOKEN_LIFETIME = 60 min`, a session longer than an hour
sees exactly one reconnect caused by expiry. Fetch a fresh token on every
connect attempt, including automatic backoff reconnects.

### Deduplication with FCM

`new_message` is delivered over **both** this socket and FCM push; both can
fire for the same message. Deduplicate on `message_id` during the legacy
rollout and retain the persisted Notification UUID from `notification_id` for
REST read/delete actions. Server-side online presence does not suppress FCM.
Flutter suppresses only a foreground popup for the exact conversation currently
open; the conversation list and Notifications page still receive the alert.

---

## 6. Premium Gating Summary

| Feature | Gate |
|---------|------|
| Message history beyond 50 messages | `is_premium = true` |
| Send media messages (image/video/audio) | Active subscription with `media_messaging_enabled` |
| Audio/video calls (`/calls/initiate`) | `is_premium` + 30-min/day cap enforced by service |
| Audio/video calls (`/calls/initiate-premium/`) | Subscription with `audio_video_calls_enabled` |

Premium error:
```json
{ "error": "This feature requires a premium subscription." }
```
HTTP 402 from the subscription gate, or HTTP 403 from the service layer.

---

## 7. HTTP Status Code Reference

| Code | Meaning |
|------|---------|
| 200 | Success (read, update) |
| 201 | Resource created (message sent, call initiated) |
| 204 | Action succeeded, no body (delete, ICE candidate) |
| 400 | Validation error (`details` field present) |
| 401 | JWT token missing or expired |
| 402 | Premium subscription required |
| 403 | Forbidden (not owner, premium required from service layer) |
| 404 | Resource not found |
| 429 | Rate limit exceeded |
| 500 | Server error |

---

## 8. Critical Implementation Notes

1. **`client_message_id` is the dedup key** across REST and WS. Always generate a UUID client-side before sending, store it locally, and use the `message_id` from `message.created` to replace any optimistic local ID.

2. **Input vs output naming**: REST POST uses `"type"` (input). All responses and WS events use `"message_type"` (output). These are different field names for the same concept.

3. **WS text only**: WS `message.send` supports text messages only. Media requires REST (§4.11).

4. **WS sender echo**: The sender also receives `message.created` for their own message — this is intentional and provides the server-assigned `message_id`.

5. **Both paths deliver to WS**: REST-sent and WS-sent messages both trigger `message.created` to all connected participants in the conversation group.

6. **Calls require an active match**: `Match.status == "ACTIVE"` between the two users. No match → 404.

7. **Call URL format**: `/api/v1/calls/initiate` (no trailing slash), unlike conversation endpoints which use trailing slashes.

8. **Conversation ID = Match ID**: There is no separate Conversation model. The UUID used in all messaging URLs is the Match UUID.
