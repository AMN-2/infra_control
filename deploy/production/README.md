# Production — quick guide

Full details: `docs/runbooks/production_install.md`. This page is the short path.

## 0. Server requirements

**Controller droplet** (runs only Infra Control, no client sites):

| | Minimum | Recommended |
|---|---|---|
| Image | Ubuntu 22.04 LTS | **Ubuntu 24.04 LTS**, x86-64 |
| Size | `s-2vcpu-2gb` (frontend build needs the 2 GB swap the installer does not add) | **`s-2vcpu-4gb`** (2 vCPU / 4 GB RAM / 80 GB SSD) up to 20 managed servers; `s-4vcpu-8gb` beyond that |
| Disk | 50 GB | 80 GB (Ansible run artifacts, metrics for 2 years, controller backups before upload) |
| Region | any | the same region as the managed servers (lower SSH latency, VPC later) |
| Network | public IPv4, ports 22 / 80 / 443 reachable | DigitalOcean Monitoring enabled on the droplet |
| DNS | an `A` record (`ops.example.com`) pointing at the droplet before install | |
| Access | root SSH with your key; nothing else installed on the droplet | |

**Managed servers** (the ones Infra Control provisions or onboards):

| | Requirement |
|---|---|
| Provider | DigitalOcean only (v1); droplet tagged `infra-control` + `role:<all|app|db|proxy>` |
| OS | Ubuntu 22.04 or 24.04; `python3` present (onboard-server.sh installs it) |
| Size | whatever the sites need; the bench role itself needs ≥ 2 GB RAM for `bench build` |
| Access | user `frappe` with passwordless sudo and the controller's SSH key; root login and password SSH off |
| Firewall | DigitalOcean firewall `infra-control-managed`: SSH from the controller IP only, 80/443 open |
| Monitoring | DigitalOcean Monitoring agent enabled (metrics come from the DO API, not from SSH) |

## 1. Install the controller (fresh Ubuntu 24.04 droplet, as root)

```bash
git clone --depth 1 https://github.com/AMN-2/infra_control.git /opt/infra_control-installer
cd /opt/infra_control-installer/deploy/production
INFRA_SITE=ops.example.com ADMIN_PASSWORD='<strong>' LETSENCRYPT_EMAIL=you@example.com \
ALLOW_CIDRS='<your-office-ip>/32' ./install.sh
```

Expect: `== packages` … `== firewall`, then a summary with the URL, the public IP and the
controller's SSH public key. Takes 10–15 minutes. Re-run the same command if it stops.

Check:

```bash
supervisorctl status                      # every line RUNNING
curl -s https://ops.example.com/api/method/ping   # {"message":"pong"}
```

## 2. First setup (in the UI, in this order)

1. `/app/user`: your user with role **Infra Admin**.
2. `/infra/settings/security`: enable 2FA.
3. `/app/infra-settings`: Controller IP (from the summary), Telegram, Spaces, off-site bucket.
4. DigitalOcean → Security: add the printed SSH key, named **infra-control**.
5. `/app/provider-account`: `DO-PROD`, DigitalOcean token (custom scopes), `is_staging` off.
6. `/app/infra-settings` → Production: tick **Allow production accounts**.

## 3. Connect servers

- **New server**: Servers → New server. Done when the job is `Success` and the server is Active.
- **Existing server**, as root on it:

  ```bash
  CONTROLLER_PUBKEY='<key from the summary>' CONTROLLER_IP=<controller ip> ./onboard-server.sh
  ```

  Then in DigitalOcean tag the droplet `infra-control` + `role:all`, attach the firewall
  `infra-control-managed`, and in the UI run **Sync** on `DO-PROD`, then `server.trust_ca`.

Keep the first server read-only for 48 hours (monitoring only), then start with `site.backup`.

## 4. Update later (as user `frappe`)

```bash
~/frappe-bench/apps/infra_control/deploy/production/deploy.sh
```

## Files

| File | Purpose |
|---|---|
| `install.sh` | fresh droplet → controller (bench, site, supervisor, nginx + TLS, firewall) |
| `deploy.sh` | update from GitHub (fast-forward, migrate, rebuild UI, restart) |
| `onboard-server.sh` | prepare an existing server (frappe user, key, sshd) |
| `nginx-site.conf.tmpl`, `supervisor-infra.conf.tmpl` | templates rendered by install.sh |

Back up `~frappe/.ssh/id_ed25519`, `~frappe/.infra-control/ssh_ca/` and
`/root/.infra-control/db-root-password` to your password manager; they are not in site backups.
