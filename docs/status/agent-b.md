# Status — Agent B (Experience)

This file is how the next Agent B session resumes. Agent A keeps its own in
`docs/status/agent-a.md`. Update it before ending every session.

Last updated: 2026-10-07

## Tasks done

| Task | Branch | PR | State |
|---|---|---|---|
| B0.1 scaffold Vite app, CI, generated API client | `agent-b/B0.1-scaffold-frontend` | [#1](https://github.com/AMN-2/infra_control/pull/1) → `main` | Open, local CI green |
| B0.2 design tokens, motion, `/infra/_design` showcase | `agent-b/B0.2-design-tokens` | [#2](https://github.com/AMN-2/infra_control/pull/2) → B0.1 (stacked) | Open, local CI green, initial JS 55.9 KB gz |

Reviewer decisions recorded in `docs/questions/agent-b.md`: Q-B2, Q-B4, Q-B5, Q-B6 approved.
Q-B7 pending.

## In progress

**Waiting on Agent A's contracts merge** (`agent-a/A0.2-contracts`, stacked under A0.4/A0.3,
none merged yet). Exact next step once `contracts/openapi.yaml` and `contracts/events/` are
on `main`:

1. Rebase B0.1/B0.2 onto `main`; `cd frontend && npm run gen:api` and commit `src/api/schema.d.ts`.
2. Add the `info` alert severity tone to `src/design/status.ts` and `docs/design/tokens.md`
   (contract `Severity` enum is `info, warning, critical`) with a WCAG AA contrast test in
   `tests/frontend/unit/design-*.spec.ts`.
3. Point the dev server at the Prism mock on `:4010` (`contracts/mock`, `npm run mock`) via a
   Vite proxy for `/api/`.
4. Type `src/realtime/` from `contracts/events/*.schema.json` (events `infra:*`, namespace
   `/<site>`); the Socket.IO replay on `:9000` (`npm run realtime`) is the dev source.

**B1.1 is blocked** until the reviewer confirms the Phase 0 exit gate.

## Open questions

See `docs/questions/agent-b.md`. Only Q-B7 is undecided.

## Environment notes

- Worktree: `/home/frappe/worktrees/infra_control-agent-b`. SSH to GitHub is not available
  from this machine; git uses HTTPS through `gh auth setup-git` with a per-worktree
  `url.https://github.com/.insteadOf git@github.com:` rewrite (`git config --worktree`).
- Full local CI: `cd frontend && npm run check:api && npm run format:check && npm run lint &&
  npm run typecheck && npm test && npm run build && npm run check:size && CI=true npm run test:e2e`.
