# Backend — Real-Time Messaging Requirements (Session 2)

**Date**: 2026-07-30
**Author**: Frontend session (Claude), read-only access to `d:\Projets\HIVMeet\env\hivmeet_backend`
**Context**: Finishing the real-time messaging feature ([HANDOFF_REALTIME_MESSAGING_SESSION2.md](HANDOFF_REALTIME_MESSAGING_SESSION2.md)) surfaced a hard backend gap plus several smaller contract issues. This report lists exactly what to change, with file:line references and payload shapes. Nothing here has been applied — the backend was only read, per the access granted for this session.

---

## P0 — `new_message` never reaches `/ws/notifications/`

### The problem

`notifications/consumers.py:79-86` (`UserNotificationConsumer.new_message`) is a fully-implemented event handler with **zero producer**. The only site that broadcasts a new message is `messaging/signals.py:88-112` (`dispatch_new_message_after_commit`), and it sends exactly one `group_send`:

```python
async_to_sync(channel_layer.group_send)(
    f"conversation_{instance.match_id}",
    {"type": "message_created", ...}
)
```

That only reaches clients currently connected to `/ws/conversations/{match_id}/` — i.e. only a user who already has that specific chat screen open. A user sitting on the conversation list, on another tab, or with the app merely foregrounded elsewhere gets **no WebSocket signal at all** for an incoming message. Confirmed by grep: the only `group_send` calls targeting a `user_{id}` group anywhere in the backend are in `matching/signals.py` (`new_match`, `like`, `super_like`) — `messaging/` never touches that group.

This is the root cause of handoff issues #5 (conversation list not updating) and #6 (badge not updating). The frontend has worked around it this session with a 3-layer strategy (WebSocket + FCM foreground push + resume-time reconciliation — FCM already covers `new_message` today via `messaging/tasks.py`), but WebSocket is the only channel with sub-second latency and works without a registered device token, so this patch is worth applying.

### The fix

Add a second `group_send` in `dispatch_new_message_after_commit` (`messaging/signals.py:88-112`), right next to the existing one:

```python
with channel_layer_context() as channel_layer:
    if channel_layer:
        try:
            async_to_sync(channel_layer.group_send)(
                f"conversation_{instance.match_id}",
                { ... existing message_created payload, unchanged ... }
            )
        except Exception:
            logger.warning('Message websocket dispatch failed: message_id=%s', instance.id)

        if recipient is not None:
            try:
                async_to_sync(channel_layer.group_send)(
                    f"user_{recipient.id}",
                    {
                        "type": "new_message",
                        "conversation_id": str(instance.match_id),
                        "message_id": str(instance.id),
                        "from_user_id": str(instance.sender_id),
                        "preview": preview,
                        "unread_count": recipient_unread_count,  # see note below
                    }
                )
            except Exception:
                logger.warning('User-notification websocket dispatch failed: message_id=%s', instance.id)
```

Notes:
- `recipient` and `preview` are already computed earlier in the function (lines 57-58) — reuse them, don't recompute.
- `recipient_unread_count`: pull it from `instance.match.get_unread_count(recipient)` (the same helper `matching/models.py:230` backs `unread_count_for_me` in the REST serializer) so the frontend can trust the count without an extra round trip. If that's inconvenient at this call site, omit the field — the frontend already reconciles via `GET /api/v1/conversations/` regardless, it's a nice-to-have.
- `UserNotificationConsumer.new_message` (`notifications/consumers.py:79-86`) already sends exactly these keys (`conversation_id`, `from_user_id`, `preview`) to the client — **no consumer change needed**, add `message_id` and `unread_count` to both the consumer's `send` payload and this dict if you include them.
- Wrap in the same `channel_layer_context()`/try-except pattern already used everywhere else in this file — a Redis hiccup must not break message persistence or the REST response.

### Frontend contract (already implemented, ready today)

`lib/core/services/notification_websocket_service.dart` parses `new_message` on `/ws/notifications/` with exactly this shape:
```json
{"type": "new_message", "conversation_id": "...", "from_user_id": "...", "preview": "..."}
```
`message_id` and `unread_count` are optional extras the frontend does not yet read — add them if convenient, but they are not blocking.

---

## P0 — `message_read` never reaches the sender outside the conversation

`messaging/services.py` (`_broadcast_read_receipt`, called from `MessageService.mark_as_read`) only does `group_send` to `conversation_{match.id}`. If the message sender isn't currently viewing that conversation, their sent message never flips from ✓✓ gray to ✓✓ purple until they reopen the chat (which re-fetches via REST and gets the correct status anyway — so this is a staleness issue, not a correctness one, but it defeats the point of a read receipt).

