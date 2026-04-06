  # HIVMeet WebSocket Frontend Contract

For Flutter / Web frontend integration with real-time messaging.

Status: production-ready
Last updated: 2026-03-27

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
  "sent_at": "2026-03-27T14:05:50.337558+00:00",
  "client_message_id": "uuid-or-client-id"
}
```

### 4.2 Typing Indicator

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

### 4.3 Presence Update

Server -> other participant(s):

```json
{
  "type": "presence.update",
  "user_id": "uuid",
  "status": "online",
  "timestamp": "2026-03-27T14:05:49.739406+00:00"
}
```

Status values: `online`, `offline`

### 4.4 WebRTC Candidate Forwarding

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

### 4.5 WebRTC Offer Forwarding

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

### 4.6 WebRTC Answer Forwarding

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

### 4.7 Error Event

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

Latest run: `OK` (6 tests).
