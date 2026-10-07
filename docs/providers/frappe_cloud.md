# Frappe Cloud (Press API) — endpoint verification

**Task:** A0.3. **Verified against:** `frappe/press` `master` @ `4a66670e869c89bbcef2e12fe3e564f14ebfe80e` (2026-10-07).
**Status:** source-verified. Live verification against a throwaway Frappe Cloud team is blocked on plan
open question 5 (staging team); the daily contract test (A2.4) will replay every call below.

> The Press API is the dashboard's internal API, not a stable public contract. Every call in this file
> goes through `infra_control/providers/frappe_cloud/client.py::FrappeCloudClient` only. Nothing else
> in the app may know these paths. Re-verify this file whenever the contract test raises drift.

## 1. Transport and authentication

| Item | Value | Source |
|---|---|---|
| Base URL | `https://frappecloud.com` (configurable per `Provider Account`) | — |
| Path | `/api/method/<dotted.path>` (Frappe whitelisted methods) | Frappe |
| Auth header | `Authorization: token <api_key>:<api_secret>` | Frappe token auth |
| Team header | `X-Press-Team: <team name>` — **required** on every call | `press/utils/__init__.py:129`, `press/api/client.py:630` |
| Create key | `POST press.api.account.create_api_secret` → `{api_key, api_secret}` (needs a logged-in dashboard session; done once by the human, stored in `Provider Account.api_token` as `key:secret`) | `press/api/account.py:1155` |
| Whoami | `GET press.api.account.me` → `{user, team}` — used by the contract test as the auth probe | `press/api/account.py:1168` |
| Success body | Frappe envelope `{"message": <return value>}` | Frappe |
| Error body | Frappe `{"exception", "exc_type", "_server_messages"}` with 4xx/5xx; `PermissionError` = wrong team or not owned | Frappe |
| Timeouts | Client default 30 s; Press Agent Jobs are async, we poll | ours |

Team scoping: every `press.api.site.*` call decorated `@protected("Site")` checks `Site.team == current team`
unless the user is a System User (`press/api/site.py:68-100`). API-token users are Website Users, so the
team header must match the site's team.

## 2. Generic document API (`press.api.client`) — preferred for reads

`press/api/client.py`. Allowed doctypes (`ALLOWED_DOCTYPES`, line 31) include `Site`, `Site Backup`,
`Site Domain`, `Site Update`, `Site Config`, `Site Plan`, `Bench`, `Bench App`, `Release Group`,
`Release Group App`, `Agent Job`, `Agent Job Type`. `get_list` auto-filters by the current team when the
doctype has a `team` field (line 161).

| Method | Params | Returns | Line |
|---|---|---|---|
| `POST press.api.client.get_list` | `doctype`, `fields: list`, `filters: dict`, `order_by`, `start=0`, `limit=20`, `parent` | `[ {field: value} ]` | 126 |
| `POST press.api.client.get` | `doctype`, `name` | full document dict (+ `__onload`, dashboard fields) | 234 |
| `POST press.api.client.run_doc_method` | `dt`, `dn`, `method`, `args: dict` | `{"docs": [<document after the call>]}` in the response root; the method must be `@dashboard_whitelist`ed | 363 |

Sample (derived from source; fields chosen by us):

```json
POST /api/method/press.api.client.get_list
{"doctype": "Site", "fields": ["name", "host_name", "status", "group", "bench", "server", "cluster", "plan", "creation", "current_database_usage", "current_disk_usage"], "filters": {"status": ["!=", "Archived"]}, "limit": 200}
→ {"message": [{"name": "staging-client-c.frappe.cloud", "host_name": "staging.client-c.frappe.cloud", "status": "Active", "group": "bench-abc123", "bench": "bench-abc123-000001-f1", "server": "f1-fra-1.frappe.cloud", "cluster": "Frankfurt", "plan": "USD 25", "creation": "2026-09-01 10:00:00.000000", "current_database_usage": 12, "current_disk_usage": 3}]}
```

## 3. Calls used by the adapter, by `Provider` method

### 3.1 `sync_inventory()`

