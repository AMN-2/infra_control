# ADR 0003: one drift alert per Provider Account, carrying every finding

Date: 2026-10-08. Status: accepted (A3.3; same agent on both sides since 2026-10-07).

## Context

Plan section 9.4 says drift detection "raises a `warning` alert per difference" and never
auto-fixes. `inventory.sync` (A2.5) already produces one `Finding` per difference it will not
fix (`server_missing`, `bench_missing`, `site_missing`, `server_unreachable`,
`server_archived_but_present`). An hourly sync over a few accounts with a handful of stale
documents would open, notify and later resolve dozens of near-identical alerts, each tied to a
document that may no longer exist as a valid `TargetRef`.

## Decision

- Drift is detected by `inventory.plan.plan_sync` (pure) and surfaced by
  `monitoring.alerts.sync_drift_alerts(account, findings)` right after `apply_plan`.
- There is **one** `Alert` per `Provider Account` for the built-in `drift` rule (`kind: drift`,
  `target_doctype: Provider Account`). Its `value` is the number of findings and its `message`
  lists the first five as `<kind>: <doctype> <name>`; later syncs refresh the open alert in
  place (no new notification) and the alert resolves, with one notification, on the first
  clean sync.
- Severity and channels come from the built-in rule (`warning`, editable through
  `alert_rules.update` like every other rule; it cannot be deleted).
- Nothing is ever deleted, archived or re-created in response to a finding. The sync only
  creates documents for resources the provider has and updates provider-owned fields.

## Consequences

- The alerts screen shows a single drift row per account instead of one per stale document;
  the full list of differences is in the message and in the sync job's output.
- Section 9.4 of the plan is read as "an alert per account, carrying one entry per
  difference". If a per-document alert is ever wanted, `sync_drift_alerts` is the one place
  to change.
- `Finding.kind` is a closed set documented in `docs/runbooks/drift.md`; adding a kind is a
  change to `inventory/plan.py` and its unit tests only.
