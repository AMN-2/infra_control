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
- Creation flows: `server.provision` targets a `Provider Account`, `site.create` targets a `Bench`; the
  new entity's fields go in `params`, and `Job.created` links to the new document on success
  (`docs/adr/0001-creation-playbooks-target-the-parent.md`).
- Capabilities are provider-level. The actions for a target come from `playbooks.list`, never from
  `capabilities` alone.
- High-risk confirmation: `confirm` = target name for `jobs.run`; `"<playbook key>:<target count>"`
  for `bulk.create`.
- Any endpoint may return `429 rate_limited` with `Retry-After`.

## Auth failures (verified on Frappe v15.98, `infra_control/infra_control/tests/test_auth_shape.py`)

| Situation | Status | Body |
|---|---|---|
| Invalid `Authorization: token` | 401 | Frappe shape, `exc_type: AuthenticationError` |
| No session, or expired / invalid `sid` cookie | 403 | Frappe shape, `exc_type: PermissionError`, **no** `error` key |
| Logged in, role lacks the right | 403 | `{ "error": { "code": "permission_denied", ... } }` |
| Stale CSRF token on POST | 400 | Frappe shape, `exc_type: CSRFTokenError` |

Client rule: `reauthenticate = status === 401 || (status === 403 && !("error" in body))`;
on `CSRFTokenError` reload the boot data (`window.infra_boot.csrf_token`) and retry once.

## Realtime transport

Frappe's Socket.IO server. The client connects to `<origin>/<site_name>` (namespace = site name)
with `path: "/socket.io"` and `withCredentials: true`; the `sid` cookie authenticates it. System
Users automatically join the site room, where all `infra:*` events are published. The event name
is the Socket.IO event; the payload is the message object exactly as described in `events/`.