**Fix**: mirror the P0 fix above — add a `group_send` to `user_{sender.id}` with `type: "message_read"` in the same broadcast call, and add a `message_read` handler to `UserNotificationConsumer` (`notifications/consumers.py`) forwarding `conversation_id`, `message_ids`, `read_at`. The frontend's `NotificationWebSocketService` already parses this event type (see the switch in `_onRawMessage`) — no frontend change needed once the backend sends it.

---

## P1 — No server-side total-unread-count endpoint

The frontend's global badge (`UnreadCubit`, new this session) currently sums `unread_count_for_me` across `GET /api/v1/conversations/?status=all&page=1&page_size=20` — i.e. **only the 20 most recent conversations**. This is a reasonable approximation (unread conversations bubble to the top by `updated_at`) but is not exact for a user with >20 active conversations and unread messages beyond the first page.

**Requested**: `GET /api/v1/conversations/unread-count/` → `{"unread_count": <int>}`, summing `user1_unread_count`/`user2_unread_count` across *all* the user's active matches server-side. Same auth/permission model as the existing conversation endpoints. Low cardinality query (one aggregate over `Match` rows for the user), should be cheap.

---

## P1 — FCM `notification_id` collision for `new_message`

`messaging/tasks.py:32` (`send_message_notification`) builds:
```python
notification_id=f'msg_{message_id}'  # sender_id is actually what's passed as message_id here
```
Tracing the call site (`messaging/signals.py:59-64`): `send_message_notification.delay(recipient.id, instance.sender.id, preview, str(instance.match.id))` — the task's `message_id` parameter is actually bound to `instance.sender.id`. So every push notification's `notification_id` is `msg_<sender_uuid>` — **identical for every message from the same sender**, regardless of which message it actually is.

This disagrees with the DB-persisted `Notification.data.notification_id` computed in `messaging/signals.py:80`, which correctly uses `f'msg_{instance.id}'` (the actual message id). The two code paths should agree.

**Fix**: in `messaging/tasks.py`, rename the task's parameter (or fix the call site) so the FCM payload's `notification_id` is built from the actual message id, not the sender id. This also unblocks exact WS↔FCM dedup on the frontend (see next item).

**Frontend impact**: `RealtimeEventBus` currently dedupes WS vs. FCM `new_message` events by `conversation_id` within a 2s window (not by message id, since FCM's `notification_id` isn't a reliable per-message key today). Once fixed, dedup could tighten to the actual message id if useful — not required, current window-based approach already produces correct behavior.

---

## P1 — Message `status` never reaches `delivered`

`docs/MESSAGING_BACKEND_STATE.md` §10 already flags this internally: `mark_as_delivered` exists on the `Message` model but nothing calls it. In practice `status` only ever transitions `sent` → `read`. The frontend's `MessageBubble` renders three states (✓ sent, ✓✓ gray delivered, ✓✓ purple read) but the middle one is currently unreachable from the backend.

**Fix suggestion**: call `message.mark_as_delivered()` (or equivalent) from `ConversationConsumer.connect()` (`messaging/consumers.py`) for any of the recipient's unread messages when they connect to the conversation socket — that's the natural "delivered" signal (client is online and subscribed). Broadcast a `message.delivered` WS event (new `type`) so the sender's open chat updates live, same pattern as `message.read`.

---

## P2 — `UserNotificationConsumer` has no `receive()`

`notifications/consumers.py`'s `UserNotificationConsumer` doesn't override `receive()`, so it silently drops anything a client sends (including a `ping`). `ConversationConsumer` replies to `ping` with `pong` (`messaging/consumers.py:128-167`); the notifications socket has no equivalent, so the frontend can't application-level-verify liveness on this specific connection (it relies on `dart:io` `WebSocket.pingInterval` protocol pings instead, which works but is a lower-level signal).

**Suggested**: add a minimal `receive()` handling `{"type": "ping"}` → `{"type": "pong", "timestamp": ...}`, matching the conversation consumer's contract.

---

## P2 — WS JWT expires in 60 minutes, no in-band refresh