| Our entity | Press call | Notes |
|---|---|---|
| Bench | `press.api.client.get_list` `doctype=Release Group`, fields `name,title,version,enabled,public,creation,modified` | A Press **Release Group** is the user-facing "bench"; a Press `Bench` is one deployment of it. Our `Bench.provider_ref` = Release Group name. `press.api.bench.all` (`press/api/bench.py:116`) returns the same with `number_of_sites`. |
| Bench apps | `press.api.client.get_list` `doctype=Release Group App`, `filters={"parenttype":"Release Group","parent":<rg>}`, fields `app,title,source,branch` | child table needs `parenttype` + `parent` (`client.py:151`) |
| Bench frappe version | `press.api.client.get` `Release Group` → `version` (e.g. `Version 15`) | |
| Site | `press.api.client.get_list` `doctype=Site` (fields in section 2) or `press.api.site.all` (`site.py:1634`, returns `name,host_name,status,creation,bench,current_*_usage,team,cluster,group,title,version,public,plan,tags`) | `provider_ref` = Site name |
| Site detail | `press.api.site.get` `name` (`site.py:1722`) → `{name, host_name, status, group, team, frappe_version, server, ip, site_tags, info:{created_on,last_deployed,auto_updates_enabled}, pending_for_long, site_migration, version_upgrade, ...}` | `ip` is the proxy IP (DNS target) |
| Custom domains | `press.api.site.domains` `name` (`site.py:807`) → `[{name, domain, status, retry_count, redirect_to_primary, primary}]` | status: `Pending / In Progress / Active / Broken` |
| Backups (last_backup) | `press.api.site.backups` `name` (`site.py:746`) → list of Site Backup rows: `name,with_files,database_file,database_size,database_url,public_*,private_*,config_*,creation,status,offsite,remote_*` sorted newest first | up to 10 on-site + N offsite |

### 3.2 Mutations — every call returns an Agent Job (our `OpRef(kind="press_job")`)

| `Provider` method | Press call | Params | Returns / how we get the job | Source |
|---|---|---|---|---|
| `create_site(site, bench, apps)` | `POST press.api.site.new` | `site: {name: <subdomain>, domain: <press domain>, group: <release group>, plan: <Site Plan>, apps: [app names], version: "Version 15", cluster?, files?: {database, public, private, config}, skip_failing_patches?}` | `{"site": <name>, "job": <Agent Job name of "New Site">}` | `site.py:409,153,250` |
| `backup_site(site, with_files)` | `POST press.api.site.backup` | `name`, `with_files: bool` | returns nothing; poll `press.api.site.jobs` with `filters={"site": name, "job_type": "Backup Site"}` newest, or `press.api.site.backups` for the new `Site Backup` (`status` Pending→Success) | `site.py:2148`, `Site.backup` `site.py:1585` |
| `restore_site(site, backup_ref)` | `POST press.api.site.restore` | `name`, `files: {database: <Remote File>, public?, private?, config?}`, `skip_failing_patches?` | `Site.restore_site` returns the Agent Job (type "Restore Site"); site status → `Pending` | `site.py:2178`, `site.py:1504` |
| `update_site(site)` | `POST press.api.site.update` | `name`, `skip_failing_patches=False`, `skip_backups=False` | creates a `Site Update` document; poll `press.api.client.get("Site Update", <name>)` → `status`, `update_job` (Agent Job) | `site.py:2134`, `Site.schedule_update` `site.py:1676` |
| `update_site` (migrate only) | `POST press.api.site.migrate` | `name`, `skip_failing_patches` | Agent Job "Migrate Site"; site → `Pending` then back | `site.py:2166`, `Site.migrate` `site.py:1319` |
| `set_maintenance(site, on=True)` | `POST press.api.site.deactivate` | `name` | sets `maintenance_mode=1`, status `Inactive`; synchronous (Agent Job "Update Site Configuration" follows) | `site.py:2116`, `Site.deactivate` `site.py:3168` |
| `set_maintenance(site, on=False)` | `POST press.api.site.activate` | `name` | status `Active` (or stays `Broken` if unresponsive) | `site.py:2122`, `Site.activate` `site.py:3190` |
| `add_domain(site, domain)` | `POST press.api.site.check_dns` then `POST press.api.site.add_domain` | `name`, `domain` | `check_dns` → `{matched: bool, type, answer...}`; `add_domain` creates a `Site Domain` (status `Pending`→`Active`) and an Agent Job "Add Domain to Upstream"; poll `press.api.site.domains` | `site.py:2267,2283`, `Site.add_domain` `site.py:1924` |
| `suspend_site(site, suspended)` | **not available to team API users** | `Site.suspend` / `Site.unsuspend` (`site.py:3209,3249`) are plain `@frappe.whitelist()` doc methods, not `@dashboard_whitelist`, so `run_doc_method` rejects them (`client.py:458`). Proposed mapping: `deactivate` / `activate` (same effect for users: maintenance mode on, status `Inactive`). See `docs/QUESTIONS.md` Q7. | |
| `get_status(op)` | `GET press.api.site.job` | `job` (Agent Job name) | `{name, job_type, creation, status, start, end, duration, steps: [{step_name, status, start, end, duration, output}]}`; `Undelivered` is reported as `Pending` | `site.py:698` |
| job list | `GET press.api.site.jobs` | `filters`, `order_by`, `limit_start`, `limit_page_length` | `[{name, job_type, creation, status, start, end, duration}]` | `site.py:667` |
| running jobs | `GET press.api.site.running_jobs` | `name` | `[job_detail]` with live step output from cache | `site.py:723`, `agent_job.py:422` |

