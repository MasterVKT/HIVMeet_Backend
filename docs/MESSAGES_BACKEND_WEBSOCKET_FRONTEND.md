  # HIVMeet WebSocket Frontend Contract

For Flutter / Web frontend integration with real-time messaging.

Status: contrat backend — intégration client authentifiée requise
Last updated: 2026-10-02

## 1. Endpoint And Auth

WebSocket URL:

- Production: `wss://api.hivmeet.com/ws/conversations/{conversation_id}/`
- Local: `ws://localhost:8000/ws/conversations/{conversation_id}/`

Authentication methods (implemented):

1. `Authorization: Bearer <jwt_access_token>` header
2. Query string fallback: `?token=<jwt_access_token>`

Close codes on connection failure:

- `4000`: missing or invalid token
- `4001`: user not allowed on this conversation (or conversation invalid)
- `4999`: internal server error

Notes:

- For browser/Flutter clients without WS custom headers, use query token fallback.
- `conversation_id` is the match id UUID.

## 2. Message Envelope

### 2.1 Global deletion event

When a Premium author retracts a message for everyone, both conversation
clients receive the following event. Keep the row in chronological order and
render a deletion marker instead of removing it:

```json
{
  "type": "message_deleted",
  "conversation_id": "uuid",
  "message_ids": ["uuid"]
}
```

Delivery state is monotone: `sent` means persisted by the server, `delivered`
means a recipient client is connected, and `read` means the conversation read
endpoint has acknowledged the incoming message.

Inbound messages sent by client are flat JSON objects:

```json
{
  "type": "message.send",
  "content": "Hello",
  "client_message_id": "4d1d8a35-c8f8-42bd-8d73-3808f90e95f1"
}
```

There is no mandatory `data` wrapper in current backend implementation.

## 3. Supported Client Events

### 3.1 Send Text Message

Client -> server:

```json
{
  "type": "message.send",
  "content": "Hello WebSocket",
  "client_message_id": "uuid-or-stable-client-id"
}
```

Rules:

- `content` is required and non-empty after trim.
- `client_message_id` is optional but recommended for deduplication.
- Duplicate `(conversation, sender, client_message_id)` returns existing message.

### 3.2 Typing Start

Client -> server:

```json
{
  "type": "typing.start"
}
```

### 3.3 Typing Stop

Client -> server:

```json
{
  "type": "typing.stop"
}
```

### 3.4 Ping

Client -> server:

```json
{
  "type": "ping"
}
```

Server -> client:

```json
{
  "type": "pong",
  "timestamp": "2026-03-27T14:05:50.339406+00:00"
}
```

### 3.5 WebRTC Candidate

Client -> server:

```json
{
  "type": "ice.candidate",
  "candidate": "candidate:...",
  "sdpMid": "0",
  "sdpMLineIndex": 0
}
```

### 3.6 WebRTC Offer

Client -> server:

```json
{
  "type": "offer",
  "call_id": "optional-call-id",
  "offer": {
    "type": "offer",
    "sdp": "v=0..."
  }
}
```

### 3.7 WebRTC Answer

Client -> server:

```json
{
  "type": "answer",
  "call_id": "optional-call-id",
  "answer": {
    "type": "answer",
    "sdp": "v=0..."
  }
}
```

## 4. Events Received From Server

### 4.1 Message Created

Server -> all participants of conversation group:

```json
{
  "type": "message.created",
  "message_id": "uuid",
  "conversation_id": "uuid",
  "sender_id": "uuid",
  "content": "Hello WebSocket",
  "message_type": "text",
  "media_url": null,
  "media_type": null,
  "media_thumbnail_url": null,
  "sent_at": "2026-03-27T14:05:50.337558+00:00",
  "client_message_id": "uuid-or-client-id"
}
```

The event is dispatched only after the message transaction commits. For a text
message, `media_url`, `media_type`, and `media_thumbnail_url` are all `null`.
For media, `media_url` and `media_download_url` are the same relative,
authenticated REST download route; `media_thumbnail_url` is `null`. They never
contain a bucket, signed URL, storage path or direct `/media/...` URL. A client
must resolve the route through its authenticated HTTP transport and drop any
temporary/cached bytes when KYC becomes inactive or on logout.

### 4.2 Message Read

Server -> all connected clients of the conversation group:

```json
{
  "type": "message.read",
  "reader_id": "uuid",
  "message_ids": ["uuid", "uuid"],
  "read_at": "2026-07-25T16:00:00.000000+00:00"
}
```

The event is emitted only after commit of a successful explicit REST mark-as-read
operation. `message_ids` contains the messages persisted as `read` with the
same `read_at` timestamp. It is intentionally sent to every connected client,
including the reader's other devices. Clients should update only messages sent
by the current user when `reader_id` is another participant.

The same fact is also pushed to the message author's personal channel
(`/ws/notifications/`, event `message_read`) so their ticks update even when
they are not on this conversation screen. See section 7.

