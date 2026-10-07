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
