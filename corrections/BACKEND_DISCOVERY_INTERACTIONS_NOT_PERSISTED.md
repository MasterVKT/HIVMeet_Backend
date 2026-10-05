# Backend Change Required - Discovery interactions not persisted in history

## Summary
When a user performs new interactions from Discovery (`dislike`, and likely `like/super_like`), backend returns `201`, but:
1. Discovery exclusion counters do not increase.
2. History counts/lists (`my-passes`, `my-likes`) do not reflect newly created interactions.

This produces stale history lists on frontend even after refresh.

## Evidence from logs
- `POST /api/v1/discovery/interactions/dislike` returns `201`.
- Immediately after, Discovery recommendation service still logs same active interaction count:
  - Before: `Active interactions (is_revoked=False): 41`
  - After dislike: still `41`
- History endpoints still return unchanged totals:
  - `GET /api/v1/discovery/interactions/my-passes` => `Returning 20 passes`
  - `GET /api/v1/discovery/interactions/my-likes` => `Returning 15 likes`

## Affected endpoints
- `POST /api/v1/discovery/interactions/dislike`
- `POST /api/v1/discovery/interactions/like`
- `POST /api/v1/discovery/interactions/super-like`
- `GET /api/v1/discovery/interactions/my-passes`
- `GET /api/v1/discovery/interactions/my-likes`

## Expected behavior
After any successful interaction creation (`201`):
1. Interaction must be persisted as active (`is_revoked=false`) in canonical source used by history and discovery exclusion.
2. Discovery exclusion counters should include the new interaction immediately.
3. `my-passes`/`my-likes` should include the new record on first page with recent ordering.

## Suspected backend root causes
1. Interaction write path stores into a different table/source than history read path.
2. Upsert logic updates existing row without updating timestamp/order field used by history sorting.
3. Transaction commits delayed or filtered by query conditions (`is_revoked`, actor/target mismatch).
4. Discovery exclusion and history use mixed legacy + new models with inconsistent write/read contracts.

## Required backend checks
1. Verify canonical interaction model used by:
   - discovery exclusion
   - history listing
   - interaction creation endpoints
2. Verify write/read consistency for actor user and target profile ids.
3. Ensure created/updated timestamp used by history sorting is updated on new interaction action.
4. Ensure history ordering is deterministic and recent-first for page 1.

## Contract recommendation
### Request (existing)
- `POST /api/v1/discovery/interactions/dislike`
```json
{
  "profile_id": "<uuid>"
}
```

### Success response (recommended fields)
Status: `201`
```json
{
  "id": "<interaction_uuid>",
  "interaction_type": "dislike",
  "actor_user_id": "<uuid>",
  "target_user_id": "<uuid>",
  "is_revoked": false,
  "created_at": "2026-04-09T19:30:45.000Z",
  "updated_at": "2026-04-09T19:30:45.000Z"
}
```

### History list requirement
- `GET /api/v1/discovery/interactions/my-passes?page=1&page_size=20&order_by=recent`
- Must include newly created interaction immediately when action succeeded.

## Frontend status
Frontend mapping is working (JSON mapping logs confirm records parsed). Current UI refresh is implemented. Remaining inconsistency appears to be backend write/read contract.
