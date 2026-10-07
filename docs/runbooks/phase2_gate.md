# Phase 2 exit gate on DigitalOcean (2026-10-07)

Plan section 12, Phase 2 exit gate:

1. "A new DO server reaches a working site in one action, twice in a row with identical results."
2. "The same `site.backup` call succeeds on one DO site and one Frappe Cloud site."
3. "Frontend runs against the real API with mocks off."

This file records part 1 and the DigitalOcean half of part 2. The Frappe Cloud half waits for a
staging Frappe Cloud team (plan open question 5, docs/QUESTIONS.md Q7/Q8).

## Setup

| Item | Value |
|---|---|
| Control plane | `ops-staging.localhost` on the shared dev bench (not a dedicated droplet; plan 13.1 is for production) |
| Provider Account | `DO-STAGING-LIVE`, `is_staging = 1`, a DigitalOcean team created for staging, custom-scoped token |
| Controller key | `~/.ssh/infra_control_ed25519` (site config `infra_ssh_private_key`), added to the team as "infra-control staging" |
| Controller IP | `142.93.168.28` (`Infra Settings.controller_ip`), the only address allowed on port 22 by the managed firewall |
| Spaces | bucket `infara`, region `fra1` |
| Code | local branch `integration/phase2` = frontend tip + `agent-a/A2.6-phase2-gate` |
| Worker | `bench worker --queue infra`, ansible-core 2.19.14 and ansible-runner 2.4.3 in the bench env |
| Driver | every step goes through `POST /api/method/infra_control.api.jobs.run` as an `Infra Admin` API user, then `jobs.get` until terminal |

Each run is three jobs, as the API exposes them: `server.provision` (droplet → firewall →
Ansible roles → bench init → supervisor and nginx), `site.create` on the recorded Bench, and
`site.backup` to Spaces. Between them the site is checked from the controller, outside the
droplet: `GET http://<droplet ip>/api/method/ping` with the site's Host header.

The plan says "one action". The contract has no single job that both provisions and creates a
site, so a run is three jobs triggered back to back with no manual step; the documents each job
needs (Server, Bench) are recorded by the previous one.

## Runs

| Run | Server | Provision | site.create | HTTP from outside | site.backup | Spaces files |
|---|---|---|---|---|---|---|
| 1 | gate-01.fra1 → SRV-0002 | JOB-00006 Success, 691 s, 55 steps | JOB-00010 Success (after the fixes below were applied to the server) | `{"message":"pong"}`, /login 200 | JOB-00011 Success | database, private files (public missed: bug 7) |
| 2 | gate-02.fra1 → SRV-0003 | JOB-00012 Success, 721 s, 56 steps | JOB-00013 Success, first attempt | `{"message":"pong"}`, /login 200 | JOB-00014 Success | database, files, private files |
| 3 | gate-03.fra1 | RUN3_PROVISION | RUN3_SITE | RUN3_HTTP | RUN3_BACKUP | RUN3_FILES |

Run 2 is the first run with the final code from start to finish, with no manual step. RUN3_COMPARE

## What the live runs found

Every one of these passed the unit tests and Molecule; only real DigitalOcean servers showed them.
Each is fixed on `agent-a/A2.6-phase2-gate` with a test where a test can see it.

| # | Seen in | Symptom | Cause and fix |
|---|---|---|---|
| 1 | read-only check | SSH key "infra-control staging" not found | Exact-name lookup. The key is now matched by its key material; the name is a fallback. |
| 2 | design review | A provisioned server had no bench, and no Bench document to create a site on | Provision now runs `bench init` and wires production; success records the Bench. |
| 3 | JOB-00004 | `ansible-playbook` printed its usage, rc 2 | `binary=` puts ansible-runner in RAW mode, which drops the playbook argument. PATH carries the venv instead; a test runs ansible-runner's real command builder. |
| 4 | JOB-00005 | `bench setup production` failed | It pip-installs Ansible into bench's venv, then cannot find it for its fail2ban role. Supervisor and nginx are wired explicitly; a re-run on the real droplet reported `changed=0`. |
| 5 | JOB-00007 | MariaDB error 1130, "Host 127.0.0.1 is not allowed" | `skip-name-resolve` breaks Frappe's TCP connections to users @'localhost'. Removed. |
| 6 | JOB-00007 | A failed `new-site` left `site_config.json`, so a retry would skip creation and report success | `site_create` rescues by dropping the partial site, then fails clearly. |
| 7 | JOB-00008 | `nginx -t`: No such file | The play PATH had no sbin directories. Added, with a test. |
| 8 | JOB-00009 | `unknown log format "main"` | The bench's nginx config uses a format `bench setup production` would define. The nginx role defines it in `00-infra-control.conf`, loaded before `frappe-bench.conf`. |
| 9 | JOB-00011 | The public files archive was never uploaded | The match needed a digit before `-files.tar`; bench names it after the site. Fixed and checked against real names. |
| 10 | between runs 2 and 3 | The infra worker received a warm shutdown from the agent session | Operational: run the worker detached (`setsid nohup bench worker --queue infra`) or under supervisor. |

## Clean-up

The droplet from JOB-00004 and the first one from JOB-00005 were deleted through the DigitalOcean
API after their failed runs, because there is no deprovision playbook yet; a retry of
`server.provision` creates a new droplet rather than reusing one. RUN3_CLEANUP

## Still open for the gate

- The Frappe Cloud half of part 2 (A2.4; needs a staging Frappe Cloud team).
- Part 3, the frontend against the real API with mocks off, is checked separately (`/infra` on the
  staging site).
- `server.deprovision` does not exist; deleting test droplets is manual.
