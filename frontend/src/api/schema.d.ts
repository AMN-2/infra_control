/* eslint-disable */
// GENERATED from contracts/openapi.yaml by scripts/gen-api.mjs. Do not edit.

export interface paths {
    "/api/method/infra_control.api.overview.summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Counts by status, running jobs, firing alerts */
        get: operations["overview_summary"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.inventory.topology": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Nodes and edges for providers, servers, benches and sites */
        get: operations["inventory_topology"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.servers.list": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List servers */
        get: operations["servers_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.servers.get": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Server detail with capabilities, benches and latest metrics */
        get: operations["servers_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.sites.list": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List sites */
        get: operations["sites_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.sites.get": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Site detail with capabilities, bench and recent backups */
        get: operations["sites_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.benches.list": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List benches (Frappe Cloud benches have `server` = null) */
        get: operations["benches_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.benches.get": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Bench detail with its sites and capabilities */
        get: operations["benches_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.metrics.series": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Time series for one metric of one server */
        get: operations["metrics_series"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.playbooks.list": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Playbooks applicable to a target type, filtered by the target's capabilities */
        get: operations["playbooks_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.jobs.run": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Validate, audit, create an Infra Job and enqueue it */
        post: operations["jobs_run"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.jobs.cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel a queued or running job */
        post: operations["jobs_cancel"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.jobs.retry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create a new job linked to a failed one, resuming from its first failed step */
        post: operations["jobs_retry"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.jobs.list": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List jobs, newest first */
        get: operations["jobs_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.jobs.get": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Job with its steps and masked output */
        get: operations["jobs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.bulk.create": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create and start a bulk operation (backup, canary, batches) */
        post: operations["bulk_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.bulk.pause": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Pause after the current batch finishes */
        post: operations["bulk_pause"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.bulk.resume": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Resume a paused or halted bulk operation with the remaining targets */
        post: operations["bulk_resume"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.bulk.cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Cancel a bulk operation; stops after the current target finishes
         * @description The target currently running completes (its job is not interrupted); every remaining target
         *     becomes `Skipped` and the bulk operation ends in status `Cancelled`. Allowed from `Queued`,
         *     `Running`, `Paused` and `Halted`; otherwise `409 invalid_state`.
         */
        post: operations["bulk_cancel"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.bulk.get": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Bulk operation with per-target progress */
        get: operations["bulk_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.bulk.list": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List bulk operations, newest first (summary rows, no targets) */
        get: operations["bulk_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.alerts.list": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List alerts, firing first then newest */
        get: operations["alerts_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.alerts.ack": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Acknowledge a firing alert */
        post: operations["alerts_ack"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.alert_rules.list": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List alert rules */
        get: operations["alert_rules_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.alert_rules.get": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** One alert rule */
        get: operations["alert_rules_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.alert_rules.create": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create an alert rule (Infra Admin) */
        post: operations["alert_rules_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.alert_rules.update": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Update an alert rule (Infra Admin); omitted fields keep their value */
        post: operations["alert_rules_update"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.alert_rules.delete": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Delete a metric alert rule (Infra Admin); its historical alerts are kept. Built-in rules -> 409 invalid_state */
        post: operations["alert_rules_delete"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.git.connections": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Configured Git connections (tokens never returned) */
        get: operations["git_connections"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.git.connect": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Verify a GitHub access token and store it as a connection (Infra Admin) */
        post: operations["git_connect"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.git.disconnect": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Delete a Git connection (Infra Admin) */
        post: operations["git_disconnect"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.git.repos": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Repositories the connection can see, newest pushed first */
        get: operations["git_repos"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.git.refs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Branches and tags of a repository (the "version" picker) */
        get: operations["git_refs"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.providers.accounts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Provider accounts (tokens never returned) */
        get: operations["providers_accounts"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.providers.options": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Regions and plans (sizes with specs and price) a server can be provisioned with; cached one hour */
        get: operations["providers_options"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.console.ticket": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** One-time ticket (60 s) carrying a fresh CA-signed SSH certificate for one server (Infra Admin; audited) */
        post: operations["console_ticket"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.console.sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Console sessions (who, which server, when, how it ended), newest first */
        get: operations["console_sessions"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.console.transcript": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** What happened in one console session (last 200 KB of the terminal transcript) */
        get: operations["console_transcript"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.audit.list": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Paginated immutable audit log, newest first */
        get: operations["audit_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/method/infra_control.api.search.query": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Command palette search across servers, sites, benches, playbooks, jobs and alerts */
        get: operations["search_query"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** @enum {string} */
        ErrorCode: "validation_error" | "permission_denied" | "not_found" | "confirmation_required" | "capability_missing" | "invalid_state" | "invalid_cursor" | "rate_limited" | "provider_error" | "internal_error";
        Error: {
            code: components["schemas"]["ErrorCode"];
            message: string;
            /** @description Machine-readable context; keys depend on `code`. */
            details: {
                [key: string]: unknown;
            };
        };
        ErrorResponse: {
            error: components["schemas"]["Error"];
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
        FrappeFrameworkError: {
            /** @enum {string} */
            exc_type: "AuthenticationError" | "PermissionError" | "CSRFTokenError";
            exception?: string;
            /** @description JSON-encoded list of JSON-encoded message objects (Frappe format) */
            _server_messages?: string;
        } & {
            [key: string]: unknown;
        };
        /** @enum {string} */
        Provider: "digitalocean" | "frappe_cloud";
        /** @enum {string} */
        Capability: "site" | "bench" | "server" | "ssh" | "snapshot" | "service_control" | "metrics" | "custom_playbook" | "managed_backup" | "managed_update";
        /** @enum {string} */
        ServerStatus: "Provisioning" | "Active" | "Degraded" | "Down" | "Archived";
        /** @enum {string} */
        SiteStatus: "Pending" | "Active" | "Maintenance" | "Suspended" | "Broken" | "Archived";
        /** @enum {string} */
        JobStatus: "Queued" | "Running" | "Success" | "Failed" | "Cancelled";
        /** @enum {string} */
        StepStatus: "Queued" | "Running" | "Success" | "Failed" | "Cancelled" | "Skipped";
        /** @enum {string} */
        BulkStatus: "Queued" | "Running" | "Paused" | "Halted" | "Success" | "Failed" | "Cancelled";
        /** @enum {string} */
        BulkPhase: "backup" | "canary" | "batches" | "done";
        /** @enum {string} */
        BulkTargetStatus: "Pending" | "Running" | "Success" | "Failed" | "Skipped";
        /** @enum {string} */
        AlertStatus: "firing" | "acknowledged" | "resolved";
        /** @enum {string} */
        Severity: "info" | "warning" | "critical";
        /** @enum {string} */
        Risk: "low" | "medium" | "high";
        /** @enum {string} */
        TargetDoctype: "Server" | "Site" | "Bench" | "Provider Account";
        /**
         * @description `metric`: threshold on a server metric (user-created). `heartbeat`: no server heartbeat for
         *     `for_minutes`. `ssl_expiry`: a site certificate expires within `threshold` days. `drift`:
         *     inventory sync found a difference. `contract`: the daily Press API contract test failed.
         *     Only `metric` rules can be created or deleted; the other kinds exist as built-in rules.
         * @enum {string}
         */
        AlertRuleKind: "metric" | "heartbeat" | "ssl_expiry" | "drift" | "contract";
        /** @enum {string} */
        ServerRole: "app" | "db" | "proxy" | "all";
        /** @enum {string} */
        MetricName: "cpu" | "ram" | "disk" | "load1" | "queue_backlog";
        /** @enum {string} */
        Resolution: "1m" | "1h" | "1d";
        /** @enum {string} */
        FailurePolicy: "halt" | "continue";
        /** @enum {string} */
        Operator: "gt" | "gte" | "lt" | "lte" | "eq";
        /** @enum {string} */
        AlertChannel: "telegram" | "email";
        /** @enum {string} */
        BackupKind: "db" | "files" | "snapshot";
        /** @enum {string} */
        AuditResult: "success" | "failed" | "denied";
        /** @enum {string} */
        SearchResultType: "server" | "site" | "bench" | "playbook" | "job" | "alert";
        TargetRef: {
            target_doctype: components["schemas"]["TargetDoctype"];
            target_name: string;
        };
        JobRef: {
            job: string;
        };
        BulkRef: {
            bulk: string;
        };
        /** @description Pass as `cursor` to fetch the next page; `null` when there is none. */
        NextCursor: string | null;
        InstalledApp: {
            app: string;
            version: string | null;
            branch: string | null;
        };
        Server: {
            /** @description Stable id (naming series), e.g. `SRV-0001` */
            name: string;
            /** @description Display name (the droplet name); used as the topology label and the search title */
            hostname: string;
            provider: components["schemas"]["Provider"];
            provider_account: string;
            /** @description Droplet id */
            provider_ref: string;
            public_ip: string | null;
            private_ip: string | null;
            role: components["schemas"]["ServerRole"];
            region: string;
            size: string;
            tags: string[];
            status: components["schemas"]["ServerStatus"];
            /** Format: date-time */
            last_heartbeat: string | null;
            /** @description Provider-level capability set (plan section 4.2); actions come from `playbooks.list` */
            capabilities: components["schemas"]["Capability"][];
            bench_count: number;
            site_count: number;
        };
        ServerPage: {
            items: components["schemas"]["Server"][];
            next_cursor: components["schemas"]["NextCursor"];
        };
        MetricSnapshot: {
            /** Format: date-time */
            ts: string;
            /** @description percent */
            cpu: number;
            /** @description percent */
            ram: number;
            /** @description percent */
            disk: number;
            load1: number;
            queue_backlog: number;
        };
        ServerDetail: components["schemas"]["Server"] & {
            benches: components["schemas"]["Bench"][];
            latest_metrics: components["schemas"]["MetricSnapshot"] | null;
            /** @description Name of the job currently holding this server's lock */
            running_job: string | null;
        };
        Bench: {
            name: string;
            /** @description Display name (bench directory name or Press release group title) */
            title: string;
            provider: components["schemas"]["Provider"];
            provider_account: string;
            provider_ref: string;
            /** @description `null` for Frappe Cloud benches */
            server: string | null;
            path: string | null;
            frappe_version: string | null;
            apps: components["schemas"]["InstalledApp"][];
            site_count: number;
            /** @description Provider-level capability set (plan section 4.2); actions come from `playbooks.list` */
            capabilities: components["schemas"]["Capability"][];
        };
        BenchPage: {
            items: components["schemas"]["Bench"][];
            next_cursor: components["schemas"]["NextCursor"];
        };
        BenchDetail: components["schemas"]["Bench"] & {
            sites: components["schemas"]["Site"][];
            /** @description Job currently holding the lock of this bench's server (`null` for Frappe Cloud) */
            running_job: string | null;
        };
        Site: {
            name: string;
            domain: string;
            provider: components["schemas"]["Provider"];
            provider_account: string;
            provider_ref: string;
            bench: string;
            server: string | null;
            status: components["schemas"]["SiteStatus"];
            plan: string | null;
            /** Format: date-time */
            ssl_expiry: string | null;
            db_size_mb: number | null;
            /** Format: date-time */
            last_backup: string | null;
            custom_domains: string[];
            /** @description Provider-level capability set (plan section 4.2); actions come from `playbooks.list` */
            capabilities: components["schemas"]["Capability"][];
        };
        SitePage: {
            items: components["schemas"]["Site"][];
            next_cursor: components["schemas"]["NextCursor"];
        };
        Backup: {
            name: string;
            site: string;
            kind: components["schemas"]["BackupKind"];
            /** @description Storage path or provider reference, never a signed URL */
            location: string;
            size_mb: number;
            /** Format: date-time */
            created_at: string;
            /** Format: date-time */
            last_restore_test: string | null;
            restore_test_ok: boolean | null;
        };
        SiteDetail: components["schemas"]["Site"] & {
            bench_info: components["schemas"]["Bench"];
            /** @description Most recent first */
            backups: components["schemas"]["Backup"][];
            running_job: string | null;
        };
        /** @enum {string} */
        TopologyNodeType: "provider" | "server" | "bench" | "site";
        TopologyNode: {
            /** @description `<type>:<ref>`, unique in the graph */
            id: string;
            type: components["schemas"]["TopologyNodeType"];
            /** @description Document name (Provider Account, Server, Bench or Site) */
            ref: string;
            /** @description Display name: Server.hostname, Bench.title, Site.domain, Provider Account label */
            label: string;
            /** @description Unified status for servers and sites; `null` for providers and benches */
            status: string | null;
            provider: components["schemas"]["Provider"];
            has_running_job: boolean;
        };
        TopologyEdge: {
            id: string;
            source: string;
            target: string;
        };
        Topology: {
            nodes: components["schemas"]["TopologyNode"][];
            edges: components["schemas"]["TopologyEdge"][];
            /** Format: date-time */
            generated_at: string;
        };
        ServerStatusCounts: {
            Provisioning: number;
            Active: number;
            Degraded: number;
            Down: number;
            Archived: number;
        };
        SiteStatusCounts: {
            Pending: number;
            Active: number;
            Maintenance: number;
            Suspended: number;
            Broken: number;
            Archived: number;
        };
        OverviewSummary: {
            servers: {
                total: number;
                by_status: components["schemas"]["ServerStatusCounts"];
            };
            sites: {
                total: number;
                by_status: components["schemas"]["SiteStatusCounts"];
            };
            jobs: {
                queued: number;
                running: number;
                success_24h: number;
                failed_24h: number;
            };
            alerts: {
                /** @description All unresolved alerts (firing + acknowledged) */
                unresolved: number;
                info: number;
                warning: number;
                critical: number;
            };
            running_jobs: components["schemas"]["Job"][];
            recent_alerts: components["schemas"]["Alert"][];
            /** Format: date-time */
            generated_at: string;
        };
        MetricPoint: {
            /** Format: date-time */
            ts: string;
            /** @description `null` marks a gap (no reading) */
            value: number | null;
        };
        MetricSeries: {
            server: string;
            metric: components["schemas"]["MetricName"];
            resolution: components["schemas"]["Resolution"];
            /** Format: date-time */
            from: string;
            /** Format: date-time */
            to: string;
            points: components["schemas"]["MetricPoint"][];
        };
        Playbook: {
            /** @description e.g. `site.migrate` */
            key: string;
            title: string;
            description: string;
            /** @description The existing document a job targets. Creation playbooks target the parent (`Provider Account` for `server.provision`, `Bench` for `site.create`). */
            target_doctype: components["schemas"]["TargetDoctype"];
            /** @description Doctype of the document the job creates (`Server`, `Site`), else `null`. The UI renders a "create" form from `params_schema` when set. */
            creates: components["schemas"]["TargetDoctype"] | null;
            risk: components["schemas"]["Risk"];
            required_capability: components["schemas"]["Capability"] | null;
            /** @description JSON Schema (draft 2020-12) for `params`. The UI renders the form from it. */
            params_schema: {
                [key: string]: unknown;
            };
        };
        PlaybookList: {
            items: components["schemas"]["Playbook"][];
        };
        Job: {
            name: string;
            playbook: string;
            playbook_title: string;
            target_doctype: components["schemas"]["TargetDoctype"];
            target_name: string;
            /** @description Masked; secrets never appear */
            params: {
                [key: string]: unknown;
            };
            status: components["schemas"]["JobStatus"];
            progress: number;
            steps_done: number;
            /** @description 0 while unknown */
            steps_total: number;
            /** @description User id, or `scheduler` */
            triggered_by: string;
            bulk_operation: string | null;
            retry_of: string | null;
            /** @description The document a creation playbook produced (`server.provision` -> Server, `site.create` -> Site). `null` until the job succeeds and for all other playbooks. */
            created: components["schemas"]["TargetRef"] | null;
            /** @description `jobs.cancel` was called; the status flips to `Cancelled` when the worker observes it */
            cancel_requested: boolean;
            /** Format: date-time */
            created_at: string;
            /** Format: date-time */
            started_at: string | null;
            /** Format: date-time */
            ended_at: string | null;
            /** @description Short masked failure reason */
            error: string | null;
        };
        JobStep: {
            idx: number;
            title: string;
            status: components["schemas"]["StepStatus"];
            /** @description Masked, may be truncated to the last 64 KB */
            output: string;
            /** Format: date-time */
            started_at: string | null;
            /** Format: date-time */
            ended_at: string | null;
        };
        JobDetail: components["schemas"]["Job"] & {
            steps: components["schemas"]["JobStep"][];
        };
        JobPage: {
            items: components["schemas"]["Job"][];
            next_cursor: components["schemas"]["NextCursor"];
        };
        JobEnvelope: {
            job: components["schemas"]["Job"];
        };
        JobRunRequest: {
            playbook: string;
            target_doctype: components["schemas"]["TargetDoctype"];
            target_name: string;
            /** @default {} */
            params: {
                [key: string]: unknown;
            };
            /** @description Must equal `target_name` for high-risk playbooks */
            confirm?: string;
        };
        BulkOperation: {
            name: string;
            playbook: string;
            playbook_title: string;
            status: components["schemas"]["BulkStatus"];
            phase: components["schemas"]["BulkPhase"];
            failure_policy: components["schemas"]["FailurePolicy"];
            batch_size: number;
            canary_target: components["schemas"]["TargetRef"];
            /** @description Number of targets including the canary */
            total: number;
            /** @description Targets in a terminal state */
            done: number;
            failed: number;
            /** @description 0 = canary */
            current_batch: number;
            batches_total: number;
            triggered_by: string;
            /** Format: date-time */
            created_at: string;
            /** Format: date-time */
            started_at: string | null;
            /** Format: date-time */
            ended_at: string | null;
        };
        BulkTarget: {
            target_doctype: components["schemas"]["TargetDoctype"];
            target_name: string;
            status: components["schemas"]["BulkTargetStatus"];
            job: string | null;
            /** @description 0 = canary */
            batch: number;
        };
        BulkOperationDetail: components["schemas"]["BulkOperation"] & {
            targets: components["schemas"]["BulkTarget"][];
        };
        BulkEnvelope: {
            bulk: components["schemas"]["BulkOperation"];
        };
        BulkPage: {
            items: components["schemas"]["BulkOperation"][];
            next_cursor: components["schemas"]["NextCursor"];
        };
        BulkCreateRequest: {
            playbook: string;
            targets: components["schemas"]["TargetRef"][];
            /** @description Must be one of `targets` */
            canary_target: components["schemas"]["TargetRef"];
            /** @default 5 */
            batch_size: number;
            /** @default halt */
            failure_policy: components["schemas"]["FailurePolicy"];
            /** @default {} */
            params: {
                [key: string]: unknown;
            };
            /** @description For high-risk playbooks: must equal `"<playbook key>:<number of targets>"`, e.g. `site.restore:3` */
            confirm?: string;
        };
        Alert: {
            name: string;
            rule: string;
            rule_title: string;
            kind: components["schemas"]["AlertRuleKind"];
            severity: components["schemas"]["Severity"];
            status: components["schemas"]["AlertStatus"];
            target: components["schemas"]["TargetRef"];
            /** @description Metric name, or `null` for non-metric alerts (heartbeat, drift, contract) */
            metric: string | null;
            value: number | null;
            message: string;
            /** Format: date-time */
            fired_at: string;
            acknowledged_by: string | null;
            /** Format: date-time */
            acknowledged_at: string | null;
            /** Format: date-time */
            resolved_at: string | null;
        };
        AlertPage: {
            items: components["schemas"]["Alert"][];
            next_cursor: components["schemas"]["NextCursor"];
        };
        AlertEnvelope: {
            alert: components["schemas"]["Alert"];
        };
        /** @description Body of `alert_rules.create`. Only `metric` rules can be created; the built-in kinds exist from install. */
        AlertRuleInput: {
            title: string;
            /**
             * @default metric
             * @constant
             */
            kind: "metric";
            /**
             * @default Server
             * @constant
             */
            target_doctype: "Server";
            metric: components["schemas"]["MetricName"];
            operator: components["schemas"]["Operator"];
            threshold: number;
            for_minutes: number;
            severity: components["schemas"]["Severity"];
            channels: components["schemas"]["AlertChannel"][];
            /** @default true */
            enabled: boolean;
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
        AlertRule: {
            name: string;
            title: string;
            kind: components["schemas"]["AlertRuleKind"];
            /** @enum {string} */
            target_doctype: "Server" | "Site" | "Provider Account";
            metric: components["schemas"]["MetricName"] | null;
            operator: components["schemas"]["Operator"] | null;
            threshold: number | null;
            for_minutes: number | null;
            severity: components["schemas"]["Severity"];
            channels: components["schemas"]["AlertChannel"][];
            enabled: boolean;
            /** @description Created on install; cannot be deleted */
            builtin: boolean;
            /** Format: date-time */
            modified_at: string;
        } & (unknown & unknown & unknown & unknown);
        /** @description Omitted fields keep their value. Fields that do not apply to the rule's `kind` (see `AlertRule`) are rejected with `400 validation_error`. */
        AlertRuleUpdate: {
            rule: string;
            title?: string;
            metric?: components["schemas"]["MetricName"];
            operator?: components["schemas"]["Operator"];
            threshold?: number;
            for_minutes?: number;
            severity?: components["schemas"]["Severity"];
            channels?: components["schemas"]["AlertChannel"][];
            enabled?: boolean;
        };
        AlertRulePage: {
            items: components["schemas"]["AlertRule"][];
            next_cursor: components["schemas"]["NextCursor"];
        };
        AlertRuleEnvelope: {
            rule: components["schemas"]["AlertRule"];
        };
        GitConnection: {
            name: string;
            label: string;
            /** @enum {string} */
            provider: "github";
            enabled: boolean;
            login: string | null;
            /** @description User or Organization */
            account_type: string | null;
            scopes: string[];
            /** Format: date-time */
            verified_at: string | null;
        };
        GitConnectionList: {
            items: components["schemas"]["GitConnection"][];
        };
        GitRepo: {
            full_name: string;
            name: string;
            owner: string;
            private: boolean;
            default_branch: string;
            /** Format: uri */
            clone_url: string;
            description: string | null;
            /** Format: date-time */
            pushed_at: string | null;
        };
        GitRepoPage: {
            items: components["schemas"]["GitRepo"][];
            next_page: number | null;
        };
        GitRef: {
            name: string;
            /** @enum {string} */
            kind: "branch" | "tag";
            sha: string;
        };
        GitRefList: {
            repo: components["schemas"]["GitRepo"];
            items: components["schemas"]["GitRef"][];
        };
        ProviderAccountSummary: {
            name: string;
            label: string;
            provider: components["schemas"]["Provider"];
            enabled: boolean;
            is_staging: boolean;
        };
        ProviderAccountList: {
            items: components["schemas"]["ProviderAccountSummary"][];
        };
        ProvisionRegion: {
            slug: string;
            name: string;
            /** @description Size slugs offered in the region */
            sizes: string[];
        };
        ProvisionSize: {
            slug: string;
            /** @enum {string} */
            family: "basic" | "general" | "cpu" | "memory" | "storage" | "other";
            description: string;
            vcpus: number;
            memory_mb: number;
            disk_gb: number;
            transfer_tb: number;
            /** @description USD */
            price_monthly: number;
            /** @description USD */
            price_hourly: number;
            regions: string[];
        };
        ProvisionCatalogue: {
            account: string;
            provider: components["schemas"]["Provider"];
            regions: components["schemas"]["ProvisionRegion"][];
            sizes: components["schemas"]["ProvisionSize"][];
            defaults: {
                region: string;
                size: string;
                image: string;
            };
        };
        ConsoleTicket: {
            /** @description Single use; 60 s */
            ticket: string;
            /** @description WebSocket path on the app origin, e.g. /console/ws */
            path: string;
            expires_in: number;
            /** @description Id of the session's transcript */
            session: string;
            server: string;
            hostname: string;
            /** @description SSH user on the server */
            user: string;
            /** @description ssh-keygen validity, e.g. +10m */
            certificate_valid_for: string;
        };
        ConsoleSession: {
            session: string;
            server: string;
            hostname: string;
            /** @description Operator who opened it */
            by: string;
            /** Format: date-time */
            started_at: string | null;
            /** Format: date-time */
            ended_at: string | null;
            bytes: number;
            /** @enum {string} */
            status: "open" | "closed";
            /** @description client closed | ssh exited | idle timeout | maximum session length */
            reason: string | null;
        };
        ConsoleSessionList: {
            items: components["schemas"]["ConsoleSession"][];
        };
        ConsoleTranscript: {
            session: string;
            server: string;
            hostname: string;
            by: string;
            /** Format: date-time */
            started_at: string | null;
            /** Format: date-time */
            ended_at: string | null;
            bytes: number;
            /** @enum {string} */
            status: "open" | "closed";
            reason: string | null;
            /** @description Raw terminal bytes as UTF-8 (last 200 KB) */
            transcript: string;
            truncated: boolean;
        };
        AuditEntry: {
            name: string;
            /** Format: date-time */
            ts: string;
            user: string;
            /** @description e.g. `jobs.run:site.migrate`, `alerts.ack`, `alert_rules.update` */
            action: string;
            target: components["schemas"]["TargetRef"] | null;
            /** @description SHA-256 of the canonical params JSON; params themselves are never stored here */
            params_hash: string;
            job: string | null;
            result: components["schemas"]["AuditResult"];
        };
        AuditPage: {
            items: components["schemas"]["AuditEntry"][];
            next_cursor: components["schemas"]["NextCursor"];
        };
        SearchResult: {
            type: components["schemas"]["SearchResultType"];
            /** @description Document name or playbook key */
            id: string;
            /** @description Display name: Server.hostname, Bench.title, Site.domain, playbook title, job title, alert rule title */
            title: string;
            subtitle: string | null;
            status: string | null;
            provider: components["schemas"]["Provider"] | null;
        };
        SearchResults: {
            items: components["schemas"]["SearchResult"][];
        };
    };
    responses: {
        /**
         * @description Invalid `Authorization: token` header (Frappe `AuthenticationError`, framework shape). A missing
         *     or expired session cookie does **not** produce 401; see `Forbidden`.
         */
        Unauthorized: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                /**
                 * @example {
                 *       "exception": "frappe.exceptions.AuthenticationError",
                 *       "exc_type": "AuthenticationError"
                 *     }
                 */
                "application/json": components["schemas"]["FrappeFrameworkError"];
            };
        };
        /**
         * @description Two distinct cases share this status:
         *     - **Re-authenticate**: body has no `error` key (Frappe framework shape, `exc_type: PermissionError`).
         *       The caller is Guest because there is no session or the `sid` cookie is expired or invalid.
         *     - **Permission denied**: body is the `error` envelope with `code: permission_denied`; the user is
         *       logged in but the role lacks the right.
         */
        Forbidden: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["ErrorResponse"] | components["schemas"]["FrappeFrameworkError"];
            };
        };
        /** @description Too many requests; retry after the number of seconds in `Retry-After` */
        RateLimited: {
            headers: {
                "Retry-After"?: number;
                [name: string]: unknown;
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
                "application/json": components["schemas"]["ErrorResponse"];
            };
        };
        /** @description Target does not exist */
        NotFound: {
            headers: {
                [name: string]: unknown;
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
                "application/json": components["schemas"]["ErrorResponse"];
            };
        };
        /** @description Invalid parameters or body */
        ValidationError: {
            headers: {
                [name: string]: unknown;
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
                "application/json": components["schemas"]["ErrorResponse"];
            };
        };
        /**
         * @description Invalid input, or a high-risk playbook without the right `confirm`: the target name for
         *     `jobs.run`, `"<playbook key>:<target count>"` for `bulk.create`. `details.expected` always
         *     carries the exact string to type.
         */
        ValidationOrConfirmation: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["ErrorResponse"];
            };
        };
        /** @description The target's provider does not support the required capability */
        CapabilityMissing: {
            headers: {
                [name: string]: unknown;
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
                "application/json": components["schemas"]["ErrorResponse"];
            };
        };
        /** @description The entity is not in a state that allows this action */
        InvalidState: {
            headers: {
                [name: string]: unknown;
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
                "application/json": components["schemas"]["ErrorResponse"];
            };
        };
    };
    parameters: {
        limit: number;
        /** @description Opaque cursor from a previous page's `next_cursor`. */
        cursor: string;
    };
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    overview_summary: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Overview summary */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OverviewSummary"];
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            429: components["responses"]["RateLimited"];
        };
    };
    inventory_topology: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Topology graph */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Topology"];
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            429: components["responses"]["RateLimited"];
        };
    };
    servers_list: {
        parameters: {
            query?: {
                status?: components["schemas"]["ServerStatus"];
                provider_account?: string;
                role?: components["schemas"]["ServerRole"];
                region?: string;
                limit?: components["parameters"]["limit"];
                /** @description Opaque cursor from a previous page's `next_cursor`. */
                cursor?: components["parameters"]["cursor"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Page of servers */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ServerPage"];
                };
            };
            400: components["responses"]["ValidationError"];
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            429: components["responses"]["RateLimited"];
        };
    };
    servers_get: {
        parameters: {
            query: {
                server: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Server detail */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ServerDetail"];
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            429: components["responses"]["RateLimited"];
        };
    };
    sites_list: {
        parameters: {
            query?: {
                status?: components["schemas"]["SiteStatus"];
                provider_account?: string;
                bench?: string;
                server?: string;
                limit?: components["parameters"]["limit"];
                /** @description Opaque cursor from a previous page's `next_cursor`. */
                cursor?: components["parameters"]["cursor"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Page of sites */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SitePage"];
                };
            };
            400: components["responses"]["ValidationError"];
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            429: components["responses"]["RateLimited"];
        };
    };
    sites_get: {
        parameters: {
            query: {
                site: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Site detail */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SiteDetail"];
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            429: components["responses"]["RateLimited"];
        };
    };
    benches_list: {
        parameters: {
            query?: {
                provider_account?: string;
                server?: string;
                limit?: components["parameters"]["limit"];
                /** @description Opaque cursor from a previous page's `next_cursor`. */
                cursor?: components["parameters"]["cursor"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Page of benches */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BenchPage"];
                };
            };
            400: components["responses"]["ValidationError"];
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            429: components["responses"]["RateLimited"];
        };
    };
    benches_get: {
        parameters: {
            query: {
                bench: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Bench detail */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BenchDetail"];
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            429: components["responses"]["RateLimited"];
        };
    };
    metrics_series: {
        parameters: {
            query: {
                server: string;
                metric: components["schemas"]["MetricName"];
                from: string;
                to: string;
                /** @description Defaults to the coarsest resolution that keeps the series under 1,000 points. */
                resolution?: components["schemas"]["Resolution"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Metric series */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MetricSeries"];
                };
            };
            400: components["responses"]["ValidationError"];
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            409: components["responses"]["CapabilityMissing"];
            429: components["responses"]["RateLimited"];
        };
    };
    playbooks_list: {
        parameters: {
            query?: {
                target_doctype?: components["schemas"]["TargetDoctype"];
                /** @description When given, only playbooks whose `required_capability` this target supports are returned. */
                target_name?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Playbooks (not paginated; the catalogue is small) */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlaybookList"];
                };
            };
            400: components["responses"]["ValidationError"];
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            429: components["responses"]["RateLimited"];
        };
    };
    jobs_run: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["JobRunRequest"];
            };
        };
        responses: {
            /** @description The queued job */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobEnvelope"];
                };
            };
            400: components["responses"]["ValidationOrConfirmation"];
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            409: components["responses"]["CapabilityMissing"];
            429: components["responses"]["RateLimited"];
        };
    };
    jobs_cancel: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["JobRef"];
            };
        };
        responses: {
            /** @description The job after the cancel request (status `Cancelled`, or still `Running` until the worker observes the flag) */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobEnvelope"];
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            409: components["responses"]["InvalidState"];
            429: components["responses"]["RateLimited"];
        };
    };
    jobs_retry: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["JobRef"];
            };
        };
        responses: {
            /** @description The new job (`retry_of` points at the original) */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobEnvelope"];
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            409: components["responses"]["InvalidState"];
            429: components["responses"]["RateLimited"];
        };
    };
    jobs_list: {
        parameters: {
            query?: {
                status?: components["schemas"]["JobStatus"];
                playbook?: string;
                target_doctype?: components["schemas"]["TargetDoctype"];
                target_name?: string;
                bulk_operation?: string;
                limit?: components["parameters"]["limit"];
                /** @description Opaque cursor from a previous page's `next_cursor`. */
                cursor?: components["parameters"]["cursor"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Page of jobs (without steps) */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobPage"];
                };
            };
            400: components["responses"]["ValidationError"];
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            429: components["responses"]["RateLimited"];
        };
    };
    jobs_get: {
        parameters: {
            query: {
                job: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Job detail */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobDetail"];
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            429: components["responses"]["RateLimited"];
        };
    };
    bulk_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BulkCreateRequest"];
            };
        };
        responses: {
            /** @description The created bulk operation */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BulkEnvelope"];
                };
            };
            400: components["responses"]["ValidationOrConfirmation"];
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            409: components["responses"]["CapabilityMissing"];
            429: components["responses"]["RateLimited"];
        };
    };
    bulk_pause: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BulkRef"];
            };
        };
        responses: {
            /** @description Bulk operation (status `Paused` once the current batch completes) */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BulkEnvelope"];
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            409: components["responses"]["InvalidState"];
            429: components["responses"]["RateLimited"];
        };
    };
    bulk_resume: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BulkRef"];
            };
        };
        responses: {
            /** @description Bulk operation */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BulkEnvelope"];
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            409: components["responses"]["InvalidState"];
            429: components["responses"]["RateLimited"];
        };
    };
    bulk_cancel: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BulkRef"];
            };
        };
        responses: {
            /** @description Bulk operation (status `Cancelled` once the current target completes) */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BulkEnvelope"];
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            409: components["responses"]["InvalidState"];
            429: components["responses"]["RateLimited"];
        };
    };
    bulk_get: {
        parameters: {
            query: {
                bulk: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Bulk operation detail */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BulkOperationDetail"];
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            429: components["responses"]["RateLimited"];
        };
    };
    bulk_list: {
        parameters: {
            query?: {
                status?: components["schemas"]["BulkStatus"];
                playbook?: string;
                limit?: components["parameters"]["limit"];
                /** @description Opaque cursor from a previous page's `next_cursor`. */
                cursor?: components["parameters"]["cursor"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Page of bulk operations */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BulkPage"];
                };
            };
            400: components["responses"]["ValidationError"];
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            429: components["responses"]["RateLimited"];
        };
    };
    alerts_list: {
        parameters: {
            query?: {
                status?: components["schemas"]["AlertStatus"];
                severity?: components["schemas"]["Severity"];
                target_doctype?: components["schemas"]["TargetDoctype"];
                target_name?: string;
                limit?: components["parameters"]["limit"];
                /** @description Opaque cursor from a previous page's `next_cursor`. */
                cursor?: components["parameters"]["cursor"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Page of alerts */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AlertPage"];
                };
            };
            400: components["responses"]["ValidationError"];
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            429: components["responses"]["RateLimited"];
        };
    };
    alerts_ack: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    alert: string;
                };
            };
        };
        responses: {
            /** @description The acknowledged alert */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AlertEnvelope"];
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            409: components["responses"]["InvalidState"];
            429: components["responses"]["RateLimited"];
        };
    };
    alert_rules_list: {
        parameters: {
            query?: {
                limit?: components["parameters"]["limit"];
                /** @description Opaque cursor from a previous page's `next_cursor`. */
                cursor?: components["parameters"]["cursor"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Page of alert rules */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AlertRulePage"];
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            429: components["responses"]["RateLimited"];
        };
    };
    alert_rules_get: {
        parameters: {
            query: {
                rule: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Alert rule */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AlertRule"];
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            429: components["responses"]["RateLimited"];
        };
    };
    alert_rules_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AlertRuleInput"];
            };
        };
        responses: {
            /** @description Created rule */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AlertRuleEnvelope"];
                };
            };
            400: components["responses"]["ValidationError"];
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            429: components["responses"]["RateLimited"];
        };
    };
    alert_rules_update: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AlertRuleUpdate"];
            };
        };
        responses: {
            /** @description Updated rule */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AlertRuleEnvelope"];
                };
            };
            400: components["responses"]["ValidationError"];
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            429: components["responses"]["RateLimited"];
        };
    };
    alert_rules_delete: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    rule: string;
                };
            };
        };
        responses: {
            /** @description Deleted */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        rule: string;
                        /** @constant */
                        deleted: true;
                    };
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            409: components["responses"]["InvalidState"];
            429: components["responses"]["RateLimited"];
        };
    };
    git_connections: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Connections */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GitConnectionList"];
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            429: components["responses"]["RateLimited"];
        };
    };
    git_connect: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    /** @description Stable id, e.g. GH-SMARTCHOICE; an existing label replaces its token */
                    label: string;
                    /** Format: password */
                    token: string;
                };
            };
        };
        responses: {
            /** @description The verified connection */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        connection: components["schemas"]["GitConnection"];
                    };
                };
            };
            400: components["responses"]["ValidationError"];
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            429: components["responses"]["RateLimited"];
        };
    };
    git_disconnect: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    connection: string;
                };
            };
        };
        responses: {
            /** @description Deleted */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        connection: string;
                        /** @constant */
                        deleted: true;
                    };
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            429: components["responses"]["RateLimited"];
        };
    };
    git_repos: {
        parameters: {
            query: {
                connection: string;
                query?: string;
                page?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Page of repositories */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GitRepoPage"];
                };
            };
            400: components["responses"]["ValidationError"];
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            429: components["responses"]["RateLimited"];
        };
    };
    git_refs: {
        parameters: {
            query: {
                connection: string;
                repo: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Repository and its refs */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GitRefList"];
                };
            };
            400: components["responses"]["ValidationError"];
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            429: components["responses"]["RateLimited"];
        };
    };
    providers_accounts: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Accounts */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProviderAccountList"];
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            429: components["responses"]["RateLimited"];
        };
    };
    providers_options: {
        parameters: {
            query: {
                account: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Provisioning catalogue */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProvisionCatalogue"];
                };
            };
            400: components["responses"]["ValidationError"];
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            409: components["responses"]["CapabilityMissing"];
            429: components["responses"]["RateLimited"];
        };
    };
    console_ticket: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    server: string;
                };
            };
        };
        responses: {
            /** @description Ticket; connect a WebSocket to `<path>?ticket=<ticket>` on the app origin */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConsoleTicket"];
                };
            };
            400: components["responses"]["ValidationError"];
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            409: components["responses"]["CapabilityMissing"];
            429: components["responses"]["RateLimited"];
        };
    };
    console_sessions: {
        parameters: {
            query?: {
                server?: string;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Sessions */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConsoleSessionList"];
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            429: components["responses"]["RateLimited"];
        };
    };
    console_transcript: {
        parameters: {
            query: {
                session: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Session with its transcript */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConsoleTranscript"];
                };
            };
            400: components["responses"]["ValidationError"];
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            429: components["responses"]["RateLimited"];
        };
    };
    audit_list: {
        parameters: {
            query?: {
                user?: string;
                action?: string;
                target_doctype?: components["schemas"]["TargetDoctype"];
                target_name?: string;
                from?: string;
                to?: string;
                limit?: components["parameters"]["limit"];
                /** @description Opaque cursor from a previous page's `next_cursor`. */
                cursor?: components["parameters"]["cursor"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Page of audit entries */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuditPage"];
                };
            };
            400: components["responses"]["ValidationError"];
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            429: components["responses"]["RateLimited"];
        };
    };
    search_query: {
        parameters: {
            query: {
                q: string;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Ranked results */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SearchResults"];
                };
            };
            400: components["responses"]["ValidationError"];
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            429: components["responses"]["RateLimited"];
        };
    };
}
