# Runbook: the controller is down (A4.3)

The controller is the Frappe site that runs `infra_control`: web, Socket.IO, the `infra`
worker, the scheduler and (staging) the edge and console bridge. Managed servers keep
serving their sites without it; only control, monitoring and scheduled jobs stop.

## Symptoms

- `/infra` unreachable or the edge answers "upstream web unavailable".
- No new `Server Metric` rows, every server drifts to `Down` after 3 minutes (that is the
  heartbeat rule firing because the collector stopped, not the servers).
- Jobs stay `Queued`; a job that was `Running` is marked `Failed` by crash recovery once
  the controller is back (no heartbeat for 5 minutes) and its lock is released.

## Restore service

1. Host up? `ssh frappe@<controller>` → `./deploy/staging/staging.sh status` (staging) or
   `sudo supervisorctl status` (production). Start what is stopped; check
   `logs/infra-staging-*.log` or `logs/web.error.log` for the reason.
2. Redis / MariaDB down? `systemctl status redis-server mariadb`; a full disk is the usual
   cause (`df -h`), prune `sites/<site>/private/infra_ansible/` run directories and old
   `logs/*.log.N` first.
3. Scheduler paused? `bench --site <site> scheduler status`; `scheduler enable` and remove
   `pause_scheduler` from site config.
4. Worker missing? Jobs need `bench worker --queue infra`. After it is back, re-run any job
   that crash recovery marked `Failed`: each is idempotent (Ansible roles, ff-only pulls).

## Rebuild the controller from the off-site backup

Daily `bench backup --with-files` of the controller site is uploaded to the off-site bucket
(Infra Settings → off-site; `backups/controller.py`). On a fresh droplet:

1. Provision a bench with only `frappe` and `infra_control` (`deploy/staging/README.md` for
   the shape; production uses `bench setup production`).
2. Download the newest `controller/<site>/<date>/` objects from the off-site bucket.
3. `bench --site <site> restore <db.sql.gz> --with-public-files … --with-private-files …`
   then `bench --site <site> migrate`.
4. Put the controller SSH key (`~/.ssh/id_ed25519`, 0600) and the console CA
   (`~/.infra-control/ssh_ca`, 0600) back from your secrets store. Both are **not** in the site
   backup on purpose; without them regenerate: a new SSH public key must be added to the
   DigitalOcean account as `infra-control` and to every managed server's
   `~frappe/.ssh/authorized_keys` (one `server.exec` per server from a still-trusted key, or by
   hand), and a new CA is rolled out with `server.trust_ca`.
5. Set `Infra Settings.controller_ip` to the new IP: the managed firewall allows SSH only
   from it (`inventory.sync` re-applies it).
6. Open Settings → Security and clear every `fail`.

## Prevent

- Security posture: "Controller backup off DigitalOcean" must be `pass` and recent.
- Alert rule `heartbeat` on the controller's own server when it is managed too.
