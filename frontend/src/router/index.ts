import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";
import { installGuards } from "./guards";

declare module "vue-router" {
	interface RouteMeta {
		title: string;
		/** Role required beyond being logged in. */
		requiresRole?: "Infra Admin" | "Infra Operator";
		/** Hidden from navigation and the palette. */
		hidden?: boolean;
		/** Renders without a session (the login page). */
		public?: boolean;
	}
}

/** The SPA is served at /infra (plan §2). Every feature route is lazy-loaded (plan §10.4). */
export const routes: RouteRecordRaw[] = [
	{ path: "/", redirect: "/overview" },
	{
		// In-app login (ADR 0008). Full-page scene; App.vue keeps it outside the shell.
		path: "/login",
		name: "login",
		component: () => import("@/features/login/LoginView.vue"),
		meta: { title: "Sign in", hidden: true, public: true },
	},
	{
		path: "/overview",
		name: "overview",
		component: () => import("@/features/overview/OverviewView.vue"),
		meta: { title: "Overview" },
	},
	{
		path: "/topology",
		name: "topology",
		component: () => import("@/features/topology/TopologyView.vue"),
		meta: { title: "Topology" },
	},
	{
		path: "/servers",
		name: "servers",
		component: () => import("@/features/servers/ServersView.vue"),
		meta: { title: "Servers" },
	},
	{
		path: "/servers/:name",
		name: "server",
		component: () => import("@/features/servers/ServerDetailView.vue"),
		meta: { title: "Server", hidden: true },
	},
	{
		path: "/benches",
		name: "benches",
		component: () => import("@/features/benches/BenchesView.vue"),
		meta: { title: "Benches" },
	},
	{
		path: "/benches/:name",
		name: "bench",
		component: () => import("@/features/benches/BenchDetailView.vue"),
		meta: { title: "Bench", hidden: true },
	},
	{
		path: "/sites",
		name: "sites",
		component: () => import("@/features/sites/SitesView.vue"),
		meta: { title: "Sites" },
	},
	{
		path: "/sites/:name",
		name: "site",
		component: () => import("@/features/sites/SiteDetailView.vue"),
		meta: { title: "Site", hidden: true },
	},
	{
		path: "/tenants",
		name: "tenants",
		component: () => import("@/features/tenants/TenantsView.vue"),
		meta: { title: "Tenants" },
	},
	{
		path: "/tenants/:name",
		name: "tenant",
		component: () => import("@/features/tenants/TenantDetailView.vue"),
		meta: { title: "Tenant", hidden: true },
	},
	{
		path: "/jobs",
		name: "jobs",
		component: () => import("@/features/jobs/JobsView.vue"),
		meta: { title: "Jobs" },
	},
	{
		path: "/jobs/:name",
		name: "job",
		component: () => import("@/features/jobs/JobDetailView.vue"),
		meta: { title: "Job", hidden: true },
	},
	{
		path: "/bulk",
		name: "bulk",
		component: () => import("@/features/bulk/BulkView.vue"),
		meta: { title: "Bulk rollouts" },
	},
	{
		path: "/alerts",
		name: "alerts",
		component: () => import("@/features/alerts/AlertsView.vue"),
		meta: { title: "Alerts" },
	},
	{
		path: "/settings/security",
		name: "settings-security",
		component: () => import("@/features/settings/SecurityView.vue"),
		meta: { title: "Security", requiresRole: "Infra Admin", hidden: true },
	},
	{
		path: "/audit",
		name: "audit",
		component: () => import("@/features/audit/AuditView.vue"),
		meta: { title: "Audit log", hidden: true },
	},
	{
		path: "/settings/github",
		name: "settings-github",
		component: () => import("@/features/settings/GitHubView.vue"),
		meta: { title: "GitHub", requiresRole: "Infra Admin", hidden: true },
	},
	{
		// Living design-system showcase; Infra Admin only (Q-B7).
		path: "/_design",
		name: "design",
		component: () => import("@/features/design/DesignShowcase.vue"),
		meta: { title: "Design system", requiresRole: "Infra Admin", hidden: true },
	},
	{
		path: "/:pathMatch(.*)*",
		name: "not-found",
		component: () => import("@/features/system/NotFoundView.vue"),
		meta: { title: "Not found", hidden: true },
	},
];

export const router = createRouter({
	history: createWebHistory("/infra/"),
	routes,
});
installGuards(router);
