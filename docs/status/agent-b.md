# Status — Experience (frontend)

Since 2026-10-07 the same agent owns backend and frontend; the authoritative resume file is
`docs/STATUS.md`. This file is kept for the frontend branch map.

Last updated: 2026-10-07

| Task | Branch | PR | State |
|---|---|---|---|
| B0.1 + B0.2 foundation (rebased on the backend stack, client regenerated) | `agent-b/B0-foundation` | [#13](https://github.com/AMN-2/infra_control/pull/13) | supersedes #1 and #2 |
| B1.1 design system (29 components, showcase section) | `agent-b/B1.1-components` | [#14](https://github.com/AMN-2/infra_control/pull/14) | local CI green |
| B1.3 typed realtime layer + Pinia stores | `agent-b/B1.3-realtime-stores` | [#15](https://github.com/AMN-2/infra_control/pull/15) | local CI green |
| B1.2 app shell, routing, auth guard, command palette (+ `5213f05`: test files lint/type clean) | `agent-b/B1.2-app-shell` | [#16](https://github.com/AMN-2/infra_control/pull/16) | full local CI green, incl. Playwright |
| B2.1 Overview + Topology screens (ADR 0002, Q-B8/Q-B9, docs/design/screens.md) | `agent-b/B2.1-overview-topology` | [#18](https://github.com/AMN-2/infra_control/pull/18) | full local CI green: 68 vitest, 15 Playwright, 132 KB gz initial |

Full local CI: `cd frontend && npm run check:api && npm run format:check && npm run lint &&
npm run typecheck && npm test && npm run build && npm run check:size && CI=true npm run test:e2e`.
