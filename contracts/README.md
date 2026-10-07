# contracts/

The binding interface between the backend (Agent A) and the frontend (Agent B). Plan section 6.

| File | What |
|---|---|
| `openapi.yaml` | OpenAPI 3.1 for every REST endpoint. Agent B generates `frontend/src/api/schema.d.ts` from it. |
| `events/*.schema.json` | JSON Schema (2020-12) for every realtime event payload; `events/index.json` maps event name to file. |
| `mock/` | Prism mock of the REST API plus a Socket.IO replay server for realtime scenarios. |

## Change process

1. Open a PR that touches only `contracts/` (either agent may author it).
2. The human reviewer approves it.
3. Only after merge may either agent implement the change.

CI runs `pytest tests/backend -m contract`, which validates the spec, checks every endpoint of plan
section 6.1 is present, validates every example against its schema and checks the event index.

## REST conventions

- Base path `/api/method/infra_control.api.<module>.<fn>`; `GET` with query params, `POST` with a JSON body.
- Auth: Frappe session cookie `sid` (+ `X-Frappe-CSRF-Token` on POST) or `Authorization: token key:secret`.
- Success: payload at the top level. Error: `{ "error": { "code", "message", "details" } }`.
- Lists: `?limit=50&cursor=...` -> `{ "items": [...], "next_cursor": string | null }`.
- Timestamps: RFC 3339 UTC with `Z`. Statuses: unified enums from plan section 5.
- `jobs.run`, `jobs.cancel`, `jobs.retry` return `{ "job": Job }`; bulk and alert mutations follow the same envelope pattern.

## Realtime transport

Frappe's Socket.IO server. The client connects to `<origin>/<site_name>` (namespace = site name)
with `path: "/socket.io"` and `withCredentials: true`; the `sid` cookie authenticates it. System
Users automatically join the site room, where all `infra:*` events are published. The event name
is the Socket.IO event; the payload is the message object exactly as described in `events/`.