`ACCESS_TOKEN_LIFETIME = 60 min` (`settings.py`). Neither consumer supports refreshing the token over an established connection — the only way to renew is to reconnect with a fresh token. The frontend now handles this correctly (both `ChatWebSocketService` and `NotificationWebSocketService` re-fetch a token via `AuthenticationService.getAccessToken()` on every reconnect attempt, including scheduled backoff reconnects), so this is not blocking, but a long-lived foreground session (>60 min) will cause one reconnect cycle purely from token expiry. If that's undesirable, consider either a longer WS-specific token lifetime or an in-band `{"type": "token.refresh", "token": "..."}` client message that re-validates and updates `self.user`/`self.scope` without dropping the socket.

---

## P2 — `POST /conversations/{id}/typing/` does not broadcast

The REST endpoint (`messaging/views.py`, `typing_indicator`) persists/returns `{"is_typing": bool}` but never touches the channel layer — only the WebSocket messages `typing.start`/`typing.stop` (`messaging/consumers.py`) actually broadcast `typing_indicator` to the conversation group. The frontend already only uses the WS path for this (see `ChatWebSocketService.sendTyping`), so this isn't currently causing a bug, but the REST endpoint's existence is misleading (a caller might reasonably expect it to notify the other participant). Either wire it to `group_send` for parity, or mark it deprecated/internal in `docs/MESSAGES_BACKEND_WEBSOCKET_FRONTEND.md`.

---

## P2 — Incoming calls invisible unless the callee's conversation socket is already open

`incoming_call` / `call_update` (`messaging/signals.py:115-158`) broadcast only to `conversation_{match_id}`. A callee who isn't currently viewing that chat never sees the WS event — the FCM push (`send_call_notification`, `notifications/fcm.py`) is the only real ring path today. If a WebRTC screen is ever built off the WS event alone (the frontend currently has a `// TODO: Implémenter les appels WebRTC` placeholder — no call UI wired up yet), it will need the same `user_{id}` broadcast pattern as the P0 items above.

---

## Documentation drift (no code change, just flag for whoever maintains these)

- `ENDPOINTS_COMPLETE_DOCUMENTATION.md` (messaging section, lines ~643-768) is badly stale: wraps responses in `{"conversations":[...]}` / `{"messages":[...]}` (reality: `{count,next,previous,results}`), calls the unread field `unread_count` (reality: `unread_count_for_me`), documents a mark-as-read body of `{"message_ids":[...]}` (reality: `{"last_read_message_id": "uuid"}`), and has no WebSocket section at all.
- `MESSAGES_BACKEND_CONTRACT_FRONTEND.md` §2.5/§2.6: mark-as-read response shapes omit `unread_count_for_me` and the conditional `read_at`. §5.4 omits `message.read`, `incoming_call`, `call_update` from the server→client event list (they exist in code).
- `MESSAGES_BACKEND_SPECIFICATION_FRONTEND.md` §3.1 documents `status=active|archived` for the conversation list filter — the serializer (`messaging/serializers.py:205-219`) only accepts `all|unread|archived`; `status=active` returns HTTP 400.
- `docs/MESSAGES_BACKEND_WEBSOCKET_FRONTEND.md` (2026-07-25) is the most accurate WS doc and matches the code closely — it's just missing `incoming_call`/`call_update` from its event table.

---

## Summary for planning

| Priority | Item | Effort | Unblocks |
|---|---|---|---|
| P0 | `new_message` → `user_{id}` group_send | ~15 lines, 1 file | Real-time conversation list + badge without depending on FCM |
| P0 | `message_read` → `user_{sender.id}` group_send + consumer handler | ~15 lines, 2 files | Read receipts update outside the open chat |
| P1 | `GET /api/v1/conversations/unread-count/` | New view + route | Exact global badge (currently approximated from page 1) |
| P1 | Fix FCM `notification_id` for new_message | 1-line param fix | Reliable WS/FCM dedup, correct per-message push id |
| P1 | Wire `mark_as_delivered` + `message.delivered` WS event | Moderate | Makes the ✓✓ gray "delivered" state reachable |
| P2 | `ping`/`pong` on `UserNotificationConsumer` | ~10 lines | Application-level liveness check on notifications socket |
| P2 | In-band WS token refresh (optional) | Design + moderate | Avoids one reconnect per hour on long sessions |
| P2 | `POST .../typing/` broadcast or deprecate | Small | Contract clarity |
| P2 | `incoming_call`/`call_update` → `user_{id}` too | ~15 lines | Needed once WebRTC call UI is actually built |
| Doc | Refresh 3 stale docs listed above | Writing only | Prevents future frontend work coding against wrong contracts |
