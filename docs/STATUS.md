# Agent A status

Resume file for the next Agent A session. Update before every session ends.
Last update: 2026-10-07 (session 2, after the PR #4 contracts review).

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

## In progress

A1.1 (DocTypes, roles, permissions, immutable audit log) on `agent-a/A1.1-doctypes`, stacked on
A0.5. Previously: the PR #4 contracts review (6 blocking + 5 non-blocking items) is fully addressed in
`25ddf00` on `agent-a/A0.2-contracts`; the mock follows in `2028632` on `agent-a/A0.4-mock-server`.
ADR 0001 (`docs/adr/`) records the creation-playbook target decision. The stack was rebased and
force-pushed. Phase 0 exit gate is waiting on the human: approve `contracts/` and merge #3–#7.

**Blocker for the reviewer:** GitHub Actions has never run on this repository (zero workflow
runs, on Agent B's PRs #1–#2 as well; only the Sourcery app reports). Enable Actions under
Settings → Actions → General (the PAT used by `gh` cannot change it). Until then "both CI
pipelines green" can only be shown locally; all A0.x checks pass locally as listed above.

**Exact next step for the next session:** once Actions is on, check `gh pr checks <n>
--repo AMN-2/infra_control` for #3–#7 and fix anything red (the `bench-tests` job is the only
place the `/infra` integration test runs). Then wait for contract approval. Do not start
Phase 1 (A1.x) until the reviewer approves the contracts.

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
