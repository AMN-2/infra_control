# Screens

How each screen in plan section 10.2 is built. Components come from `docs/design/components.md`;
every screen handles loading (skeletons), empty and error (`features/system/ErrorState.vue`,
with retry) states.

## Overview (B2.1)

Source: `frontend/src/features/overview/OverviewView.vue`, store `stores/overview.ts`.
Data: one call to `overview.summary`, kept live by `infra:job.updated` (a known running job is
patched in place; anything else refetches once per burst) and `infra:alert.fired/resolved`.

| Block          | Content                                                | Notes                                                                                                                                                  |
| -------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Headline stats | Servers, Sites, Jobs in flight, Unresolved alerts      | `IcStat` counts up on arrival and on change. Card tone is the worst status present (down > degraded > running > healthy). Each card links to its list. |
| Sparklines     | Trend of the four headline numbers                     | The contract has no trend series (Q-B8), so the store keeps the last 24 fetches of the session and the line appears from the second reading.           |
| By status      | Status badge + count per present status                | Chips link to the list filtered by `status`.                                                                                                           |
| Running jobs   | Title, target, status, real progress, step counter     | Card glows while anything runs. Rows link to the job viewer.                                                                                           |
| Recent alerts  | Message, target, rule, relative time, severity, status | Severity accent on the start edge of the alert only; new rows rise in.                                                                                 |

## Topology (B2.1)

Source: `frontend/src/features/topology/` (`layout.ts`, `TopologyGraph.vue`, `TopologyView.vue`),
store `stores/inventory.ts`. Data: `inventory.topology`, refreshed once per burst when a job
starts or ends or `infra:inventory.changed` arrives; `infra:server.heartbeat` updates the
server's status and metrics in place and triggers the pulse. Layout decision: ADR 0002.

| Element     | Behaviour                                                                                                                                                                                   |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Columns     | provider → server → bench → site, 208 × 48 px cards on the 4 px grid, 64 px between columns                                                                                                 |
| Rows        | Depth-first, subtrees contiguous, parents centred on children, siblings by label                                                                                                            |
| Node card   | Status dot (tone from `design/status.ts`), label (mono for servers and sites), kind, status, provider badge on servers and sites, latest cpu/ram/disk on servers that have sent a heartbeat |
| Running job | `has_running_job` → glow ring and pulsing dot                                                                                                                                               |
| Heartbeat   | A dot travels the server's provider edge, then each hop of its subtree; skipped under reduced motion and while the tab is hidden                                                            |
| Navigation  | Server and site nodes open their detail; bench nodes open Sites filtered by bench; provider nodes open Servers filtered by account                                                          |
| Viewport    | Scroll to zoom around the cursor (0.25×–2×), drag to pan, fit-to-view on load, resize and via the toolbar                                                                                   |

The diagram is spatial and always laid out LTR (`dir="ltr"` on the graph); the surrounding page
follows the document direction.

## Servers, Sites, Server detail, Site detail (B2.2)

Source: `features/servers/`, `features/sites/`, shared `features/jobs/TargetActions.vue`,
`features/jobs/RunPlaybookDialog.vue`, `features/jobs/schemaForm.ts`.

| Screen | Content |
|---|---|
| Servers list | `IcTable` with status, provider, region, size, live cpu/disk chips from heartbeats, sites, heartbeat age. Filters from the query (`status`, `provider_account`) so Overview and Topology can link in. Rows open the detail. |
| Sites list | Domain, status, provider, bench, DB size, last backup, SSL expiry. Filters `status`, `bench`, `server`. |
| Server detail | Header (hostname, provider, region, size, role, IP), badges (status, provider, tags, running job), Metrics card with threshold chips and a session sparkline per metric, actions, tabs: Benches, Jobs (history for this target), Details (ids, IPs, capabilities). Heartbeats update status and metrics in place. |
| Site detail | Header (domain, bench, plan), badges (status, provider, server, running job), facts (SSL days left with tone, DB size, backups with freshness tone), Domains, actions, tabs: Backups (kind, size, location, restore test), Jobs, Bench (apps, path, provider ref, capabilities). |

