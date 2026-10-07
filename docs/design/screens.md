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
