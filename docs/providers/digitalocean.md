# DigitalOcean adapter (A2.1)

Package: `infra_control/providers/digitalocean/`. Only `client.py` speaks HTTP, only
`mapping.py` knows DigitalOcean's status strings, and only `settings.py` touches Frappe
(plan section 4.3). Capabilities: `site`, `bench`, `server`, `ssh`, `snapshot`,
`service_control`, `metrics`, `custom_playbook` (section 4.2).

## 1. Transport

| Rule | Implementation |
|---|---|
| Auth | `Authorization: Bearer <Provider Account.api_token>`; the token lives in `ProviderConfig` (hidden from `repr`) and the session headers only. |
| Timeout | 30 s per request. |
| Retries | Up to 5 attempts on 429, 500, 502, 503, 504 and connection errors. Full-jitter exponential backoff (base 0.5 s, cap 20 s). A 429 waits `Retry-After`, else until `RateLimit-Reset`. |
| Rate limit | `RateLimit-Limit/Remaining/Reset` are recorded on every response. Below 50 remaining, the next call sleeps until the window resets instead of spending the rest of the 5,000/h budget. |
| Errors | 404 → `NotFound`; 429 after retries → `RateLimited` (HTTP 429); other 4xx/5xx → `ProviderError` (HTTP 502) carrying DO's `id` and `message`, never the token. |
| Pagination | `list_all()` follows `links.pages.next` (page size 200). |

## 2. Endpoints used

| Call | Endpoint | Used by |
|---|---|---|
| List droplets by tag | `GET /v2/droplets?tag_name=infra-control` | `sync_inventory` |
| Get droplet | `GET /v2/droplets/{id}` | provisioning poll |
| Create droplet | `POST /v2/droplets` | `create_server` |
| Droplet action | `POST /v2/droplets/{id}/actions` (`reboot`, `snapshot`) | `reboot_server`, `snapshot_server` |
| Get action | `GET /v2/actions/{id}` | `get_status` for `do_action` |
| SSH keys | `GET /v2/account/keys` | `create_server` (key named `infra-control`) |
| Firewalls | `GET/POST /v2/firewalls`, `PUT /v2/firewalls/{id}`, `POST /v2/firewalls/{id}/droplets` | provisioning |
| DNS | `GET/POST/DELETE /v2/domains/{d}/records` | client only; `site.add_domain` uses it from A2.3 |
| Monitoring | `GET /v2/monitoring/metrics/droplet/{cpu,memory_total,memory_available,filesystem_size,filesystem_free,load_1}` | `get_metrics` |

Spaces (S3-compatible, `spaces.py`, boto3) stores off-site backups at
`spaces://<bucket>/<site>/<file>`; `Backup.location` never holds a signed URL.

## 3. Operations and `OpRef` kinds

| Kind | External id | Steps reported |
|---|---|---|
| `do_action` | DO action id | One step named after the action type, with DO's start and completion times. |
| `provision` | droplet id | `Create droplet` (until `active`) → `Attach managed firewall` → the steps of `server_provision.yml`. Success sets `created = ("Server", <droplet id>)` (ADR 0001). |
| `ansible` | runner id | Steps of the playbook, from the `PlaybookRunner` (A2.2). |

`cancel()` stops a running Ansible stage; a DO action cannot be cancelled once accepted, so it
returns `False` and the engine reports the job when the action ends.

## 4. Status mapping (`mapping.py`)

| DigitalOcean | Unified |
|---|---|
| droplet `new` | Server `Provisioning` |
| droplet `active` | Server `Active` |
| droplet `off` | Server `Down` |
| droplet `archive` | Server `Archived` |
| droplet, anything else | Server `Degraded` (never guessed healthy) |
| action `in-progress` | `Running` |
| action `completed` | `Success` |
| action `errored` | `Failed` |

## 5. Provisioning security (plan section 13.2)

- The droplet gets the account's SSH key named `infra-control` and a cloud-init
  (`cloud_init.yaml`) that creates the `frappe` sudo user with that key, disables root login and
  password authentication, and drops an `sshd_config.d` override.
- The managed firewall `infra-control-managed` allows SSH only from
  `Infra Settings.controller_ip/32`, HTTP and HTTPS from anywhere, all outbound. Rules are kept
  current on every provision. **If `controller_ip` is empty the provision fails** instead of
  opening SSH to the world.
- Droplets are tagged `infra-control`, `role:<role>`, `staging` (staging accounts) and the user's
  tags. Only `infra-control` droplets are synced, so unrelated droplets on the account are never
  touched.

## 6. Metrics

`get_metrics()` reads the last 10 minutes from DO Monitoring (the droplet must be created with
`monitoring: true`, which `create_server` sets). CPU is `1 − Δidle / Δtotal` over the last two
cumulative samples; RAM and disk are `1 − available / total`. `queue_backlog` needs the host and
is added by the collector in A3.1.

