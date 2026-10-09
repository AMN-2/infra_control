# ADR 0009: Bench screens with upstream update checks, and a bulk rollout preflight

Date: 2026-10-09. Status: accepted (reviewer request).

## Context

Benches had no screen: their apps appeared as a comma list on the server page, nothing said
which version was running or whether upstream had moved, and updating or pinning one app
meant typing parameters into the generic run dialog. The bulk screen asked for target names
in a textarea and gave no indication whether the targets could take the operation.

## Decision

1. **Discovery records provenance.** `discover_bench.py` reports, per app, the short commit
   of HEAD and the token-free fetch URL of `upstream`/`origin`. `Bench App` stores `commit`,
   `remote` and the result of the last upstream check (`upstream_commit`, `behind`,
   `latest_tag`, `checked_at`). Inventory sync keeps the last check when the commit is
   unchanged.
2. **Update checks are reads, on demand.** `benches.check_updates` (POST, Infra Operator,
   audited) asks GitHub for the tip of the app's branch, the number of commits the bench is
   behind (`compare`), and the newest version tag of the same major. The token of the first
   enabled Git Connection is used when present, else the anonymous API. Apps not on GitHub
   stay `unknown`. The API exposes `update_state` (`update_available | up_to_date | unknown`)
   per app. Nothing is polled: the operator presses "Check for updates" (or "Check all").
3. **Version control through the existing job.** "Update" queues `bench.update` with
   `apps=[app]`; "Switch version…" lists the upstream branches and tags (`benches.refs`) and
   queues `bench.update` with `apps=[app], branch=<ref>`. The playbook already checks out the
   ref, pulls fast-forward on branches, installs requirements, backs up and migrates every
   site, builds and restarts. No new mutation path.
4. **Bulk preflight.** `bulk.preflight` (POST, Infra Operator) runs read-only checks per
   target: exists, playbook target type, capability, status (and the bench's server status),
   lock, backup age for sites, and an optional ping. The wizard picks targets from the
   inventory with filters and "select shown", requires a fresh preflight with no blocked
   target before "Start", and offers "Drop blocked". Any non-creating playbook on Site, Bench
   or Server can be rolled out; params come from the playbook's schema.

## Consequences

- Three contract additions (`benches.check_updates`, `benches.refs`, `bulk.preflight`) and
  new `InstalledApp` fields; Prism examples updated.
- Screens: `/benches`, `/benches/:name` (apps, sites, jobs tabs), the rollout wizard.
- Tests: `tests/backend/test_bench_updates.py` (GitHub queries over mocked HTTP, check and
  state rules, discovery parsing incl. packed refs and detached HEAD, preflight), unit and
  Playwright specs `benches.spec.ts` and `bulk.spec.ts`.
- GitHub's anonymous limit is 60 requests/hour; a bench with many apps costs 2–3 requests
  per app. Connect a GitHub token (Settings → GitHub) for 5000/hour and private repositories.