**Actions (capability-driven).** `TargetActions` asks `playbooks.list` for the target, drops
creation playbooks and any playbook whose `required_capability` the target lacks, hides itself
for viewers, and shows "locked by JOB-x" with disabled buttons while the target's server holds a
running job (one job per server). High-risk playbooks use the danger button.

**Run-playbook dialog.** The form is rendered from `params_schema` (`schemaForm.ts`: string,
password, boolean, number/integer, enum, list of strings), validated before submit (required,
pattern, minLength, hostname, ranges) and again by the backend. High risk adds the typed
confirmation (`confirm` = target name, enforced server-side too). Success: toast and navigation
to the job viewer; failure: the API error (code and message) stays in the dialog.

## Jobs and Job viewer (B2.3)

Source: `features/jobs/JobsView.vue`, `features/jobs/JobDetailView.vue`, store `stores/jobs.ts`.

| Element | Behaviour |
|---|---|
| Jobs list | Running and queued first, then failed, success, cancelled; status filter from the query; real progress per row; "Load older jobs" follows `next_cursor`. |
| Header | Playbook title, job id, target (links to the server, site or filtered list), trigger, created time, status badge, `retry of` / `retried as` / `bulk` / `created` badges, live duration. |
| Steps | `IcTimeline`: the running step is expanded and coloured as it executes, finished steps collapse and show their duration; `infra:job.step` adds or updates rows. |
| Log | `IcTerminal` (xterm, lazy) seeded with each step's stored output under a `── title` rule, then streamed from `infra:job.log` through the store's `onLog`, buffered at 50 ms. |
| Controls | Operators only. Cancel (typed confirmation of the job id, `cancel_requested` badge until the worker observes it); Retry on failed jobs (new job linked by `retry_of`, badge links to it). Viewers see no controls. |
| Error | The masked failure reason as an alert under the progress bar. |
| Parameters | Masked `params` as a definition list (`********` for write-only fields). |

## Alerts and rule editor (B3.2)

Source: `features/alerts/AlertsView.vue`, `features/alerts/RuleDialog.vue`, `features/alerts/ruleForm.ts`,
stores `stores/alerts.ts` and `stores/alertRules.ts`.

| Element | Behaviour |
|---|---|
| Tabs | `Alerts` (count = firing) and `Rules` (count = rules). |
| Alerts list | Firing first then newest (API order); severity accent on the start edge; severity and status badges; message; target links to the server or site; rule title; fired / acknowledged by / resolved relative times. Resolved rows are dimmed. Status and severity filters refetch with the query; "Load more" follows `next_cursor`. |
| Acknowledge | Operators only, firing alerts only. Optimistic (plan §10.4): the badge flips at once, the row is rolled back and a toast shows the error on failure. The store keeps the optimistic row if the response names another alert. |
| Realtime | `infra:alert.fired` refetches the list (the event carries ids only); `infra:alert.resolved` patches the row in place. |
| Rules list | Title, severity, kind, `built-in` badge, id, target doctype, a one-line condition (`CPU above 90% for 5 min`, `No heartbeat for 3 min`, …) and channels. Enable switch is optimistic with rollback; edit and delete are Infra Admin only; built-in rules have no delete. |
| Rule editor | Create = `metric` rule on `Server` (title, metric, condition, threshold, for-minutes, severity, channels, enabled). Edit shows only the fields the kind allows (contract `AlertRule`): every kind edits title, severity, channels, enabled; `metric` its four fields; `heartbeat` minutes; `ssl_expiry` days. The update body carries only changed, allowed fields so a built-in rule never triggers `400 validation_error`. Client validation mirrors the contract ranges (0–1440 minutes, ≥1 for heartbeat, ≥1 day for ssl). |
| Delete | Typed confirmation of the rule id; historical alerts are kept (API contract). |
| States | Skeletons while loading, empty states per tab, `ErrorState` with retry. |