## 7. Site operations (A2.3)

| Method | Playbook | What the adapter adds | Recorded on success |
|---|---|---|---|
| `create_site` | `site_create.yml` | apps, bench path; `admin_password` (masked by the engine, `no_log` in the play) | `Site` (name = domain) |
| `backup_site` | `site_backup.yml` | presigned **PUT** URLs per file (`database`, `public`, `private`) | one `Backup` per uploaded file, `Site.last_backup` |
| `update_site` (`site.migrate`) | `site_migrate.yml` | presigned PUT URL for the database | the pre-migrate `Backup` |
| `restore_site` | `site_restore.yml` | presigned **GET** URLs for the backup's files (found by the key prefix) | — |
| `set_maintenance` | `site_maintenance.yml` | `maintenance_on` | — |
| `add_domain` | `site_add_domain.yml` | an `A` record through the DO API when the zone is on the account (`dns_managed`) | the domain in `Site.custom_domains` |
| `suspend_site` | `site_suspend.yml` | `suspended` (maintenance + scheduler paused, the same meaning as Q7 on Frappe Cloud) | — |

- **Spaces keys never leave the controller.** The server gets presigned URLs that expire after
  6 hours, and every task that touches one is `no_log` (a unit test enforces it). Without Spaces
  configured, backups and migrations refuse to run: backups must leave the server.
- **`site.migrate` backs up first** (plan 13.7). The backup tasks have no `ignore_errors`; a failed
  dump or upload fails the job before maintenance mode is touched. A failed `bench migrate`
  still switches maintenance off (`always`), then fails the job.
- `provision` success records the `Server` (found again by `provider_ref`), so the engine links the
  job to it (ADR 0001).
- Recording happens once per operation in the adapter instance. If the worker restarts mid-run,
  the job still finishes correctly but the document is not recorded; `inventory.sync` (A2.5)
  reconciles it.
- TLS: `site.add_domain` asks certbot only when the name already resolves to the server, so a
  pending DNS change never fails the job; the output says to run it again.

## 8. Gaps until later tasks

| Gap | Closes in |
|---|---|
| Benches and sites in `sync_inventory()` (needs host discovery) | A2.5 |
| Live verification against a staging DigitalOcean token | Phase 2 exit gate; needs a `Provider Account` with `is_staging = 1` and a real token |
| Site playbooks exercised end to end (they need a real bench) | Phase 2 exit gate |

## 9. Setup on the controller

1. In the DigitalOcean account used for staging, create a token with custom scopes:
   `droplet:create/read/update/delete`, `actions:read`, `firewall:create/read/update`,
   `ssh_key:read`, `domain:read/create/delete`, `monitoring:read`, `tag:create/read`.
2. Add the controller's SSH public key under Settings → Security, named `infra-control`.
3. Create a `Provider Account` (`provider = digitalocean`, `is_staging = 1`, the token).
4. Fill `Infra Settings.controller_ip` and, for backups, the Spaces bucket, region, key and secret.

## 10. inventory.sync (A2.5)

Reconciles the whole tree, not just servers. Two halves, run as one `Infra Job`:

1. **API** — droplets tagged `infra-control` become the server list (status, address, size,
   region, role).
2. **Hosts** — one Ansible run (`inventory_discover.yml`) scans every reachable, active server
   in parallel with a read-only Python script, listing each bench (path, Frappe version, apps)
   and site (domain, maintenance mode). `ignore_unreachable` keeps the run green; a server that
   did not answer becomes a `server_unreachable` finding.

`infra_control/inventory/plan.py` is pure: provider inventory plus the account's documents in, a
plan of creates, updates and findings out. `apply.py` is the only writer and emits
`infra:inventory.changed`.

| Match | By |
|---|---|
| Server | `provider_ref` (droplet id) |
| Bench | (server, path) |
| Site | domain |

Rules (plan 9.4): the provider owns existence and provider facts; documents are created and
updated to match. **Nothing is deleted or archived automatically.** A droplet the provider no
longer lists, or a bench or site missing on a server discovery actually scanned, is a finding for
a human (`server_missing`, `bench_missing`, `site_missing`). Human-set states (`Archived`,
`Suspended`) are never overwritten, and a bench or site on a server discovery could not reach is
never reported missing.

Scheduled hourly on every enabled `Provider Account` by
`infra_control.inventory.schedule.sync_all_providers` (hooks). It creates `Infra Job`s as the
`scheduler` user, so runs are audited, locked per account and visible in the UI; an account with
a sync already queued or running is skipped. The engine lets the scheduler user run only
low-risk playbooks.

Verified live (2026-10-08): `inventory.sync` on `DO-STAGING-LIVE` discovered gate-02 and gate-03,
filled in both benches' Frappe version and apps (the provision recorder leaves them empty), and
left the archived server, its bench and site untouched with no false findings.