### 4.3 Message Delivered

Server -> all connected clients of the conversation group:

```json
{
  "type": "message.delivered",
  "conversation_id": "uuid",
  "message_ids": ["uuid", "uuid"],
  "delivered_at": "2026-07-31T16:00:00.000000+00:00"
}
```

Emitted when the recipient's device comes online and their incoming messages
transition `sent` -> `delivered`. Two triggers, both server-side:

- the recipient connects to `/ws/conversations/{id}/` (scoped to that conversation);
- the recipient connects to `/ws/notifications/` (sweeps every active conversation).

This is the standard "second tick" semantic: `delivered` means the message
reached the recipient's device, not that they opened the chat. A `delivered`
message is still counted as unread, so unread counters are unaffected.

The same fact is pushed to the message author's personal channel
(`/ws/notifications/`, event `message_delivered`). See section 7.

### 4.4 Typing Indicator

Server -> other participant(s):

```json
{
  "type": "typing.indicator",
  "user_id": "uuid",
  "status": "typing"
}
```

or

```json
{
  "type": "typing.indicator",
  "user_id": "uuid",
  "status": "stopped"
}
```

Note: for `typing.start`, sender does not receive its own event.

### 4.5 Presence Update

Server -> other participant(s):

```json
{
  "type": "presence.update",
  "user_id": "uuid",
  "visibility": true,
  "is_online": true,
  "last_active": "2026-09-25T14:05:49.739406+00:00",
  "server_timestamp": "2026-09-25T14:05:49.739406+00:00"
}
```

A foreground device sends `presence.heartbeat` every 30 seconds. The server
aggregates all device sessions and expires an inactive session after 90 seconds.
When `visibility` is false, `is_online` is false and `last_active` is null;
clients clear the subtitle instead of retaining an earlier status.
### 4.6 WebRTC Candidate Forwarding

Server -> other participant(s):

```json
{
  "type": "ice.candidate",
  "from_user_id": "uuid",
  "candidate": "candidate:...",
  "sdpMid": "0",
  "sdpMLineIndex": 0
}
```

### 4.7 WebRTC Offer Forwarding

Server -> other participant(s):

```json
{
  "type": "webrtc.offer",
  "from_user_id": "uuid",
  "call_id": "optional-call-id",
  "offer": {
    "type": "offer",
    "sdp": "v=0..."
  }
}
```

### 4.8 WebRTC Answer Forwarding

Server -> other participant(s):

```json
{
  "type": "webrtc.answer",
  "from_user_id": "uuid",
  "call_id": "optional-call-id",
  "answer": {
    "type": "answer",
    "sdp": "v=0..."
  }
}
```

### 4.9 Error Event

Server -> client:

```json
{
  "type": "error",
  "message": "Message cannot be empty",
  "code": "EMPTY_MESSAGE"
}
```

Known codes emitted by current implementation:

- `INVALID_JSON`
- `INTERNAL_ERROR`
- `EMPTY_MESSAGE`
- `CREATION_FAILED`
- `SEND_FAILED`

### 4.10 Incoming Call

Server -> callee (the caller does not receive its own ring):

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

`call_type` is `audio` or `video`. Also delivered on the callee's personal
channel (section 7), which is the path that actually rings when the callee is
not on this conversation screen.

### 4.11 Call Update

Server -> conversation group and both participants' personal channels:

```json
{
  "type": "call_update",
  "call": {
    "id": "uuid",
    "status": "ended",
    "end_reason": "ended_by_caller",
    "match_id": "uuid"
  }
}
```

`status` is `answered`, `ended` or `declined`. `end_reason` is non-null only
for `ended`. Saves that cannot change the call state (for example persisting an
ICE candidate) do not emit this event.

## 5. Minimal Flutter Example

```dart
import 'dart:convert';
import 'dart:io';
import 'package:uuid/uuid.dart';

Future<WebSocket> connectConversationSocket({
  required String baseWsUrl,
  required String conversationId,
  required String accessToken,
}) async {
  final uri = '$baseWsUrl/ws/conversations/$conversationId/?token=$accessToken';
  return WebSocket.connect(uri);
}

void sendTextMessage(WebSocket ws, String content) {
  ws.add(jsonEncode({
    'type': 'message.send',
    'content': content,
    'client_message_id': const Uuid().v4(),
  }));
}

void sendTyping(WebSocket ws, bool isTyping) {
  ws.add(jsonEncode({'type': isTyping ? 'typing.start' : 'typing.stop'}));
}

void listen(WebSocket ws) {
  ws.listen((raw) {
    final msg = jsonDecode(raw as String) as Map<String, dynamic>;
    switch (msg['type']) {
      case 'message.created':
        // Render incoming/outgoing message
        break;
      case 'message.read':
        // Mark matching locally-sent messages as read when reader_id is another user
        break;
      case 'message.delivered':
        // Flip locally-sent messages in message_ids to the "delivered" tick
        break;
      case 'typing.indicator':
        // Update typing UI
        break;
      case 'presence.update':
        // Update online/offline UI
        break;
      case 'ice.candidate':
      case 'webrtc.offer':
      case 'webrtc.answer':
        // Forward to WebRTC layer
        break;
      case 'error':
        // Show backend error
        break;
    }
  });
}
```

