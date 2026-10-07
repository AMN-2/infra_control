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

## 7. Gaps until later tasks

| Gap | Closes in |
|---|---|
| SSH-backed calls (site playbooks, `service.control`, `custom_playbook`, the configure stage of provisioning) raise `ProviderError` from `UnavailableRunner`, never a silent no-op | A2.2 (ansible-runner, roles, Molecule) |
| Site playbooks themselves (`site_*.yml`) | A2.3 |
| Benches and sites in `sync_inventory()` (needs host discovery) | A2.5 |
| Live verification against a staging DigitalOcean token | Phase 2 exit gate; needs a `Provider Account` with `is_staging = 1` and a real token |

## 8. Setup on the controller

1. In the DigitalOcean account used for staging, create a token with custom scopes:
   `droplet:create/read/update/delete`, `actions:read`, `firewall:create/read/update`,
   `ssh_key:read`, `domain:read/create/delete`, `monitoring:read`, `tag:create/read`.
2. Add the controller's SSH public key under Settings → Security, named `infra-control`.
3. Create a `Provider Account` (`provider = digitalocean`, `is_staging = 1`, the token).
4. Fill `Infra Settings.controller_ip` and, for backups, the Spaces bucket, region, key and secret.
