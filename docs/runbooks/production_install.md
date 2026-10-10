# Runbook: install the production controller and connect your servers

The production controller is a dedicated DigitalOcean droplet that runs only `infra_control`
(plan section 2, "hosts no client sites"). This runbook takes a fresh droplet to a working
control plane, then connects new and existing servers. Scripts live in `deploy/production/`.

## 1. Where the controller lives (decision)

**Same DigitalOcean account as the managed servers, in its own Project, with its own scoped
token.** The alternative (a second DigitalOcean account for the controller) buys nothing here:

- `inventory.sync`, the managed firewall, DO Monitoring metrics and provisioning all go through
  the **Provider Account token**, and a token only sees the account it belongs to. The servers
  therefore define which account the token must come from; the controller droplet can sit
  anywhere, since every SSH-backed operation goes to the server's public IP with the
  controller's key.
- What actually isolates the controller from the servers is: (1) the controller droplet is
  **not tagged `infra-control`**, so the system never manages or deprovisions itself; (2) the
  token has **custom scopes** (droplet, firewall, ssh_key, monitoring, domain, action: read +
  create + update + delete, nothing else: no billing, no team, no Spaces keys); (3) staging and
  production tokens are different tokens on different controllers (plan 13.3).
- Same account also allows a **VPC**: put the controller and the servers in one region/VPC
  and SSH can later move to private IPs (`Server.public_ip` is used today; private networking
  is a v2 switch, not required).

Use a second account only when you need a billing or ownership boundary (for example a
client's servers under the client's own account). Then one Provider Account per DigitalOcean
account, each with its own token, and the controller in whichever account you own.

Sizing: `s-2vcpu-4gb` runs the controller comfortably up to the plan's 20 servers; the
`infra` worker runs one Ansible play at a time per server, in parallel across servers.

## 2. Install

Prerequisites: Ubuntu 24.04 droplet (22.04 works), a DNS name pointing at it
(`ops.example.com`), root SSH, and the allowlist CIDRs of the people who will use the UI.

```bash
ssh root@<controller-ip>
git clone --depth 1 https://github.com/AMN-2/infra_control.git /opt/infra_control-installer
cd /opt/infra_control-installer/deploy/production
INFRA_SITE=ops.example.com ADMIN_PASSWORD='<strong>' LETSENCRYPT_EMAIL=you@example.com \
ALLOW_CIDRS='203.0.113.4/32,198.51.100.0/24' SSH_ALLOW_CIDRS='203.0.113.4/32' ./install.sh
```

`install.sh` (idempotent, re-run after any failure) builds:

