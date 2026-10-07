# AGENTS.md — rules for working in this repository

Read this first. `ORCHESTRATOR_IMPLEMENTATION_PLAN.md` is the binding source of truth; this file
is the short operational version. If they disagree, the plan wins.

## Ownership

| Agent | Owns | Must not edit |
|---|---|---|
| **A — Platform** | `infra_control/` (Python), `ansible/`, `tests/backend/`, `docs/providers/`, `docs/runbooks/`, authors `contracts/` | `frontend/`, `tests/frontend/`, `docs/design/` |
| **B — Experience** | `frontend/`, `tests/frontend/`, `docs/design/` | `infra_control/`, `ansible/`, `tests/backend/` |
| Shared (PR + human approval) | `contracts/`, `AGENTS.md`, `docs/QUESTIONS.md`, `.github/` | |

CI enforces this with `.github/workflows/path-guard.yml`. Need something changed on the other
side? Write it in your PR handoff note.

## Workflow

1. One task per branch: `agent-a/<task-id>-slug` or `agent-b/<task-id>-slug`. One task per PR.
2. Contract first. An endpoint or event exists only once it is merged in `contracts/`.
   Never return a field that is not in `contracts/openapi.yaml`.
3. Do not start a phase before the previous phase's exit gate passed.
4. Ambiguity → `docs/QUESTIONS.md` with a proposed default. Deviations → ADR in `docs/adr/`.
5. Every PR description ends with a **handoff note**: done, assumptions, remaining, what the
   other agent needs to know.
6. Staging only. `Provider Account` records with `is_staging = 1`; never production credentials.

## Commands (backend)

```bash
# from the app root (apps/infra_control)
ruff check . && ruff format --check .
mypy --strict infra_control
pytest tests/backend -m "not integration"      # unit tests, no Frappe site
pytest tests/backend -m contract               # OpenAPI + event schema validation
bench --site <site> run-tests --app infra_control   # Frappe integration tests
cd contracts/mock && npm ci && npm run mock    # Prism mock on :4010
cd contracts/mock && npm run realtime          # Socket.IO replay on :9000
```

Dev tooling: `pip install -e ".[dev]"` (inside the bench env: `env/bin/pip install -e "apps/infra_control[dev]"`).

## Non-negotiable engineering rules (backend)

- Nothing mutates infrastructure except an `Infra Job` run by the job engine through a provider
  adapter. API handlers and monitoring never call DigitalOcean, Press or SSH directly.
- One running job per server, enforced by a Redis lock, covered by a test.
- Capability check before every provider call. Unsupported → `NotSupported`
  (HTTP 409, `capability_missing`). Never a silent no-op.
- Provider-specific status strings never leave `infra_control/providers/<name>/`.
- Every Ansible role is idempotent (second Molecule run: `changed=0`).
- All job output passes `mask_secrets()` before storage or emission.
- High-risk playbooks need typed confirmation and the `Infra Admin` role.
- `site.migrate` and updates back up first and fail if the backup fails.
- External HTTP: timeout, bounded retries with jitter on 5xx/429, rate-limit aware.

## API conventions (see `contracts/README.md`)

- Base path `/api/method/infra_control.api.<module>.<fn>`.
- Success: the payload is the top-level JSON object (no `message` wrapper).
- Error: `{ "error": { "code", "message", "details" } }` with a meaningful HTTP status.
- Lists: `?limit=50&cursor=...` → `{ "items": [...], "next_cursor": string|null }`.
- Realtime: Frappe Socket.IO, namespace `/<site>`, events `infra:*`, payloads in `contracts/events/`.
