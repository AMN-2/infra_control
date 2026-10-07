# Job engine (A1.2)

Everything that changes infrastructure is an `Infra Job` run by `infra_control.job_engine.engine`
through a provider adapter (plan section 3). Flow:

1. `create_job()` validates role and risk (high risk needs `Infra Admin` and `confirm` = target
   name), the playbook's target doctype, the target's provider capability, `params` against the
   playbook's `params_schema`; writes an `Infra Audit Log` row for every outcome (denied, failed,
   success); stores the job with write-only params masked; enqueues on the RQ queue `infra`.
2. `run_job()` (worker) takes the Redis lock `infra:lock:server:<server>` (or `site:`/`bench:`
   for Frappe Cloud targets, `provider:` for account-level jobs). If another job holds it, the
   worker waits up to 2 minutes, then re-enqueues the job.
3. The adapter is called once through `Provider.call()` (capability check first) and returns an
   `OpRef`; the worker polls `get_status()` every 3 s, backing off to 15 s, mirrors steps into
   `Infra Job Step`, masks every output chunk, and emits `infra:job.step`, `infra:job.log` and
   `infra:job.updated`.
4. Terminal state: lock released, `infra:job.updated` emitted once with the final status, and
   `infra:inventory.changed` for the target (or the created document, ADR 0001).

## Worker setup

Add the queue to `sites/common_site_config.json` and run a dedicated worker:

```json
"workers": { "infra": { "timeout": 21600 } }
```

```bash
bench worker --queue infra
```

Crash recovery runs every minute from the scheduler (`infra_control.job_engine.recovery.run`):
`Running` jobs whose `worker_heartbeat` is older than `Infra Settings.job_heartbeat_timeout_minutes`
(default 5) are failed and their lock dropped.

## Dummy provider (Phase 1 exit gate, tests)

Set `"infra_use_dummy_provider": 1` in the site config to route every job to the in-memory
`DummyProvider`, which completes steps over successive polls without touching anything. Never
set it on a control plane that manages real servers.

## Secrets

Real params are kept in Redis under `infra:job:params:<job>` only until the job ends; the stored
document holds masked params. `mask_secrets()` runs on every chunk before storage or emission,
seeded with the provider token and the write-only params. See `tests/backend/test_masking.py`.

## Phase 1 exit gate run (2026-10-07)

The gate ("a dummy playbook runs on a staging server and its steps arrive live over Socket.IO")
was run on the dev bench against the existing staging site `ops-staging.localhost` instead of a
new `infra.localhost` (docs/QUESTIONS.md Q9: no DB root password was needed that way). The
capture is `captures/phase1_gate_2026-10-07.json`; the second run (JOB-00003) produced the same
sequence.

Setup, exactly as executed:

```bash
# bench-wide, additive: declares the RQ queue (a backup of the file sits next to it)
python3 - <<'PY'
import json; p = "sites/common_site_config.json"; c = json.load(open(p))
c.setdefault("workers", {}).setdefault("infra", {"timeout": 21600}); json.dump(c, open(p, "w"), indent=1)
PY
bench --site ops-staging.localhost install-app infra_control
bench --site ops-staging.localhost set-config infra_use_dummy_provider 1
# seed: System User with the three Infra roles + API key/secret, Provider Account DO-STAGING
# (is_staging=1, placeholder token), Server gate-app-01 -> SRV-0001
bench worker --queue infra
```

The client connected to `http://ops-staging.localhost:9000/ops-staging.localhost` (path
`/socket.io`, `Authorization: token <key>:<secret>`, `Origin: http://ops-staging.localhost:8000`,
`X-Frappe-Site-Name: ops-staging.localhost`), then called
`POST /api/method/infra_control.api.jobs.run` with `playbook=server.snapshot`,
`target_doctype=Server`, `target_name=SRV-0001`. Every event was validated against
`contracts/events/*.schema.json` on arrival.

| t (ms) | event | payload |
|---|---|---|
| 107 | `infra:job.updated` | `Queued`, progress 0 |
| 399 | `infra:job.updated` | `Running`, progress 0 |
| 473 | `infra:job.step` | idx 0 `Snapshot` → `Queued` |
| 475 | `infra:job.log` | idx 0, `Snapshot: ok` |
| 475 | `infra:job.step` | idx 0 `Snapshot` → `Success` |
| 477 | `infra:job.updated` | `Running`, progress 100 |
| 479 | `infra:job.updated` | `Success`, progress 100 |
| 479 | `infra:inventory.changed` | `Server` `SRV-0001` `updated` |

Result: job `Success`, 8/8 events valid, lock released, audit row written. Findings from the run:

1. **Fixed here:** adapters report timezone-aware UTC timestamps; `_write_step` passed them to a
   `Datetime` column and MariaDB (strict mode) rejected `2026-10-07T18:40:57+00:00`, failing the
   first run (JOB-00001). `_db_datetime()` now converts provider timestamps to naive system-time
   datetimes at the storage boundary; `test_step_timestamps_are_stored_naive_in_the_system_timezone`
   covers it. The in-memory unit tests could not see this; only a real MariaDB did.
2. **Operational:** Frappe caches the RQ queue list per gunicorn worker (`@lru_cache` on
   `get_queues_timeout`). After adding `workers.infra`, run `bench restart`; until then a
   worker forked before the change answers `jobs.run` with `Queue should be one of short,
   default, long`. The gate client retried until it reached a fresh worker because the shared
   dev bench was not restarted.
3. **Socket.IO on a non-default site:** the realtime server derives the site from the `Host`
   header and falls back to `default_site` for `localhost`/`127.0.0.1`, and rejects an `Origin`
   whose hostname differs from `Host`. Clients must connect through the site hostname (the SPA
   does this naturally when served from `/infra` on the site).

Clean-up on the dev bench, when the reviewer wants it: `bench --site ops-staging.localhost
uninstall-app infra_control`, remove the `workers.infra` key (or keep it for Phase 2), delete the
`infra.gate@ops-staging.localhost` user.
