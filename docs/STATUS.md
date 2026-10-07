# Agent A status

Resume file for the next Agent A session. Update before every session ends.
Last update: 2026-10-07 (session 3; single agent owns backend and frontend since session 2).

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

## Phase 1 (complete on both sides; gate half-passed)

Backend: A1.1 (#8), A1.3 (#9), A1.2 (#10), A1.4 (#11), A1.5 (#12), gate follow-up
[#17](https://github.com/AMN-2/infra_control/pull/17) (engine datetime fix, site-explicit
integration tests, gate record). Frontend (same agent since 2026-10-07): B0 foundation rebased
(#13, supersedes #1/#2), B1.1 components (#14), B1.3 realtime + stores (#15), B1.2 app shell
(#16). Merge order: #3..#7, #8..#12, #17, #13..#16, top-down.

Verified locally (session 3): backend ruff / mypy --strict / 146 pytest; Frappe integration
suite on a real site (`bench --site ops-staging.localhost run-tests --app infra_control`:
16 tests, OK); frontend format / lint / vue-tsc / vitest / build (132 KB gz initial, budget
250) / 13 Playwright. Session 3 found and fixed lint and type errors in the frontend test
files that the earlier "green" had missed (commit `5213f05` on `agent-b/B1.2-app-shell`).

**Exit gate:**

1. **Passed (2026-10-07).** The dummy playbook `server.snapshot` ran on staging server
   `SRV-0001` through `jobs.run`, a worker on the `infra` queue, and its steps arrived live over
   Frappe's Socket.IO on namespace `/ops-staging.localhost`: 8 `infra:*` events, all valid
   against `contracts/events`, job `Success`, reproduced twice. Record, capture and findings:
   `docs/runbooks/job_engine.md`, "Phase 1 exit gate run". It surfaced a real engine bug
   (tz-aware step timestamps rejected by MariaDB), fixed in #17.
2. **Still needs the reviewer:** approval of the design system from `/infra/_design` (sections
   Surfaces..Motion from B0.2, Components from B1.1).

## In progress: Phase 2

Started 2026-10-07 on the reviewer's instruction. After the Phase 1 report (gate half 1 passed,
design approval pending) the reviewer answered "continue the work" twice; this is recorded as
the gate decision in docs/QUESTIONS.md Q10, and the reviewer can still object to the design
system from `/infra/_design`.

| Task | State | Branch | PR |
|---|---|---|---|
| B2.1 Overview + Topology | done, full local CI green | `agent-b/B2.1-overview-topology` (on B1.2) | #18 |
| B2.2 Servers/Sites lists, Server detail, Site detail, capability actions, run-playbook dialog | done, full local CI green | `agent-b/B2.2-detail-screens` (on B2.1) | #19 |
| B2.3 Job viewer with live terminal | next | | |
| A2.1 DigitalOcean client + adapter | | | |
| A2.2 Ansible roles, server.provision, service.control | | | |
| A2.3 Site playbooks on DO | | | |
| A2.4 Frappe Cloud client + adapter | blocked on Q7/Q8 (staging team) | | |
| A2.5 inventory.sync | | | |

Preview for the reviewer: `http://<host>:5180/infra/` (Vite + Prism mock + realtime replay,
session 3; dies with the session). Phase 2 exit gate needs a real DigitalOcean staging token
(`Provider Account` with `is_staging = 1`).

## Open questions (docs/QUESTIONS.md)

- Q1–Q6: decided (recorded in the Decision column on the A0.5 branch).
- Q7: FC `suspend_site` → deactivate/activate mapping. Proposed default in use. Needs a decision
  before A2.4.
- Q9: closed on #17; the gate ran on the existing staging site `ops-staging.localhost`.
- Q8: live Press sample captures blocked on a staging Frappe Cloud team (plan open question 5).
- Q-B2 (Agent B's): answered by A0.5; Agent B should mark it decided once #7 merges.

## Environment notes

- Push over HTTPS (`git push https://github.com/AMN-2/infra_control.git <branch>`); SSH keys
  are not set up for GitHub here. `gh` is authenticated as AMN-2.
- Tooling: `ruff` from `~/.local/bin`; `mypy` and `pytest` from `~/frappe-bench/env/bin`.
- `infra_control` is installed on the staging site `ops-staging.localhost` (session 3) with
  `infra_use_dummy_provider: 1`; the Frappe integration tests run there. `workers.infra` is
  declared in `sites/common_site_config.json` (backup `*.bak-infra-gate-20261007`); gunicorn
  caches the queue list per worker, so `bench restart` is needed before `jobs.run` works from
  every web worker. Seed records: user `infra.gate@ops-staging.localhost` (Infra roles, API
  key), `Provider Account` `DO-STAGING` (staging, placeholder token), `Server` `SRV-0001`.
  A dedicated `bench worker --queue infra` must be running for jobs to execute. Creating a
  new site remains a bench-wide action; ask the reviewer first.
- Agent B works in `/home/frappe/worktrees/infra_control-agent-b` (PRs #1, #2). Both sides
  edited `docs/QUESTIONS.md`; expect a trivial conflict when the second side rebases.

## Phase 1 preview (blocked on exit gate)

A1.1 DocTypes + roles, A1.2 job engine (Redis lock, one job per server), A1.3 dummy
playbook over Socket.IO. Q2's layout decision applies: DocTypes under
`infra_control/infra_control/doctype/`, `core/` for enums, permissions, audit, errors.
