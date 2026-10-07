/* eslint-disable */
// GENERATED from contracts/openapi.yaml by scripts/gen-api.mjs. Do not edit.

export interface paths {
    readonly "/api/method/infra_control.api.overview.summary": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** Counts by status, running jobs, firing alerts */
        readonly get: operations["overview_summary"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.inventory.topology": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** Nodes and edges for providers, servers, benches and sites */
        readonly get: operations["inventory_topology"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.servers.list": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** List servers */
        readonly get: operations["servers_list"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.servers.get": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** Server detail with capabilities, benches and latest metrics */
        readonly get: operations["servers_get"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.sites.list": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** List sites */
        readonly get: operations["sites_list"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.sites.get": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** Site detail with capabilities, bench and recent backups */
        readonly get: operations["sites_get"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.benches.list": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** List benches (Frappe Cloud benches have `server` = null) */
        readonly get: operations["benches_list"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.benches.get": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** Bench detail with its sites and capabilities */
        readonly get: operations["benches_get"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.metrics.series": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** Time series for one metric of one server */
        readonly get: operations["metrics_series"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.playbooks.list": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** Playbooks applicable to a target type, filtered by the target's capabilities */
        readonly get: operations["playbooks_list"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.jobs.run": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly get?: never;
        readonly put?: never;
        /** Validate, audit, create an Infra Job and enqueue it */
        readonly post: operations["jobs_run"];
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.jobs.cancel": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly get?: never;
        readonly put?: never;
        /** Cancel a queued or running job */
        readonly post: operations["jobs_cancel"];
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.jobs.retry": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly get?: never;
        readonly put?: never;
        /** Create a new job linked to a failed one, resuming from its first failed step */
        readonly post: operations["jobs_retry"];
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.jobs.list": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** List jobs, newest first */
        readonly get: operations["jobs_list"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.jobs.get": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** Job with its steps and masked output */
        readonly get: operations["jobs_get"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.bulk.create": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly get?: never;
        readonly put?: never;
        /** Create and start a bulk operation (backup, canary, batches) */
        readonly post: operations["bulk_create"];
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.bulk.pause": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly get?: never;
        readonly put?: never;
        /** Pause after the current batch finishes */
        readonly post: operations["bulk_pause"];
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.bulk.resume": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly get?: never;
        readonly put?: never;
        /** Resume a paused or halted bulk operation with the remaining targets */
        readonly post: operations["bulk_resume"];
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.bulk.cancel": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly get?: never;
        readonly put?: never;
        /**
         * Cancel a bulk operation; stops after the current target finishes
         * @description The target currently running completes (its job is not interrupted); every remaining target
         *     becomes `Skipped` and the bulk operation ends in status `Cancelled`. Allowed from `Queued`,
         *     `Running`, `Paused` and `Halted`; otherwise `409 invalid_state`.
         */
        readonly post: operations["bulk_cancel"];
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.bulk.get": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** Bulk operation with per-target progress */
        readonly get: operations["bulk_get"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.alerts.list": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** List alerts, firing first then newest */
        readonly get: operations["alerts_list"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.alerts.ack": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly get?: never;
        readonly put?: never;
        /** Acknowledge a firing alert */
        readonly post: operations["alerts_ack"];
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.alert_rules.list": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** List alert rules */
        readonly get: operations["alert_rules_list"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.alert_rules.get": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** One alert rule */
        readonly get: operations["alert_rules_get"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.alert_rules.create": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly get?: never;
        readonly put?: never;
        /** Create an alert rule (Infra Admin) */
        readonly post: operations["alert_rules_create"];
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.alert_rules.update": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly get?: never;
        readonly put?: never;
        /** Update an alert rule (Infra Admin); omitted fields keep their value */
        readonly post: operations["alert_rules_update"];
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.alert_rules.delete": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly get?: never;
        readonly put?: never;
        /** Delete a metric alert rule (Infra Admin); its historical alerts are kept. Built-in rules -> 409 invalid_state */
        readonly post: operations["alert_rules_delete"];
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.audit.list": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** Paginated immutable audit log, newest first */
        readonly get: operations["audit_list"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
    readonly "/api/method/infra_control.api.search.query": {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        /** Command palette search across servers, sites, benches, playbooks, jobs and alerts */
        readonly get: operations["search_query"];
        readonly put?: never;
        readonly post?: never;
        readonly delete?: never;
        readonly options?: never;
        readonly head?: never;
        readonly patch?: never;
        readonly trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** @enum {string} */
        readonly ErrorCode: "validation_error" | "permission_denied" | "not_found" | "confirmation_required" | "capability_missing" | "invalid_state" | "invalid_cursor" | "rate_limited" | "provider_error" | "internal_error";
        readonly Error: {
            readonly code: components["schemas"]["ErrorCode"];
            readonly message: string;
            /** @description Machine-readable context; keys depend on `code`. */
            readonly details: {
                readonly [key: string]: unknown;
            };
        };
        readonly ErrorResponse: {
            readonly error: components["schemas"]["Error"];
        };
        /**
         * @description Emitted by Frappe before the handler runs, so it never has the `error` envelope. Verified on
         *     Frappe v15.98 with a test client (integration test `test_auth_shape.py`):
         *     - `AuthenticationError` -> 401: invalid API token.
         *     - `PermissionError` -> 403: Guest calling a non-guest method, i.e. no session or an expired or
         *       invalid `sid` cookie (Frappe resets it to Guest; it does not answer 401).
         *     - `CSRFTokenError` -> 400: POST with a session whose CSRF token does not match
         *       `X-Frappe-CSRF-Token` (only enforced once a token exists for the session, which the `/infra`
         *       page guarantees).
         *     Clients detect "re-authenticate" as `status === 401 || (status === 403 && !("error" in body))`
         *     and "permission denied" as `status === 403 && body.error?.code === "permission_denied"`.
         */
        readonly FrappeFrameworkError: {
            /** @enum {string} */
            readonly exc_type: "AuthenticationError" | "PermissionError" | "CSRFTokenError";
            readonly exception?: string;
            /** @description JSON-encoded list of JSON-encoded message objects (Frappe format) */
            readonly _server_messages?: string;
        } & {
            readonly [key: string]: unknown;
        };
        /** @enum {string} */
        readonly Provider: "digitalocean" | "frappe_cloud";
        /** @enum {string} */
        readonly Capability: "site" | "bench" | "server" | "ssh" | "snapshot" | "service_control" | "metrics" | "custom_playbook" | "managed_backup" | "managed_update";
        /** @enum {string} */
        readonly ServerStatus: "Provisioning" | "Active" | "Degraded" | "Down" | "Archived";
        /** @enum {string} */
        readonly SiteStatus: "Pending" | "Active" | "Maintenance" | "Suspended" | "Broken" | "Archived";
        /** @enum {string} */
        readonly JobStatus: "Queued" | "Running" | "Success" | "Failed" | "Cancelled";
        /** @enum {string} */
        readonly StepStatus: "Queued" | "Running" | "Success" | "Failed" | "Cancelled" | "Skipped";
        /** @enum {string} */
        readonly BulkStatus: "Queued" | "Running" | "Paused" | "Halted" | "Success" | "Failed" | "Cancelled";
        /** @enum {string} */
        readonly BulkPhase: "backup" | "canary" | "batches" | "done";
        /** @enum {string} */
        readonly BulkTargetStatus: "Pending" | "Running" | "Success" | "Failed" | "Skipped";
        /** @enum {string} */
        readonly AlertStatus: "firing" | "acknowledged" | "resolved";
        /** @enum {string} */
        readonly Severity: "info" | "warning" | "critical";
        /** @enum {string} */
        readonly Risk: "low" | "medium" | "high";
        /** @enum {string} */
        readonly TargetDoctype: "Server" | "Site" | "Bench" | "Provider Account";
        /**
         * @description `metric`: threshold on a server metric (user-created). `heartbeat`: no server heartbeat for
         *     `for_minutes`. `ssl_expiry`: a site certificate expires within `threshold` days. `drift`:
         *     inventory sync found a difference. `contract`: the daily Press API contract test failed.
         *     Only `metric` rules can be created or deleted; the other kinds exist as built-in rules.
         * @enum {string}
         */
        readonly AlertRuleKind: "metric" | "heartbeat" | "ssl_expiry" | "drift" | "contract";
        /** @enum {string} */
        readonly ServerRole: "app" | "db" | "proxy" | "all";
        /** @enum {string} */
        readonly MetricName: "cpu" | "ram" | "disk" | "load1" | "queue_backlog";
        /** @enum {string} */
        readonly Resolution: "1m" | "1h" | "1d";
        /** @enum {string} */
        readonly FailurePolicy: "halt" | "continue";
        /** @enum {string} */
        readonly Operator: "gt" | "gte" | "lt" | "lte" | "eq";
        /** @enum {string} */
        readonly AlertChannel: "telegram" | "email";
        /** @enum {string} */
        readonly BackupKind: "db" | "files" | "snapshot";
        /** @enum {string} */
        readonly AuditResult: "success" | "failed" | "denied";
        /** @enum {string} */
        readonly SearchResultType: "server" | "site" | "bench" | "playbook" | "job" | "alert";
        readonly TargetRef: {
            readonly target_doctype: components["schemas"]["TargetDoctype"];
            readonly target_name: string;
        };
        readonly JobRef: {
            readonly job: string;
        };
        readonly BulkRef: {
            readonly bulk: string;
        };
        /** @description Pass as `cursor` to fetch the next page; `null` when there is none. */
        readonly NextCursor: string | null;
        readonly InstalledApp: {
            readonly app: string;
            readonly version: string | null;
            readonly branch: string | null;
        };
        readonly Server: {
            /** @description Stable id (naming series), e.g. `SRV-0001` */
            readonly name: string;
            /** @description Display name (the droplet name); used as the topology label and the search title */
            readonly hostname: string;
            readonly provider: components["schemas"]["Provider"];
            readonly provider_account: string;
            /** @description Droplet id */
            readonly provider_ref: string;
            readonly public_ip: string | null;
            readonly private_ip: string | null;
            readonly role: components["schemas"]["ServerRole"];
            readonly region: string;
            readonly size: string;
            readonly tags: readonly string[];
            readonly status: components["schemas"]["ServerStatus"];
            /** Format: date-time */
            readonly last_heartbeat: string | null;
            /** @description Provider-level capability set (plan section 4.2); actions come from `playbooks.list` */
            readonly capabilities: readonly components["schemas"]["Capability"][];
            readonly bench_count: number;
            readonly site_count: number;
        };
        readonly ServerPage: {
            readonly items: readonly components["schemas"]["Server"][];
            readonly next_cursor: components["schemas"]["NextCursor"];
        };
        readonly MetricSnapshot: {
            /** Format: date-time */
            readonly ts: string;
            /** @description percent */
            readonly cpu: number;
            /** @description percent */
            readonly ram: number;
            /** @description percent */
            readonly disk: number;
            readonly load1: number;
            readonly queue_backlog: number;
        };
        readonly ServerDetail: components["schemas"]["Server"] & {
            readonly benches: readonly components["schemas"]["Bench"][];
            readonly latest_metrics: components["schemas"]["MetricSnapshot"] | null;
            /** @description Name of the job currently holding this server's lock */
            readonly running_job: string | null;
        };
        readonly Bench: {
            readonly name: string;
            /** @description Display name (bench directory name or Press release group title) */
            readonly title: string;
            readonly provider: components["schemas"]["Provider"];
            readonly provider_account: string;
            readonly provider_ref: string;
            /** @description `null` for Frappe Cloud benches */
            readonly server: string | null;
            readonly path: string | null;
            readonly frappe_version: string | null;
            readonly apps: readonly components["schemas"]["InstalledApp"][];
            readonly site_count: number;
            /** @description Provider-level capability set (plan section 4.2); actions come from `playbooks.list` */
            readonly capabilities: readonly components["schemas"]["Capability"][];
        };
        readonly BenchPage: {
            readonly items: readonly components["schemas"]["Bench"][];
            readonly next_cursor: components["schemas"]["NextCursor"];
        };
        readonly BenchDetail: components["schemas"]["Bench"] & {
            readonly sites: readonly components["schemas"]["Site"][];
            /** @description Job currently holding the lock of this bench's server (`null` for Frappe Cloud) */
            readonly running_job: string | null;
        };
        readonly Site: {
            readonly name: string;
            readonly domain: string;
            readonly provider: components["schemas"]["Provider"];
            readonly provider_account: string;
            readonly provider_ref: string;
            readonly bench: string;
            readonly server: string | null;
            readonly status: components["schemas"]["SiteStatus"];
            readonly plan: string | null;
            /** Format: date-time */
            readonly ssl_expiry: string | null;
            readonly db_size_mb: number | null;
            /** Format: date-time */
            readonly last_backup: string | null;
            readonly custom_domains: readonly string[];
            /** @description Provider-level capability set (plan section 4.2); actions come from `playbooks.list` */
            readonly capabilities: readonly components["schemas"]["Capability"][];
        };
        readonly SitePage: {
            readonly items: readonly components["schemas"]["Site"][];
            readonly next_cursor: components["schemas"]["NextCursor"];
        };
        readonly Backup: {
            readonly name: string;
            readonly site: string;
            readonly kind: components["schemas"]["BackupKind"];
            /** @description Storage path or provider reference, never a signed URL */
            readonly location: string;
            readonly size_mb: number;
            /** Format: date-time */
            readonly created_at: string;
            /** Format: date-time */
            readonly last_restore_test: string | null;
            readonly restore_test_ok: boolean | null;
        };
        readonly SiteDetail: components["schemas"]["Site"] & {
            readonly bench_info: components["schemas"]["Bench"];
            /** @description Most recent first */
            readonly backups: readonly components["schemas"]["Backup"][];
            readonly running_job: string | null;
        };
        /** @enum {string} */
        readonly TopologyNodeType: "provider" | "server" | "bench" | "site";
        readonly TopologyNode: {
            /** @description `<type>:<ref>`, unique in the graph */
            readonly id: string;
            readonly type: components["schemas"]["TopologyNodeType"];
            /** @description Document name (Provider Account, Server, Bench or Site) */
            readonly ref: string;
            /** @description Display name: Server.hostname, Bench.title, Site.domain, Provider Account label */
            readonly label: string;
            /** @description Unified status for servers and sites; `null` for providers and benches */
            readonly status: string | null;
            readonly provider: components["schemas"]["Provider"];
            readonly has_running_job: boolean;
        };
        readonly TopologyEdge: {
            readonly id: string;
            readonly source: string;
            readonly target: string;
        };
        readonly Topology: {
            readonly nodes: readonly components["schemas"]["TopologyNode"][];
            readonly edges: readonly components["schemas"]["TopologyEdge"][];
            /** Format: date-time */
            readonly generated_at: string;
        };
        readonly ServerStatusCounts: {
            readonly Provisioning: number;
            readonly Active: number;
            readonly Degraded: number;
            readonly Down: number;
            readonly Archived: number;
        };
        readonly SiteStatusCounts: {
            readonly Pending: number;
            readonly Active: number;
            readonly Maintenance: number;
            readonly Suspended: number;
            readonly Broken: number;
            readonly Archived: number;
        };
        readonly OverviewSummary: {
            readonly servers: {
                readonly total: number;
                readonly by_status: components["schemas"]["ServerStatusCounts"];
            };
            readonly sites: {
                readonly total: number;
                readonly by_status: components["schemas"]["SiteStatusCounts"];
            };
            readonly jobs: {
                readonly queued: number;
                readonly running: number;
                readonly success_24h: number;
                readonly failed_24h: number;
            };
            readonly alerts: {
                /** @description All unresolved alerts (firing + acknowledged) */
                readonly unresolved: number;
                readonly info: number;
                readonly warning: number;
                readonly critical: number;
            };
            readonly running_jobs: readonly components["schemas"]["Job"][];
            readonly recent_alerts: readonly components["schemas"]["Alert"][];
            /** Format: date-time */
            readonly generated_at: string;
        };
        readonly MetricPoint: {
            /** Format: date-time */
            readonly ts: string;
            /** @description `null` marks a gap (no reading) */
            readonly value: number | null;
        };
        readonly MetricSeries: {
            readonly server: string;
            readonly metric: components["schemas"]["MetricName"];
            readonly resolution: components["schemas"]["Resolution"];
            /** Format: date-time */
            readonly from: string;
            /** Format: date-time */
            readonly to: string;
            readonly points: readonly components["schemas"]["MetricPoint"][];
        };
        readonly Playbook: {
            /** @description e.g. `site.migrate` */
            readonly key: string;
            readonly title: string;
            readonly description: string;
            /** @description The existing document a job targets. Creation playbooks target the parent (`Provider Account` for `server.provision`, `Bench` for `site.create`). */
            readonly target_doctype: components["schemas"]["TargetDoctype"];
            /** @description Doctype of the document the job creates (`Server`, `Site`), else `null`. The UI renders a "create" form from `params_schema` when set. */
            readonly creates: components["schemas"]["TargetDoctype"] | null;
            readonly risk: components["schemas"]["Risk"];
            readonly required_capability: components["schemas"]["Capability"] | null;
            /** @description JSON Schema (draft 2020-12) for `params`. The UI renders the form from it. */
            readonly params_schema: {
                readonly [key: string]: unknown;
            };
        };
        readonly PlaybookList: {
            readonly items: readonly components["schemas"]["Playbook"][];
        };
        readonly Job: {
            readonly name: string;
            readonly playbook: string;
            readonly playbook_title: string;
            readonly target_doctype: components["schemas"]["TargetDoctype"];
            readonly target_name: string;
            /** @description Masked; secrets never appear */
            readonly params: {
                readonly [key: string]: unknown;
            };
            readonly status: components["schemas"]["JobStatus"];
            readonly progress: number;
            readonly steps_done: number;
            /** @description 0 while unknown */
            readonly steps_total: number;
            /** @description User id, or `scheduler` */
            readonly triggered_by: string;
            readonly bulk_operation: string | null;
            readonly retry_of: string | null;
            /** @description The document a creation playbook produced (`server.provision` -> Server, `site.create` -> Site). `null` until the job succeeds and for all other playbooks. */
            readonly created: components["schemas"]["TargetRef"] | null;
            /** @description `jobs.cancel` was called; the status flips to `Cancelled` when the worker observes it */
            readonly cancel_requested: boolean;
            /** Format: date-time */
            readonly created_at: string;
            /** Format: date-time */
            readonly started_at: string | null;
            /** Format: date-time */
            readonly ended_at: string | null;
            /** @description Short masked failure reason */
            readonly error: string | null;
        };
        readonly JobStep: {
            readonly idx: number;
            readonly title: string;
            readonly status: components["schemas"]["StepStatus"];
            /** @description Masked, may be truncated to the last 64 KB */
            readonly output: string;
            /** Format: date-time */
            readonly started_at: string | null;
            /** Format: date-time */
            readonly ended_at: string | null;
        };
        readonly JobDetail: components["schemas"]["Job"] & {
            readonly steps: readonly components["schemas"]["JobStep"][];
        };
        readonly JobPage: {
            readonly items: readonly components["schemas"]["Job"][];
            readonly next_cursor: components["schemas"]["NextCursor"];
        };
        readonly JobEnvelope: {
            readonly job: components["schemas"]["Job"];
        };
        readonly JobRunRequest: {
            readonly playbook: string;
            readonly target_doctype: components["schemas"]["TargetDoctype"];
            readonly target_name: string;
            /** @default {} */
            readonly params: {
                readonly [key: string]: unknown;
            };
            /** @description Must equal `target_name` for high-risk playbooks */
            readonly confirm?: string;
        };
        readonly BulkOperation: {
            readonly name: string;
            readonly playbook: string;
            readonly playbook_title: string;
            readonly status: components["schemas"]["BulkStatus"];
            readonly phase: components["schemas"]["BulkPhase"];
            readonly failure_policy: components["schemas"]["FailurePolicy"];
            readonly batch_size: number;
            readonly canary_target: components["schemas"]["TargetRef"];
            /** @description Number of targets including the canary */
            readonly total: number;
            /** @description Targets in a terminal state */
            readonly done: number;
            readonly failed: number;
            /** @description 0 = canary */
            readonly current_batch: number;
            readonly batches_total: number;
            readonly triggered_by: string;
            /** Format: date-time */
            readonly created_at: string;
            /** Format: date-time */
            readonly started_at: string | null;
            /** Format: date-time */
            readonly ended_at: string | null;
        };
        readonly BulkTarget: {
            readonly target_doctype: components["schemas"]["TargetDoctype"];
            readonly target_name: string;
            readonly status: components["schemas"]["BulkTargetStatus"];
            readonly job: string | null;
            /** @description 0 = canary */
            readonly batch: number;
        };
        readonly BulkOperationDetail: components["schemas"]["BulkOperation"] & {
            readonly targets: readonly components["schemas"]["BulkTarget"][];
        };
        readonly BulkEnvelope: {
            readonly bulk: components["schemas"]["BulkOperation"];
        };
        readonly BulkCreateRequest: {
            readonly playbook: string;
            readonly targets: readonly components["schemas"]["TargetRef"][];
            /** @description Must be one of `targets` */
            readonly canary_target: components["schemas"]["TargetRef"];
            /** @default 5 */
            readonly batch_size: number;
            /** @default halt */
            readonly failure_policy: components["schemas"]["FailurePolicy"];
            /** @default {} */
            readonly params: {
                readonly [key: string]: unknown;
            };
            /** @description For high-risk playbooks: must equal `"<playbook key>:<number of targets>"`, e.g. `site.restore:3` */
            readonly confirm?: string;
        };
        readonly Alert: {
            readonly name: string;
            readonly rule: string;
            readonly rule_title: string;
            readonly kind: components["schemas"]["AlertRuleKind"];
            readonly severity: components["schemas"]["Severity"];
            readonly status: components["schemas"]["AlertStatus"];
            readonly target: components["schemas"]["TargetRef"];
            /** @description Metric name, or `null` for non-metric alerts (heartbeat, drift, contract) */
            readonly metric: string | null;
            readonly value: number | null;
            readonly message: string;
            /** Format: date-time */
            readonly fired_at: string;
            readonly acknowledged_by: string | null;
            /** Format: date-time */
            readonly acknowledged_at: string | null;
            /** Format: date-time */
            readonly resolved_at: string | null;
        };
        readonly AlertPage: {
            readonly items: readonly components["schemas"]["Alert"][];
            readonly next_cursor: components["schemas"]["NextCursor"];
        };
        readonly AlertEnvelope: {
            readonly alert: components["schemas"]["Alert"];
        };
        /** @description Body of `alert_rules.create`. Only `metric` rules can be created; the built-in kinds exist from install. */
        readonly AlertRuleInput: {
            readonly title: string;
            /**
             * @default metric
             * @constant
             */
            readonly kind: "metric";
            /**
             * @default Server
             * @constant
             */
            readonly target_doctype: "Server";
            readonly metric: components["schemas"]["MetricName"];
            readonly operator: components["schemas"]["Operator"];
            readonly threshold: number;
            readonly for_minutes: number;
            readonly severity: components["schemas"]["Severity"];
            readonly channels: readonly components["schemas"]["AlertChannel"][];
            /** @default true */
            readonly enabled: boolean;
        };
        /**
         * @description Field usage per `kind` (enforced by the `allOf` conditions below):
         *
         *     | kind | target_doctype | metric | operator | threshold | for_minutes | builtin |
         *     |---|---|---|---|---|---|---|
         *     | metric | Server | required | required | required | required (0 = immediate) | false |
         *     | heartbeat | Server | null | null | null | minutes without heartbeat | true |
         *     | ssl_expiry | Site | null | null | days before expiry | null | true |
         *     | drift | Provider Account | null | null | null | null | true |
         *     | contract | Provider Account | null | null | null | null | true |
         *
         *     Editable through `alert_rules.update`: `title`, `severity`, `channels`, `enabled` for every
         *     kind; `metric`, `operator`, `threshold`, `for_minutes` for `metric`; `for_minutes` for
         *     `heartbeat`; `threshold` for `ssl_expiry`. Anything else -> `400 validation_error`.
         *     Built-in rules cannot be created or deleted (`409 invalid_state`).
         */
        readonly AlertRule: {
            readonly name: string;
            readonly title: string;
            readonly kind: components["schemas"]["AlertRuleKind"];
            /** @enum {string} */
            readonly target_doctype: "Server" | "Site" | "Provider Account";
            readonly metric: components["schemas"]["MetricName"] | null;
            readonly operator: components["schemas"]["Operator"] | null;
            readonly threshold: number | null;
            readonly for_minutes: number | null;
            readonly severity: components["schemas"]["Severity"];
            readonly channels: readonly components["schemas"]["AlertChannel"][];
            readonly enabled: boolean;
            /** @description Created on install; cannot be deleted */
            readonly builtin: boolean;
            /** Format: date-time */
            readonly modified_at: string;
        } & (unknown & unknown & unknown & unknown);
        /** @description Omitted fields keep their value. Fields that do not apply to the rule's `kind` (see `AlertRule`) are rejected with `400 validation_error`. */
        readonly AlertRuleUpdate: {
            readonly rule: string;
            readonly title?: string;
            readonly metric?: components["schemas"]["MetricName"];
            readonly operator?: components["schemas"]["Operator"];
            readonly threshold?: number;
            readonly for_minutes?: number;
            readonly severity?: components["schemas"]["Severity"];
            readonly channels?: readonly components["schemas"]["AlertChannel"][];
            readonly enabled?: boolean;
        };
        readonly AlertRulePage: {
            readonly items: readonly components["schemas"]["AlertRule"][];
            readonly next_cursor: components["schemas"]["NextCursor"];
        };
        readonly AlertRuleEnvelope: {
            readonly rule: components["schemas"]["AlertRule"];
        };
        readonly AuditEntry: {
            readonly name: string;
            /** Format: date-time */
            readonly ts: string;
            readonly user: string;
            /** @description e.g. `jobs.run:site.migrate`, `alerts.ack`, `alert_rules.update` */
            readonly action: string;
            readonly target: components["schemas"]["TargetRef"] | null;
            /** @description SHA-256 of the canonical params JSON; params themselves are never stored here */
            readonly params_hash: string;
            readonly job: string | null;
            readonly result: components["schemas"]["AuditResult"];
        };
        readonly AuditPage: {
            readonly items: readonly components["schemas"]["AuditEntry"][];
            readonly next_cursor: components["schemas"]["NextCursor"];
        };
        readonly SearchResult: {
            readonly type: components["schemas"]["SearchResultType"];
            /** @description Document name or playbook key */
            readonly id: string;
            /** @description Display name: Server.hostname, Bench.title, Site.domain, playbook title, job title, alert rule title */
            readonly title: string;
            readonly subtitle: string | null;
            readonly status: string | null;
            readonly provider: components["schemas"]["Provider"] | null;
        };
        readonly SearchResults: {
            readonly items: readonly components["schemas"]["SearchResult"][];
        };
    };
    responses: {
        /**
         * @description Invalid `Authorization: token` header (Frappe `AuthenticationError`, framework shape). A missing
         *     or expired session cookie does **not** produce 401; see `Forbidden`.
         */
        readonly Unauthorized: {
            headers: {
                readonly [name: string]: unknown;
            };
            content: {
                /**
                 * @example {
                 *       "exception": "frappe.exceptions.AuthenticationError",
                 *       "exc_type": "AuthenticationError"
                 *     }
                 */
                readonly "application/json": components["schemas"]["FrappeFrameworkError"];
            };
        };
        /**
         * @description Two distinct cases share this status:
         *     - **Re-authenticate**: body has no `error` key (Frappe framework shape, `exc_type: PermissionError`).
         *       The caller is Guest because there is no session or the `sid` cookie is expired or invalid.
         *     - **Permission denied**: body is the `error` envelope with `code: permission_denied`; the user is
         *       logged in but the role lacks the right.
         */
        readonly Forbidden: {
            headers: {
                readonly [name: string]: unknown;
            };
            content: {
                readonly "application/json": components["schemas"]["ErrorResponse"] | components["schemas"]["FrappeFrameworkError"];
            };
        };
        /** @description Too many requests; retry after the number of seconds in `Retry-After` */
        readonly RateLimited: {
            headers: {
                readonly "Retry-After"?: number;
                readonly [name: string]: unknown;
            };
            content: {
                /**
                 * @example {
                 *       "error": {
                 *         "code": "rate_limited",
                 *         "message": "Too many requests",
                 *         "details": {
                 *           "retry_after": 30
                 *         }
                 *       }
                 *     }
                 */
                readonly "application/json": components["schemas"]["ErrorResponse"];
            };
        };
        /** @description Target does not exist */
        readonly NotFound: {
            headers: {
                readonly [name: string]: unknown;
            };
            content: {
                /**
                 * @example {
                 *       "error": {
                 *         "code": "not_found",
                 *         "message": "Server SRV-9999 not found",
                 *         "details": {
                 *           "doctype": "Server",
                 *           "name": "SRV-9999"
                 *         }
                 *       }
                 *     }
                 */
                readonly "application/json": components["schemas"]["ErrorResponse"];
            };
        };
        /** @description Invalid parameters or body */
        readonly ValidationError: {
            headers: {
                readonly [name: string]: unknown;
            };
            content: {
                /**
                 * @example {
                 *       "error": {
                 *         "code": "validation_error",
                 *         "message": "params.apps must be an array",
                 *         "details": {
                 *           "field": "params.apps"
                 *         }
                 *       }
                 *     }
                 */
                readonly "application/json": components["schemas"]["ErrorResponse"];
            };
        };
        /**
         * @description Invalid input, or a high-risk playbook without the right `confirm`: the target name for
         *     `jobs.run`, `"<playbook key>:<target count>"` for `bulk.create`. `details.expected` always
         *     carries the exact string to type.
         */
        readonly ValidationOrConfirmation: {
            headers: {
                readonly [name: string]: unknown;
            };
            content: {
                readonly "application/json": components["schemas"]["ErrorResponse"];
            };
        };
        /** @description The target's provider does not support the required capability */
        readonly CapabilityMissing: {
            headers: {
                readonly [name: string]: unknown;
            };
            content: {
                /**
                 * @example {
                 *       "error": {
                 *         "code": "capability_missing",
                 *         "message": "Provider frappe_cloud lacks capability service_control",
                 *         "details": {
                 *           "capability": "service_control",
                 *           "provider": "frappe_cloud"
                 *         }
                 *       }
                 *     }
                 */
                readonly "application/json": components["schemas"]["ErrorResponse"];
            };
        };
        /** @description The entity is not in a state that allows this action */
        readonly InvalidState: {
            headers: {
                readonly [name: string]: unknown;
            };
            content: {
                /**
                 * @example {
                 *       "error": {
                 *         "code": "invalid_state",
                 *         "message": "Job JOB-00042 is already Success",
                 *         "details": {
                 *           "status": "Success"
                 *         }
                 *       }
                 *     }
                 */
                readonly "application/json": components["schemas"]["ErrorResponse"];
            };
        };
    };
    parameters: {
        readonly limit: number;
        /** @description Opaque cursor from a previous page's `next_cursor`. */
        readonly cursor: string;
    };
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    readonly overview_summary: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description Overview summary */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["OverviewSummary"];
                };
            };
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly inventory_topology: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description Topology graph */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["Topology"];
                };
            };
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly servers_list: {
        readonly parameters: {
            readonly query?: {
                readonly status?: components["schemas"]["ServerStatus"];
                readonly provider_account?: string;
                readonly role?: components["schemas"]["ServerRole"];
                readonly region?: string;
                readonly limit?: components["parameters"]["limit"];
                /** @description Opaque cursor from a previous page's `next_cursor`. */
                readonly cursor?: components["parameters"]["cursor"];
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description Page of servers */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["ServerPage"];
                };
            };
            readonly 400: components["responses"]["ValidationError"];
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly servers_get: {
        readonly parameters: {
            readonly query: {
                readonly server: string;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description Server detail */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["ServerDetail"];
                };
            };
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 404: components["responses"]["NotFound"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly sites_list: {
        readonly parameters: {
            readonly query?: {
                readonly status?: components["schemas"]["SiteStatus"];
                readonly provider_account?: string;
                readonly bench?: string;
                readonly server?: string;
                readonly limit?: components["parameters"]["limit"];
                /** @description Opaque cursor from a previous page's `next_cursor`. */
                readonly cursor?: components["parameters"]["cursor"];
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description Page of sites */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["SitePage"];
                };
            };
            readonly 400: components["responses"]["ValidationError"];
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly sites_get: {
        readonly parameters: {
            readonly query: {
                readonly site: string;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description Site detail */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["SiteDetail"];
                };
            };
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 404: components["responses"]["NotFound"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly benches_list: {
        readonly parameters: {
            readonly query?: {
                readonly provider_account?: string;
                readonly server?: string;
                readonly limit?: components["parameters"]["limit"];
                /** @description Opaque cursor from a previous page's `next_cursor`. */
                readonly cursor?: components["parameters"]["cursor"];
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description Page of benches */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["BenchPage"];
                };
            };
            readonly 400: components["responses"]["ValidationError"];
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly benches_get: {
        readonly parameters: {
            readonly query: {
                readonly bench: string;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description Bench detail */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["BenchDetail"];
                };
            };
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 404: components["responses"]["NotFound"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly metrics_series: {
        readonly parameters: {
            readonly query: {
                readonly server: string;
                readonly metric: components["schemas"]["MetricName"];
                readonly from: string;
                readonly to: string;
                /** @description Defaults to the coarsest resolution that keeps the series under 1,000 points. */
                readonly resolution?: components["schemas"]["Resolution"];
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description Metric series */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["MetricSeries"];
                };
            };
            readonly 400: components["responses"]["ValidationError"];
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 404: components["responses"]["NotFound"];
            readonly 409: components["responses"]["CapabilityMissing"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly playbooks_list: {
        readonly parameters: {
            readonly query?: {
                readonly target_doctype?: components["schemas"]["TargetDoctype"];
                /** @description When given, only playbooks whose `required_capability` this target supports are returned. */
                readonly target_name?: string;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description Playbooks (not paginated; the catalogue is small) */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["PlaybookList"];
                };
            };
            readonly 400: components["responses"]["ValidationError"];
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 404: components["responses"]["NotFound"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly jobs_run: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody: {
            readonly content: {
                readonly "application/json": components["schemas"]["JobRunRequest"];
            };
        };
        readonly responses: {
            /** @description The queued job */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["JobEnvelope"];
                };
            };
            readonly 400: components["responses"]["ValidationOrConfirmation"];
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 404: components["responses"]["NotFound"];
            readonly 409: components["responses"]["CapabilityMissing"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly jobs_cancel: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody: {
            readonly content: {
                readonly "application/json": components["schemas"]["JobRef"];
            };
        };
        readonly responses: {
            /** @description The job after the cancel request (status `Cancelled`, or still `Running` until the worker observes the flag) */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["JobEnvelope"];
                };
            };
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 404: components["responses"]["NotFound"];
            readonly 409: components["responses"]["InvalidState"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly jobs_retry: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody: {
            readonly content: {
                readonly "application/json": components["schemas"]["JobRef"];
            };
        };
        readonly responses: {
            /** @description The new job (`retry_of` points at the original) */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["JobEnvelope"];
                };
            };
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 404: components["responses"]["NotFound"];
            readonly 409: components["responses"]["InvalidState"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly jobs_list: {
        readonly parameters: {
            readonly query?: {
                readonly status?: components["schemas"]["JobStatus"];
                readonly playbook?: string;
                readonly target_doctype?: components["schemas"]["TargetDoctype"];
                readonly target_name?: string;
                readonly bulk_operation?: string;
                readonly limit?: components["parameters"]["limit"];
                /** @description Opaque cursor from a previous page's `next_cursor`. */
                readonly cursor?: components["parameters"]["cursor"];
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description Page of jobs (without steps) */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["JobPage"];
                };
            };
            readonly 400: components["responses"]["ValidationError"];
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly jobs_get: {
        readonly parameters: {
            readonly query: {
                readonly job: string;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description Job detail */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["JobDetail"];
                };
            };
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 404: components["responses"]["NotFound"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly bulk_create: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody: {
            readonly content: {
                readonly "application/json": components["schemas"]["BulkCreateRequest"];
            };
        };
        readonly responses: {
            /** @description The created bulk operation */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["BulkEnvelope"];
                };
            };
            readonly 400: components["responses"]["ValidationOrConfirmation"];
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 404: components["responses"]["NotFound"];
            readonly 409: components["responses"]["CapabilityMissing"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly bulk_pause: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody: {
            readonly content: {
                readonly "application/json": components["schemas"]["BulkRef"];
            };
        };
        readonly responses: {
            /** @description Bulk operation (status `Paused` once the current batch completes) */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["BulkEnvelope"];
                };
            };
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 404: components["responses"]["NotFound"];
            readonly 409: components["responses"]["InvalidState"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly bulk_resume: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody: {
            readonly content: {
                readonly "application/json": components["schemas"]["BulkRef"];
            };
        };
        readonly responses: {
            /** @description Bulk operation */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["BulkEnvelope"];
                };
            };
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 404: components["responses"]["NotFound"];
            readonly 409: components["responses"]["InvalidState"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly bulk_cancel: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody: {
            readonly content: {
                readonly "application/json": components["schemas"]["BulkRef"];
            };
        };
        readonly responses: {
            /** @description Bulk operation (status `Cancelled` once the current target completes) */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["BulkEnvelope"];
                };
            };
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 404: components["responses"]["NotFound"];
            readonly 409: components["responses"]["InvalidState"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly bulk_get: {
        readonly parameters: {
            readonly query: {
                readonly bulk: string;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description Bulk operation detail */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["BulkOperationDetail"];
                };
            };
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 404: components["responses"]["NotFound"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly alerts_list: {
        readonly parameters: {
            readonly query?: {
                readonly status?: components["schemas"]["AlertStatus"];
                readonly severity?: components["schemas"]["Severity"];
                readonly target_doctype?: components["schemas"]["TargetDoctype"];
                readonly target_name?: string;
                readonly limit?: components["parameters"]["limit"];
                /** @description Opaque cursor from a previous page's `next_cursor`. */
                readonly cursor?: components["parameters"]["cursor"];
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description Page of alerts */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["AlertPage"];
                };
            };
            readonly 400: components["responses"]["ValidationError"];
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly alerts_ack: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody: {
            readonly content: {
                readonly "application/json": {
                    readonly alert: string;
                };
            };
        };
        readonly responses: {
            /** @description The acknowledged alert */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["AlertEnvelope"];
                };
            };
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 404: components["responses"]["NotFound"];
            readonly 409: components["responses"]["InvalidState"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly alert_rules_list: {
        readonly parameters: {
            readonly query?: {
                readonly limit?: components["parameters"]["limit"];
                /** @description Opaque cursor from a previous page's `next_cursor`. */
                readonly cursor?: components["parameters"]["cursor"];
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description Page of alert rules */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["AlertRulePage"];
                };
            };
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly alert_rules_get: {
        readonly parameters: {
            readonly query: {
                readonly rule: string;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description Alert rule */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["AlertRule"];
                };
            };
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 404: components["responses"]["NotFound"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly alert_rules_create: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody: {
            readonly content: {
                readonly "application/json": components["schemas"]["AlertRuleInput"];
            };
        };
        readonly responses: {
            /** @description Created rule */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["AlertRuleEnvelope"];
                };
            };
            readonly 400: components["responses"]["ValidationError"];
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly alert_rules_update: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody: {
            readonly content: {
                readonly "application/json": components["schemas"]["AlertRuleUpdate"];
            };
        };
        readonly responses: {
            /** @description Updated rule */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["AlertRuleEnvelope"];
                };
            };
            readonly 400: components["responses"]["ValidationError"];
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 404: components["responses"]["NotFound"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly alert_rules_delete: {
        readonly parameters: {
            readonly query?: never;
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody: {
            readonly content: {
                readonly "application/json": {
                    readonly rule: string;
                };
            };
        };
        readonly responses: {
            /** @description Deleted */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": {
                        readonly rule: string;
                        /** @constant */
                        readonly deleted: true;
                    };
                };
            };
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 404: components["responses"]["NotFound"];
            readonly 409: components["responses"]["InvalidState"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly audit_list: {
        readonly parameters: {
            readonly query?: {
                readonly user?: string;
                readonly action?: string;
                readonly target_doctype?: components["schemas"]["TargetDoctype"];
                readonly target_name?: string;
                readonly from?: string;
                readonly to?: string;
                readonly limit?: components["parameters"]["limit"];
                /** @description Opaque cursor from a previous page's `next_cursor`. */
                readonly cursor?: components["parameters"]["cursor"];
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description Page of audit entries */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["AuditPage"];
                };
            };
            readonly 400: components["responses"]["ValidationError"];
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
    readonly search_query: {
        readonly parameters: {
            readonly query: {
                readonly q: string;
                readonly limit?: number;
            };
            readonly header?: never;
            readonly path?: never;
            readonly cookie?: never;
        };
        readonly requestBody?: never;
        readonly responses: {
            /** @description Ranked results */
            readonly 200: {
                headers: {
                    readonly [name: string]: unknown;
                };
                content: {
                    readonly "application/json": components["schemas"]["SearchResults"];
                };
            };
            readonly 400: components["responses"]["ValidationError"];
            readonly 401: components["responses"]["Unauthorized"];
            readonly 403: components["responses"]["Forbidden"];
            readonly 429: components["responses"]["RateLimited"];
        };
    };
}
