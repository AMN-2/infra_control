# Agent A status

Resume file for the next Agent A session. Update before every session ends.
Last update: 2026-10-07 (session 2; single agent owns backend and frontend since this session).

## Phase 0 tasks

| Task | State | Branch | PR | Verified by |
|---|---|---|---|---|
| A0.1 Scaffold, CI, path guard | done | `agent-a/A0.1-scaffold-ci` | [#3](https://github.com/AMN-2/infra_control/pull/3) → main | ruff, mypy --strict, 16 unit tests |
| A0.2 Contracts | review fixes pushed (commit `25ddf00`), awaiting approval | `agent-a/A0.2-contracts` | [#4](https://github.com/AMN-2/infra_control/pull/4) → A0.1 | 35 contract tests |
| A0.4 Mock + realtime replay | done, updated for the review (`2028632`) | `agent-a/A0.4-mock-server` | [#5](https://github.com/AMN-2/infra_control/pull/5) → A0.2 | `npm run smoke` (26 ops, 5 scenarios) |
| A0.3 Press API verification | done (source-based) | `agent-a/A0.3-press-api-verification` | [#6](https://github.com/AMN-2/infra_control/pull/6) → A0.4 | docs/providers/frappe_cloud.md; Q7, Q8 |
| A0.5 Serve SPA at `/infra` (Q-B2) + Q1–Q6 decisions | done | `agent-a/A0.5-serve-spa` | [#7](https://github.com/AMN-2/infra_control/pull/7) → A0.3 | 10 unit tests; integration test runs in bench CI |

Branches are stacked in that order on `main` (root commit `24ea201`). Merge PRs top-down;
after each merge GitHub retargets the next PR to `main`.

## Phase 0 exit gate

Contracts approved by the reviewer on 2026-10-07 (in chat, after `25ddf00`), with the instruction to
start Phase 1. Merging #3-#7 on GitHub and enabling Actions remain the reviewer's.

## Phase 1 (complete on both sides, gate pending)

Backend: A1.1 (#8), A1.3 (#9), A1.2 (#10), A1.4 (#11), A1.5 (#12). Frontend (same agent since
2026-10-07): B0 foundation rebased (#13, supersedes #1/#2), B1.1 components (#14), B1.3 realtime
+ stores (#15), B1.2 app shell (#16). Merge order: #3..#7, #8..#12, #13..#16, top-down.

Verified locally: backend ruff/mypy strict/145 pytest; frontend format/lint/vue-tsc/54 vitest/
build (132 KB gz initial)/13 Playwright; the built SPA connects to the mock realtime server and
validates every replayed event (see docs/runbooks/frontend_build.md, "Mock session").

**Exit gate, still needs the reviewer:** (1) the dummy playbook run on a staging server with
steps arriving over Socket.IO: needs a control-plane site with the `infra` worker
(docs/QUESTIONS.md Q9); (2) approval of the design system from `/infra/_design` (sections
Surfaces..Motion from B0.2, Components from B1.1).

## In progress

Nothing. Do not start Phase 2 (A2.x providers, B2.x screens) before the Phase 1 exit gate.

## Open questions (docs/QUESTIONS.md)

- Q1–Q6: decided (recorded in the Decision column on the A0.5 branch).
- Q7: FC `suspend_site` → deactivate/activate mapping. Proposed default in use. Needs a decision
  before A2.4.
- Q8: live Press sample captures blocked on a staging Frappe Cloud team (plan open question 5).
- Q-B2 (Agent B's): answered by A0.5; Agent B should mark it decided once #7 merges.

## Environment notes

- Push over HTTPS (`git push https://github.com/AMN-2/infra_control.git <branch>`); SSH keys
  are not set up for GitHub here. `gh` is authenticated as AMN-2.
- Tooling: `ruff` from `~/.local/bin`; `mypy` and `pytest` from `~/frappe-bench/env/bin`.
- `infra_control` is in `sites/apps.txt` but installed on no local site, so the Frappe
  integration test (`infra_control/infra_control/tests/`) only runs in the GitHub `bench-tests`
  job. Creating a site is a bench-wide action; ask the reviewer first.
- Agent B works in `/home/frappe/worktrees/infra_control-agent-b` (PRs #1, #2). Both sides
  edited `docs/QUESTIONS.md`; expect a trivial conflict when the second side rebases.

## Phase 1 preview (blocked on exit gate)

A1.1 DocTypes + roles, A1.2 job engine (Redis lock, one job per server), A1.3 dummy
playbook over Socket.IO. Q2's layout decision applies: DocTypes under
`infra_control/infra_control/doctype/`, `core/` for enums, permissions, audit, errors.