| Layer | What |
|---|---|
| OS | `frappe` user, MariaDB on 127.0.0.1 (root password in `/root/.infra-control/db-root-password`), Node 20, ufw (22 from `SSH_ALLOW_CIDRS`, 80, 443), fail2ban, key-only SSH |
| Bench | `frappe` version-15 + `infra_control` (`APP_BRANCH`, default `main`), one site, scheduler on, `workers.infra` declared, `infra_ssh_private_key` set |
| Supervisor | bench's web, socket.io, redis, default workers **plus** `infra-control-worker-infra` and `infra-control-console` (`supervisor-infra.conf.tmpl`) |
| nginx | TLS (Let's Encrypt with auto-renew, or `TLS=selfsigned` for IP-only), HSTS, IP allowlist, `/socket.io` and `/console/` WebSocket upgrades (`nginx-site.conf.tmpl`) |
| Keys | controller SSH key `~frappe/.ssh/id_ed25519` (printed at the end); the console CA is created on first use under `~frappe/.infra-control/ssh_ca` |

Everything it prints at the end (URL, public key, controller IP) is needed in section 3.
Back up `/root/.infra-control/`, `~frappe/.ssh/id_ed25519` and `~frappe/.infra-control/ssh_ca`
to your secrets store now: they are deliberately not in the site backup
(`controller_down.md`).

## 3. First configuration (in this order)

1. **Sign in** at `https://ops.example.com/infra` as Administrator. Create your users in
   `/app/user` with the roles `Infra Admin`, `Infra Operator` or `Infra Viewer`.
2. **2FA**: Settings → Security → enable two-factor (needs outgoing email on the site, or
   use OTP app). Mandatory when `ALLOW_CIDRS` was empty.
3. **Infra Settings** (`/app/infra-settings`): Controller IP (the printed public IP; the managed
   firewall allows SSH only from it), Telegram bot token + chat id, Spaces bucket/region/keys
   (production bucket, not the staging one), off-site S3 endpoint + bucket for the controller's
   own daily backup.
4. **DigitalOcean**: add the printed public key as an SSH key named `infra-control`; create a
   personal access token with custom scopes (section 1) in the production Project; create the
   firewall `infra-control-managed` if it does not exist yet (SSH from `<controller ip>/32`,
   HTTP/HTTPS from anywhere; the first provision creates it anyway).
5. **Provider Account**: `DO-PROD`, provider DigitalOcean, token, `is_staging = 0`, enabled.
   Using it is refused with "production accounts are not enabled" until step 6.
6. **Allow production accounts**: Infra Settings → Production → tick it. This is the only
   switch that lets a non-staging account run jobs (plan rule 11.6 stays the default
   everywhere else; `security.posture` shows `production_gate`).
7. **Posture**: Settings → Security must show no `fail` except "last restore test" (which
   passes after the first monthly run or a manual `site.restore_test`).

## 4. Connecting servers

**New servers**: Servers → New server (ADR 0006). The wizard provisions from the live
catalogue; the droplet gets the key, the firewall, the hardened sshd and the bench role.
Nothing else to do.

**Existing servers** (a bench you set up by hand before Infra Control):

1. On the server, as root:
   ```bash
   CONTROLLER_PUBKEY='<printed key line>' CONTROLLER_IP=<controller ip> ./onboard-server.sh
   ```
   It creates the `frappe` sudo user if missing, installs the key, installs python3, and
   turns off root login and password SSH. It does not touch the bench, nginx or MariaDB.
   Keep your own SSH session open until you have verified `ssh frappe@<server>` from the
   controller works.
2. In DigitalOcean: tag the droplet `infra-control` and `role:all` (or `role:app`,
   `role:db`, `role:proxy`), and attach it to the `infra-control-managed` firewall. Only
   tagged droplets are ever synced; untagged ones are invisible to the system.
3. On the controller: Servers → the account → **Sync** (`inventory.sync`). The Server record
   appears with its benches and sites discovered from the host (`discover_bench.py`), and a
   `drift` alert lists anything the discovery could not map; adopt or fix, then sync again.
4. Run `server.trust_ca` on the new Server so the web console works, then open a console
   session as the smoke test.
5. Read-only period (plan Phase 4 exit gate): leave the server with monitoring and inventory
   only for **48 hours**. No `fail` posture item, metrics every minute, no false alerts. Only
   then run the first write operation (`site.backup`, then `site.migrate`).

**Servers that are not on DigitalOcean** cannot be connected in v1: every adapter call goes
through the DigitalOcean API for inventory, firewall and metrics (plan 1, out of scope:
"other cloud providers").

## 5. Operating

| Task | How |
|---|---|
| Update the controller | as `frappe`: `~/frappe-bench/apps/infra_control/deploy/production/deploy.sh` (fast-forward only, refuses during a running job, restarts supervisor) |
| Status | `sudo supervisorctl status`, `bench --site <site> scheduler status`, Settings → Security |
| Logs | `~/frappe-bench/logs/worker-infra.log`, `console.log`, `web.error.log`; nginx `/var/log/nginx/` |
| Change the allowlist | edit `ALLOW_CIDRS` and re-run `install.sh` with the same variables (it re-renders nginx only) |
| Rotate the controller key | new key → add to DigitalOcean as `infra-control` → `server.exec` on every server appends it to `~frappe/.ssh/authorized_keys` → switch `infra_ssh_private_key` → remove the old key |
| Controller down / rebuild | `controller_down.md` |
| Provider API down | `provider_api_down.md` |

## 6. Security checklist before the first production write

- [ ] Controller droplet is not tagged `infra-control`, is in its own Project.
- [ ] Token has custom scopes; staging token is a different token on a different controller.
- [ ] nginx allowlist or 2FA on (both preferred); `SSH_ALLOW_CIDRS` set; ufw active.
- [ ] Managed firewall allows SSH only from the controller IP; every managed server attached.
- [ ] Off-site controller backup `pass` in posture; a manual restore of that backup rehearsed.
- [ ] `Allow production accounts` is on **only** on this controller.
- [ ] Telegram alert received for a deliberate `service.control stop nginx` on one server.
- [ ] 48-hour read-only period completed without incident.
