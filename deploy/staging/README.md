# Staging control plane on the shared dev bench

How the staging Infra Control (`ops-staging.localhost`) runs on the shared bench, and how to open
it. Production follows plan section 13.1 instead: its own droplet, nginx with TLS, 2FA and an IP
allowlist or VPN.

## Why it is shaped like this

- The bench's main gunicorn (port 8000) serves other, production sites. Restarting it for staging
  would also load whatever uncommitted code sits in those apps, so staging gets its own gunicorn.
- There is no root access on this host, so no nginx vhost and no TLS. A small Node edge proxy plays
  nginx's part: it routes `/socket.io` to Frappe's realtime server and everything else to the
  staging gunicorn, and sets `X-Frappe-Site-Name` so the right site is chosen.
- Everything listens on `127.0.0.1` only. `bench serve` was tried and rejected: it always binds
  `0.0.0.0` and enables the interactive Werkzeug debugger; on 2026-10-07 it was reachable from the
  internet for about eight hours (scanners requested `/`; no debugger access in the log).

```
browser ──(SSH / VS Code port forward)──> 127.0.0.1:8010 edge.mjs
                                             ├─ /socket.io ──> 127.0.0.1:9000 Frappe Socket.IO
                                             └─ /*        ──> 127.0.0.1:8011 gunicorn (wsgi.py)
bench worker --queue infra  ── runs Infra Jobs (Ansible, DigitalOcean API)
```

## Run

```bash
cd ~/frappe-bench/apps/infra_control/deploy/staging
./staging.sh start      # web, edge, worker
./staging.sh status     # PIDs, plus a ping and a Socket.IO handshake through the edge
./staging.sh restart    # after pulling new backend code
./staging.sh stop
```

PID files live in `~/.infra-staging/`, logs in `~/frappe-bench/logs/infra-staging-*.log`.
Processes are started with `setsid nohup`, so they survive the terminal or agent session that
started them. They do not come back after a host reboot; run `./staging.sh start` again.

## Open it

1. In VS Code (Remote SSH), open the Ports panel and forward port **8010**. From a terminal the
   same is `ssh -L 8010:127.0.0.1:8010 frappe@<host>`.
2. Browse to `http://localhost:8010/infra` and log in with a user that has an Infra role.

## Rules on this host

- The bench checkout `apps/infra_control` stays on the local branch `integration/phase2`; the
  worker and Ansible read files from it while jobs run. Work on other branches in a worktree.
- Never stop the worker while an `Infra Job` is Running (`./staging.sh status` first).
