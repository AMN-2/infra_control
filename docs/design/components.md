# Design system components (B1.1)

Live reference: `/infra/_design#components`. Source: `frontend/src/design/components/`, exported
from its `index.ts`. Feature code composes these and never restyles them; the design guard test
(`tests/frontend/unit/design-guard.spec.ts`) checks the components like any feature file, so they
only ever use tokens.

| Component | Purpose | Notes |
|---|---|---|
| `IcButton`, `IcIconButton` | Actions | `primary` is the one accent; `loading` blocks clicks but keeps the label (no spinner, §10.3.7) |
| `IcBadge`, `IcStatusBadge`, `IcStatusDot` | Status | Tone comes from `status.ts` (`toneFor(entity, status)`); only `Running`/`Provisioning` pulse |
| `IcProviderBadge` | Provider on every server/site/bench | `DO` / `FC`, long form on detail pages |
| `IcMetricChip` | One metric with threshold tone | warn 80, crit 90 by default |
| `IcCard` | Panel (level 1) or card inside a panel (level 2) | `live` glows while a job runs on it |
| `IcStat`, `IcSparkline` | Overview numbers | Count up on arrival and on change; sparkline draws in (transform wipe) |
| `IcTable` | Lists | Generic rows, `cell-<key>` slots, skeleton rows while loading, empty state, clickable rows |
| `IcTabs` | Tabbed detail pages | Roving tabindex, arrow keys |
| `IcProgress` | Job and bulk progress | Width animates with `scaleX` (transform only, §10.3.4) |
| `IcSkeleton` | Loading | Breathes via opacity; pauses when the tab is hidden |
| `IcTimeline` | Job steps | The running step is expanded; finished steps collapse |
| `IcTerminal` | Live logs | xterm.js lazy-loaded; `write()` buffers and flushes at most every 50 ms (`logBuffer.ts`) |
| `IcDialog`, `IcConfirmDialog` | Overlays | Scale transition, focus trap, Escape; typed confirmation for high-risk actions |
| `IcToastHost` + `pushToast()` | Feedback | Mounted once in `App.vue`; max 5, severity edge, auto-dismiss |
| `IcMenu`, `IcTooltip`, `IcKbd` | Actions menus, hints, shortcuts | Keyboard navigable |
| `IcInput`, `IcSelect`, `IcSwitch`, `IcField` | Forms | `IcField` carries label, hint, error |
| `IcEmptyState`, `IcPageHeader`, `IcBreadcrumbs` | Page structure | |

Status enums are typed from the generated contract (`src/api/schema.d.ts`), so a contract change
that adds a status fails `vue-tsc` until `status.ts` maps it. Alert `info` maps to the blue tone
without motion (Q-B5 follow-up).