Not supported by Frappe Cloud for us (capability matrix, plan section 4.2): `create_server`, `reboot_server`,
`snapshot_server`, `control_service`, `get_metrics`. The adapter raises `NotSupported`.

Managed capabilities Press gives us for free: `managed_backup` (scheduled + offsite backups, `Site Backup`
rows with `offsite=1`) and `managed_update` (`Site Update` with automatic backup and recovery).

## 4. Status mapping (lives only in `providers/frappe_cloud/mapping.py`)

| Press entity | Press values (`press/press/doctype/<dt>/<dt>.json`) | Unified |
|---|---|---|
| Site.status | `Pending`, `Installing`, `Updating`, `Recovering` | `Pending` |
| | `Active` | `Active` |
| | `Inactive` | `Maintenance` |
| | `Suspended` | `Suspended` |
| | `Broken` | `Broken` |
| | `Archived` | `Archived` |
| Agent Job.status | `Undelivered`, `Pending` | `Queued` |
| | `Running` | `Running` |
| | `Success` | `Success` |
| | `Failure`, `Delivery Failure` | `Failed` |
| Agent Job Step.status | `Pending` → `Queued`; `Running`; `Success`; `Failure`/`Delivery Failure` → `Failed`; `Skipped` → `Skipped` | |
| Site Update.status | `Pending`, `Scheduled` → `Queued`; `Running`, `Recovering` → `Running`; `Success` → `Success`; `Failure`, `Fatal`, `Recovered` (update failed, site rolled back) → `Failed`; `Cancelled` → `Cancelled` | |
| Site Backup.status | `Pending` → `Queued`; `Running`; `Success`; `Failure` → `Failed` | |
| Site Domain.status | `Pending`, `In Progress` → pending; `Active`; `Broken` | surfaced as `custom_domains` only when `Active` |
| Bench (deployment).status | `Pending`, `Installing`, `Updating`, `Active`, `Broken`, `Archived` | informational; our `Bench` tracks the Release Group |

## 5. Sample responses (derived from source; replace with live captures when the staging team exists)

```json
GET /api/method/press.api.site.job?job=<name>
{"message": {"name": "9c1a2b3d4e", "job_type": "Backup Site", "creation": "2026-10-07 09:30:00.000000",
  "status": "Success", "start": "2026-10-07 09:30:02.000000", "end": "2026-10-07 09:31:20.000000", "duration": "0:01:18",
  "steps": [{"step_name": "Backup Site", "status": "Success", "start": "2026-10-07 09:30:02.000000", "end": "2026-10-07 09:31:19.000000", "duration": "0:01:17", "output": "..."},
            {"step_name": "Upload Site Backup to S3", "status": "Success", "start": "...", "end": "...", "duration": "0:00:01", "output": "..."}]}}
```

```json
POST /api/method/press.api.site.new
{"site": {"name": "staging-client-c", "domain": "frappe.cloud", "group": "bench-abc123", "plan": "USD 25", "apps": ["frappe", "erpnext"], "version": "Version 15"}}
→ {"message": {"site": "staging-client-c.frappe.cloud", "job": "7f8e9d0c1b"}}
```

```json
GET /api/method/press.api.site.domains?name=staging-client-c.frappe.cloud
{"message": [{"name": "staging-client-c.frappe.cloud", "domain": "staging-client-c.frappe.cloud", "status": "Active", "retry_count": 0, "redirect_to_primary": 0, "primary": true},
             {"name": "erp.client-c.iq", "domain": "erp.client-c.iq", "status": "Active", "retry_count": 0, "redirect_to_primary": 0, "primary": false}]}
```

Timestamps from Press are naive strings in the Press server's timezone (`YYYY-MM-DD HH:MM:SS.ffffff`);
the client converts them to UTC using the `Provider Account.timezone` setting (default `Asia/Kolkata`,
Frappe Cloud's server timezone) before they reach the unified model.

## 6. Drift guard (A2.4 daily contract test)

For each row in section 3 the test calls the endpoint against the throwaway team and asserts: HTTP 200,
the `message` key present, and every field we read present with the expected JSON type. Any mismatch
raises a `critical` alert with the endpoint and the missing field. The test never mutates anything except
`press.api.site.backup` on the throwaway site.

## 7. Known gaps and decisions

- **Suspend**: not exposed to team users; mapped to deactivate/activate pending Q7.
- **Bench vs Release Group**: our `Bench` is a Press Release Group; deployments (`Bench` docs) are not modelled.
- **Backups are one-shot**: `press.api.site.backup` returns nothing; the adapter locates the resulting job by
  `job_type = "Backup Site"` created after the call time, or falls back to the newest `Site Backup`.
- **No metrics**: `press.api.analytics.*` exists but is out of scope for v1 (plan section 4.2).
- **Rate limits**: Press enforces Frappe's default rate limiter per user; the client sends at most 2 req/s
  and backs off on 429.