## 6. Validation Status

Backed by automated tests in `tests/test_websocket_messaging.py`:

- token auth via header
- token auth via query fallback
- invalid token rejection
- unauthorized user rejection
- typing event broadcast
- message send + persistence
- read receipt broadcast to every connected conversation client

Plus `messaging/test_remediation.py::DeliveryReceiptWebSocketTests`:

- conversation socket connect marks incoming messages `delivered`
- notifications socket connect sweeps every active conversation
- delivery receipt reaches the author's personal channel
- `ping` -> `pong` on the notifications socket
- notifications socket rejects a connection without token

## 7. User Notification Channel (`/ws/notifications/`)

A second, session-long socket carrying everything that is **not** scoped to one
open conversation. One connection per session, not one per conversation.

- Production: `wss://api.hivmeet.com/ws/notifications/`
- Local: `ws://localhost:8000/ws/notifications/`

Same auth as section 1 (`Authorization: Bearer <jwt>` header or `?token=<jwt>`
fallback). Close code `4000` on missing/invalid token. Server group is
`user_{user_id}`.

### 7.1 Why it exists

The conversation group only reaches clients that already have that specific
chat open. Anything that must reach a user on the conversation list, on another
tab, or anywhere else in the app goes through this channel.

### 7.2 Events received from server

| `type` | Emitted by | Payload keys |
|---|---|---|
| `new_match` | `matching/signals.py` | `match_id`, `matched_user_id` |
| `like` | `matching/signals.py` | `notification_id` (REST Notification UUID), `from_user_id` (empty if recipient not premium), `like_id`, `is_super` |
| `super_like` | `matching/signals.py` | same as `like`, `type` is `super_like` |
| `new_message` | `messaging/signals.py` | `conversation_id`, `message_id`, `from_user_id`, `preview`, `unread_count` |
| `message_read` receipt | `messaging/services.py` | `conversation_id`, `reader_id`, `message_ids`, `read_at` |
| `message_read` Premium alert | `messaging/services.py` | `notification_id`, `conversation_id`, `reader_id`, `reader_name`, `representative_message_id`, `message_count`, `read_at`; no message content |
| `message_delivered` | `messaging/services.py` | `conversation_id`, `message_ids`, `delivered_at` |
| `incoming_call` | `messaging/signals.py` | `call` object (see 4.10) |
| `call_update` | `messaging/signals.py` | `call` object (see 4.11) |

The `notification_id` of a like or super-like is the persisted
`Notification.id`. The same UUID is sent through WebSocket and FCM so Flutter
can deduplicate both channels and address the read/delete REST routes.

`new_message`:

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

`unread_count` is the recipient's unread count **for that conversation** after
the message, read straight from the denormalized counter — usable to patch a
per-conversation badge without a REST round trip. For the global badge, use
`GET /api/v1/conversations/unread-count/`.

`message_read` is addressed to the **author** of the messages, so their ticks
flip to read from anywhere in the app:

```json
{
  "type": "message_read",
  "conversation_id": "uuid",
  "reader_id": "uuid",
  "message_ids": ["uuid"],
  "read_at": "2026-07-31T16:00:00.000000+00:00"
}
```

`message_delivered` is likewise addressed to the author (see 4.3 for when it
fires).

### 7.3 Events sent by client

Only `ping` is supported, same contract as the conversation socket:

```json
{"type": "ping"}
```

Reply:

```json
{"type": "pong", "timestamp": "2026-07-31T16:00:00.000000+00:00"}
```

Malformed JSON is answered with `{"type": "error", "code": "INVALID_JSON", ...}`.
Any other `type` is ignored silently.

### 7.4 Token lifetime

The JWT is validated **only at connect**. There is deliberately no in-band
token refresh: re-authenticating an already-open socket adds attack surface for
no functional gain. `ACCESS_TOKEN_LIFETIME` is 60 minutes, so a session longer
than an hour will see exactly one reconnect caused by token expiry. Clients must
fetch a fresh token on every connect attempt, including automatic backoff
reconnects.

### 7.5 Duplicate delivery with FCM

`new_message` is delivered over **both** this channel and FCM push. They are
independent paths and both can fire for the same message. The persisted
`Notification.id` is carried as `notification_id`; clients deduplicate by
`message_id` during the legacy rollout and preserve that UUID for notification
read/delete actions. A general online presence never suppresses FCM: only the
client that is visibly displaying the exact conversation suppresses its own
foreground popup.
