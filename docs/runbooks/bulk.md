# Bulk operations: backup → canary → batches (A3.4)

A bulk operation runs one playbook over many targets with a fixed safety sequence (plan 9.3).
Nothing here touches a provider directly: every unit of work is a child `Infra Job` run through the
job engine, so the one-job-per-server lock, masking, audit and realtime all apply unchanged.

## The sequence

```
create ──▶ backup (every Site target) ──▶ canary (batch 0) ──▶ batch 1 ──▶ … ──▶ batch N ──▶ done
                 │ any backup fails           │ canary fails         │ batch fails + policy=halt
                 ▼                            ▼                      ▼
               Halted                       Halted                 Halted
```

| Step | Rule |
|---|---|
| Backup | Unless the playbook is itself a backup (`backup` in its key), `site.backup` runs for every Site target first. One failed backup halts the whole operation (core rule: updates back up first and fail if the backup fails). |
| Canary | `canary_target` must be one of `targets`; it is batch 0 and runs alone. Its failure → `Halted`, nothing else runs and every remaining target becomes `Skipped`. |
| Batches | The remaining targets keep their order and fill batches of `batch_size` numbered from 1. Inside a batch targets are grouped by server (same-server targets stay adjacent, the server lock holds). |
| Health | After each batch, `GET /api/method/ping` on every successful target (bounded timeout, never raises); a failed probe marks the target `Failed`. Skip with `params._skip_health`. |
| Policy | `halt`: a batch with a failure stops the rollout (`Halted`). `continue`: all batches run; final status `Failed` if anything failed, else `Success`. |

High-risk playbooks need Infra Admin and the typed confirmation `"<playbook key>:<number of targets>"`
(for example `site.restore:3`), checked by `bulk.create`.

## How the driver runs

`bulk.engine.drive(name)` is the RQ worker entry on the `infra` queue. Each invocation executes
**one unit** — all backups, the canary, or one batch — then re-enqueues itself. The pure state
machine in `bulk/plan.py` (`next_action`) decides what the unit is; the shell only records target
statuses and counters, commits after every target and emits `infra:bulk.updated`
(`{bulk, status, done, total, current_batch}`, `current_batch` 0 = canary).

Child jobs are created with `enqueue=False` and run synchronously inside the driver, so on the single
staging `infra` worker targets run sequentially (docs/QUESTIONS.md Q12). Cross-server fan-out can be
added later by enqueuing a batch and waiting, without changing the planner or the contract.

## Pause, resume, cancel

| Call | Allowed from | Effect |
|---|---|---|
| `bulk.pause` | Queued, Running | Sets `pause_requested`; the driver stops at the next batch boundary → `Paused`. |
| `bulk.resume` | Paused, Halted | Skipped targets go back to Pending and the driver is re-enqueued. From `Paused` this continues the remaining batches. From `Halted` the recorded failure makes the planner halt again at the same point (Q11): resume is a true continuation only from `Paused`. |
| `bulk.cancel` | Queued, Running, Paused, Halted | Sets `cancel_requested`; the running target finishes, the rest become `Skipped`, status `Cancelled`. |

Anything else → `409 invalid_state`.

## Crash recovery

`job_engine.recovery.run` (per minute) calls `bulk.engine.requeue_running()`: every `Running` bulk
is re-enqueued. The driver is idempotent and the RQ `job_name` (`infra_bulk:<name>`) dedups a
driver that is still queued, so a duplicate is harmless.

## API

`bulk.create` / `pause` / `resume` / `cancel` return `{ "bulk": BulkOperation }`; `bulk.get` returns
`BulkOperationDetail` (summary + `targets[]` with `status`, `job`, `batch`); `bulk.list` returns
summary rows newest first with `status` / `playbook` filters and cursor paging. Shapes are in
`contracts/openapi.yaml`.

## Running it against the site

```bash
bench --site ops-staging.localhost run-tests --app infra_control \
  --module infra_control.infra_control.tests.test_a34_bulk
```

The integration test drives a rollout in-process on the dummy provider (`infra_use_dummy_provider`)
with the driver's re-enqueue neutralised: a live `infra` worker would otherwise race the test loop
and, not seeing the in-process dummy flag, hit the real adapter. After a DocType change, reload it
(`frappe.reload_doctype("Bulk Operation")`) before running the test.

## Tests

- `tests/backend/test_bulk_plan.py` — the pure planner (batches, every branch of the state machine).
- `tests/backend/test_bulk_engine.py` — lifecycle on the fake Frappe (backup-first, canary halt, policy, pause/resume/cancel).
- `tests/backend/test_api_bulk.py`, `tests/backend/contracts/test_bulk_serializers.py` — API shapes against the contract.
- `infra_control/tests/test_a34_bulk.py` — success path and a broken canary on a real site.
