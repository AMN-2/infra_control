# Inventory drift detection (A3.3)

Drift is the difference between what a provider has and what the control plane's documents
say. The hourly `inventory.sync` job (A2.5) reconciles provider-owned facts and reports what it
will not fix; A3.3 turns that report into the account's `drift` alert. Nothing here mutates
infrastructure and nothing is deleted or archived automatically (plan 9.4, ADR 0003).

## Flow

```
hooks.scheduler_events hourly
  └─ inventory.schedule.sync_all_providers      one Infra Job per enabled Provider Account
       └─ job engine → provider adapter.sync_inventory()
            └─ inventory.apply.reconcile(account, provider, inventory)
                 ├─ inventory.plan.plan_sync()        pure: creates / updates / findings
                 ├─ inventory.apply.apply_plan()      writes documents, emits infra:inventory.changed
                 └─ monitoring.alerts.sync_drift_alerts(account, findings)
                      ├─ findings and no open alert  → fire once (infra:alert.fired, notify)
                      ├─ findings and open alert     → refresh value/message, no notification
                      └─ no findings and open alert  → resolve once (infra:alert.resolved, notify)
```

## Finding kinds (`inventory/plan.py`)

| kind | doctype | meaning | what a human does |
|---|---|---|---|
| `server_missing` | Server | the document's `provider_ref` is not at the provider any more | archive the server (and its benches/sites) or re-provision |
| `server_archived_but_present` | Server | a human archived the document but the droplet still exists | un-archive, or deprovision at the provider |
| `server_unreachable` | Server | the droplet exists but SSH discovery failed | fix access (`controller_ip` allowlist, key); the server's benches/sites are **not** reported missing |
| `bench_missing` | Bench | discovery scanned the server and found no bench at that path | archive the bench or restore it |
| `site_missing` | Site | discovery scanned the bench and found no site directory | archive the site or restore from backup |

What the sync fixes on its own (and therefore never reports): new servers, benches and sites
at the provider (created), and changes to provider-owned fields (`hostname`, `status`,
`public_ip`, `private_ip`, `region`, `size`, `role`, `frappe_version`, `apps`, site
`status`/`bench`). Human-set site states (`Suspended`, `Archived`) are kept.

## The alert

- Built-in rule `Inventory drift` (`kind: drift`, target `Provider Account`, default severity
  `warning`, created on install). Severity, channels and `enabled` are editable from the
  alerts screen or `alert_rules.update`; the rule cannot be deleted.
- One alert per account: `value` = number of findings, `message` = the first five as
  `<kind>: <doctype> <name>` plus `(+N more)`. The complete list is in the sync job's output
  (`findings`) and the job's `drift_alerts` counters (`fired`, `resolved`).
- Acknowledge from the alerts screen silences re-notification; the alert resolves itself on
  the first clean sync.

## Operating it

```bash
# run a sync now for one account (from the UI: Provider Account → inventory.sync), or:
bench --site <site> execute infra_control.inventory.schedule.sync_all_providers
# read the open drift alerts
bench --site <site> execute frappe.get_all --kwargs '{"doctype":"Alert","filters":{"kind":"drift","status":["!=","resolved"]},"fields":["name","target_name","value","message"]}'
```

A drift alert that never resolves means a document a human must act on; the sync will keep
refreshing the same alert every hour until it is clean.

## Tests

- `tests/backend/test_inventory_plan.py` — findings per kind; gone resources are findings, not
  deletions; unscanned servers never produce missing benches/sites.
- `tests/backend/test_alert_engine.py::test_drift_alert_opens_on_findings_and_resolves_when_clean`.
- `infra_control/tests/test_a32_alerts.py::test_drift_alert_lifecycle` — against a real site.
- `infra_control/tests/test_a25_inventory.py` — reconcile end to end (drift counters in
  the result).
