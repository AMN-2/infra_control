# Operating the SaaS from the UI (ADR 0004–0006)

The day-to-day flows an operator runs from `/infra`, and what each one does on the servers.
Every action is an `Infra Job` with live steps and a masked log; nothing here needs SSH.

## 1. Connect GitHub (once, Infra Admin)

Settings → **GitHub** (link at the bottom of the sidebar) → paste a personal access token
with repository read access → **Verify and connect**. The token is checked against GitHub,
stored encrypted on a `Git Connection`, and never shown again; the screen shows the login,
account type and scopes. Remove with typed confirmation. A fine-grained token scoped to the
organisation's repositories is enough; `repo` on a classic token also works.

## 2. Create a server from a plan (Infra Operator)

Servers → **New server**: provider account → region → plan (live catalogue: vCPU, RAM, disk,
transfer, monthly price, grouped basic / general / cpu / memory) → hostname, role, tags →
**Create server**. The job creates the droplet, waits for cloud-init, applies the roles for
the server's role (`all` = base, mariadb, redis, nginx, bench with Node 20), initialises a
bench, and ends with a verification play (services running, Node >= 20, bench answers,
frappe present). The Server document appears when the job succeeds; the servers list links
to it from the job.

## 3. Put an app on a bench (Infra Operator)

Servers → the server → **Benches** → row action **Add app to bench**. With a GitHub
connection chosen, search the repository and pick a branch or tag from the list (the default
branch is preselected); without one, paste a public https URL. Private repositories clone
through the connection's token, which is passed under `no_log`, masked in the job output, and
removed from the bench's git remote right after the clone. An app already present is a
no-op; the `Bench App` row is recorded on success.

## 4. Install the app on a site

Sites → the site → **Install app on site**. A database backup is taken and uploaded to Spaces
first (the job fails if that fails), then `bench install-app` runs under maintenance mode.
"Already installed" is a no-op.

## 5. Roll out an update

Servers → the server → **Benches** → **Update bench apps**: choose the apps (empty = all),
optionally a branch or tag to switch to, keep `migrate` and `build` on. Per app: `git fetch`,
`git pull --ff-only` (a diverged checkout fails the job; a tag checkout is left as is), then
requirements, maintenance on for every site, `bench --site all backup` (fails the job if a
backup fails), `bench --site all migrate`, maintenance off, `bench build`, `bench restart`.
Nothing new upstream = "nothing to update" and no site is touched.

Fleet-wide: Bulk rollouts → playbook `bench.update` → the benches → canary → batch size.
The canary runs first and a failure halts the rollout before any other bench is touched.

## 6. Read logs without SSH

Servers → the server → **Logs**: pick a source (nginx access/error, bench web/worker/
scheduler/errors, `frappe.log`, `database.log` query log, one site's log, MariaDB, Redis,
supervisor, system journal), the bench, a line count (max 2000) and an optional
case-insensitive filter, then **Read**. Each read is a `server.logs` job (low risk, Infra
Operator): tail/journalctl on the server, output masked and shown in the terminal, listed
under recent reads and in the job history. Nothing on the server changes.

Job steps now carry what each task did (command stdout, report messages, loop items), not
only `ok: [host]`, capped at 16 KB per task; `no_log` tasks stay censored.

## What to check when a job fails

- The failing step's output is in the job viewer; secrets are masked.
- `bench get-app` build errors usually mean the app needs a newer Node than the bench has:
  the bench role now installs Node 20, older servers need `server.apt_security` plus a
  re-run of the provision roles (or a fresh server).
- A `--ff-only` refusal means someone changed code on the server by hand: inspect
  `apps/<app>` on the bench, then re-run.
