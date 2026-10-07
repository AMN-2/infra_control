import { createPinia, setActivePinia } from "pinia";
import { mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { nextTick } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { _resetForTests, injectEvent } from "@/realtime";
import { routes } from "@/router";
import { clearToasts, toasts } from "@/design/components";
import type { Playbook } from "@/stores/playbooks";

const GET = vi.fn();
const POST = vi.fn();
vi.mock("@/api/client", () => ({
	api: { GET: (...a: unknown[]) => GET(...a), POST: (...a: unknown[]) => POST(...a) },
}));
vi.mock("motion", () => ({
	animate: (_el: unknown, _kf: unknown, opts?: { onUpdate?: (v: number) => void }) => {
		opts?.onUpdate?.(0);
		return { stop: () => undefined };
	},
}));

const { useSessionStore } = await import("@/stores/session");
const { default: TargetActions } = await import("@/features/jobs/TargetActions.vue");
const { default: RunPlaybookDialog } = await import("@/features/jobs/RunPlaybookDialog.vue");
const { default: ServerDetailView } = await import("@/features/servers/ServerDetailView.vue");
const { default: SiteDetailView } = await import("@/features/sites/SiteDetailView.vue");

const playbook = (key: string, extra: Partial<Playbook> = {}): Playbook => ({
	key,
	title: key,
	description: `${key} description`,
	target_doctype: "Server",
	creates: null,
	risk: "low",
	required_capability: "snapshot",
	params_schema: { type: "object", properties: {} },
	...extra,
});
const server = {
	name: "SRV-0001",
	hostname: "app-01.fra1",
	provider: "digitalocean",
	provider_account: "DO-STAGING",
	provider_ref: "1",
	public_ip: "164.92.10.11",
	private_ip: null,
	role: "all",
	region: "fra1",
	size: "s-4vcpu-8gb",
	tags: ["staging"],
	status: "Active",
	last_heartbeat: "2026-10-07T09:30:40Z",
	capabilities: ["server", "snapshot", "ssh", "site", "bench", "service_control", "metrics"],
	bench_count: 1,
	site_count: 2,
	benches: [
		{
			name: "BENCH-0001",
			title: "v15-prod",
			provider: "digitalocean",
			provider_account: "DO-STAGING",
			provider_ref: "x",
			server: "SRV-0001",
			path: "/home/frappe/v15-prod",
			frappe_version: "15.98.1",
			apps: [{ app: "erpnext", version: "15.80.0", branch: "version-15" }],
			site_count: 2,
			capabilities: ["site"],
		},
	],
	latest_metrics: {
		ts: "2026-10-07T09:30:40Z",
		cpu: 23.5,
		ram: 61.2,
		disk: 91,
		load1: 0.8,
		queue_backlog: 3,
	},
	running_job: null,
};
const site = {
	name: "demo.iq",
	domain: "demo.iq",
	provider: "digitalocean",
	provider_account: "DO-STAGING",
	provider_ref: "SRV-0001:/home/frappe/v15-prod:demo.iq",
	bench: "BENCH-0001",
	server: "SRV-0001",
	status: "Maintenance",
	plan: null,
	ssl_expiry: "2026-12-20T00:00:00Z",
	db_size_mb: 812.4,
	last_backup: "2026-10-07T02:00:11Z",
	custom_domains: ["www.demo.iq"],
	capabilities: ["site"],
	bench_info: server.benches[0],
	backups: [
		{
			name: "BK-1",
			site: "demo.iq",
			kind: "scheduled",
			location: "spaces://bk/demo",
			size_mb: 120,
			created_at: "2026-10-07T02:00:11Z",
			last_restore_test: null,
			restore_test_ok: null,
		},
	],
	running_job: "JOB-00042",
};
const page = (items: unknown[]) => ({ data: { items, next_cursor: null } });

function routeGET(map: Record<string, unknown>) {
	GET.mockImplementation((path: string) => {
		for (const [needle, value] of Object.entries(map))
			if (path.includes(needle)) return Promise.resolve(value);
		return Promise.reject(new Error(`unexpected GET ${path}`));
	});
}
async function settle(n = 4) {
	for (let i = 0; i < n; i++) await nextTick();
}
function admin() {
	window.infra_boot = {
		session_user: "a@x",
		roles: ["Infra Admin", "Infra Operator", "Infra Viewer"],
		site_name: "s",
	};
	useSessionStore().load();
}
async function withRouter(path: string) {
	const router = createRouter({ history: createMemoryHistory("/infra/"), routes });
	await router.push(path);
	await router.isReady();
	return router;
}

beforeEach(() => {
	setActivePinia(createPinia());
	_resetForTests();
	clearToasts();
	GET.mockReset();
	POST.mockReset();
	delete window.infra_boot;
});

describe("TargetActions", () => {
	it("renders only playbooks the target supports and hides creation playbooks", async () => {
		admin();
		routeGET({
			"playbooks.list": page([
				playbook("server.snapshot"),
				playbook("server.reboot", { risk: "high", required_capability: "server" }),
				playbook("server.custom", { required_capability: "custom_playbook" }),
				playbook("server.provision", {
					creates: "Server",
					target_doctype: "Provider Account",
				}),
			]),
		});
		const router = await withRouter("/servers/SRV-0001");
		const w = mount(TargetActions, {
			props: {
				targetDoctype: "Server",
				targetName: "SRV-0001",
				capabilities: ["snapshot", "server"],
			},
			global: { plugins: [router] },
		});
		await settle();
		expect(w.find('[data-testid="action-server.snapshot"]').exists()).toBe(true);
		expect(w.find('[data-testid="action-server.reboot"]').exists()).toBe(true);
		expect(w.find('[data-testid="action-server.custom"]').exists()).toBe(false);
		expect(w.find('[data-testid="action-server.provision"]').exists()).toBe(false);
	});

	it("shows the lock and disables actions while a job runs; viewers see nothing", async () => {
		admin();
		routeGET({ "playbooks.list": page([playbook("server.snapshot")]) });
		const router = await withRouter("/servers/SRV-0001");
		const w = mount(TargetActions, {
			props: {
				targetDoctype: "Server",
				targetName: "SRV-0001",
				capabilities: ["snapshot"],
				runningJob: "JOB-7",
			},
			global: { plugins: [router] },
		});
		await settle();
		expect(w.find('[data-testid="lock-notice"]').text()).toContain("JOB-7");
		expect(
			w.find('[data-testid="action-server.snapshot"]').attributes("disabled")
		).toBeDefined();

		setActivePinia(createPinia());
		window.infra_boot = { session_user: "v@x", roles: ["Infra Viewer"], site_name: "s" };
		useSessionStore().load();
		const viewer = mount(TargetActions, {
			props: { targetDoctype: "Server", targetName: "SRV-0001", capabilities: ["snapshot"] },
			global: { plugins: [router] },
		});
		await settle();
		expect(viewer.find('[data-testid="target-actions"]').exists()).toBe(false);
	});
});

describe("RunPlaybookDialog", () => {
	it("requires the typed target name for high risk and sends confirm with the params", async () => {
		admin();
		const router = await withRouter("/servers/SRV-0001");
		const pushSpy = vi.spyOn(router, "push").mockResolvedValue(undefined);
		POST.mockResolvedValue({
			data: {
				job: {
					name: "JOB-00099",
					status: "Queued",
					progress: 0,
					playbook_title: "Reboot",
				},
			},
		});
		const w = mount(RunPlaybookDialog, {
			props: {
				playbook: playbook("server.reboot", {
					title: "Reboot server",
					risk: "high",
					params_schema: {
						required: ["reason"],
						properties: {
							reason: { type: "string" },
							force: { type: "boolean", default: false },
							mode: { type: "string", enum: ["soft", "hard"], default: "soft" },
							notify: { type: "array", items: { type: "string" } },
						},
					},
				}),
				targetDoctype: "Server",
				targetName: "SRV-0001",
				targetLabel: "app-01.fra1",
				modelValue: true,
			},
			global: { plugins: [router] },
			attachTo: document.body,
		});
		await settle();
		const submit = document.querySelector<HTMLButtonElement>('[data-testid="run-submit"]');
		const confirm = document.querySelector<HTMLInputElement>('[data-testid="confirm-input"]');
		const reason = document.querySelector<HTMLInputElement>("#param-reason");
		const notify = document.querySelector<HTMLInputElement>("#param-notify");
		if (!submit || !confirm || !reason || !notify) throw new Error("dialog did not render");
		expect(submit.disabled).toBe(true);
		reason.value = "kernel update";
		reason.dispatchEvent(new Event("input"));
		notify.value = "ops, oncall";
		notify.dispatchEvent(new Event("input"));
		await settle();
		expect(submit.disabled).toBe(true); // still needs the typed confirmation
		confirm.value = "SRV-0001";
		confirm.dispatchEvent(new Event("input"));
		await settle();
		expect(submit.disabled).toBe(false);
		submit.click();
		await settle(6);
		expect(POST).toHaveBeenCalledTimes(1);
		const [, options] = POST.mock.calls[0] as [string, { body: Record<string, unknown> }];
		expect(options.body).toEqual({
			playbook: "server.reboot",
			target_doctype: "Server",
			target_name: "SRV-0001",
			params: {
				reason: "kernel update",
				force: false,
				mode: "soft",
				notify: ["ops", "oncall"],
			},
			confirm: "SRV-0001",
		});
		expect(toasts.items[0]?.title).toBe("Reboot server queued");
		expect(pushSpy).toHaveBeenCalledWith("/jobs/JOB-00099");
		expect(w.emitted("queued")?.[0]).toEqual(["JOB-00099"]);
		w.unmount();
	});

	it("shows the API error inside the dialog and stays open", async () => {
		admin();
		const router = await withRouter("/servers/SRV-0001");
		const { ApiError } = await import("@/api/errors");
		POST.mockRejectedValue(
			new ApiError(409, { code: "capability_missing", message: "Provider lacks snapshot" })
		);
		mount(RunPlaybookDialog, {
			props: {
				playbook: playbook("server.snapshot", { title: "Snapshot" }),
				targetDoctype: "Server",
				targetName: "SRV-0001",
				modelValue: true,
			},
			global: { plugins: [router] },
			attachTo: document.body,
		});
		await settle();
		document.querySelector<HTMLButtonElement>('[data-testid="run-submit"]')?.click();
		await settle(6);
		expect(document.querySelector('[data-testid="run-error"]')?.textContent).toContain(
			"capability_missing"
		);
		expect(document.querySelector('[data-testid="run-dialog"]')).not.toBeNull();
	});
});

describe("ServerDetailView", () => {
	it("renders header, metrics with thresholds, benches and job history; heartbeat updates in place", async () => {
		admin();
		routeGET({
			"servers.get": { data: server },
			"jobs.list": page([
				{
					name: "JOB-1",
					playbook: "server.snapshot",
					playbook_title: "Snapshot",
					target_doctype: "Server",
					target_name: "SRV-0001",
					params: {},
					status: "Success",
					progress: 100,
					steps_done: 1,
					steps_total: 1,
					triggered_by: "u",
					bulk_operation: null,
					retry_of: null,
					created: null,
					cancel_requested: false,
					created_at: "2026-10-07T09:00:00Z",
					started_at: null,
					ended_at: null,
					error: null,
				},
			]),
			"playbooks.list": page([playbook("server.snapshot")]),
		});
		const router = await withRouter("/servers/SRV-0001");
		const w = mount(ServerDetailView, { global: { plugins: [router] } });
		expect(w.find('[data-testid="server-loading"]').exists()).toBe(true);
		await settle(6);
		expect(w.text()).toContain("app-01.fra1");
		expect(w.find('[data-testid="server-badges"]').text()).toContain("Active");
		const metrics = w.find('[data-testid="server-metrics"]');
		expect(metrics.text()).toContain("91");
		expect(metrics.find(".text-down").exists()).toBe(true); // disk 91 % is critical
		expect(w.text()).toContain("v15-prod");
		expect(w.find('[data-testid="action-server.snapshot"]').exists()).toBe(true);

		injectEvent("infra:server.heartbeat", {
			server: "SRV-0001",
			status: "Degraded",
			cpu: 95,
			ram: 50,
			disk: 60,
			ts: "2026-10-07T09:31:40Z",
		});
		await settle();
		expect(w.find('[data-testid="server-badges"]').text()).toContain("Degraded");
		expect(w.find('[data-testid="server-metrics"]').text()).toContain("95");
	});

	it("shows a not-found error with retry", async () => {
		admin();
		const { ApiError } = await import("@/api/errors");
		GET.mockImplementation((path: string) =>
			path.includes("servers.get")
				? Promise.reject(
						new ApiError(404, { code: "not_found", message: "No such server" })
					)
				: Promise.resolve(page([]))
		);
		const router = await withRouter("/servers/NOPE");
		const w = mount(ServerDetailView, { global: { plugins: [router] } });
		await settle(6);
		expect(w.text()).toContain("Server not found");
		expect(w.find('[data-testid="error-retry"]').exists()).toBe(true);
	});
});

describe("SiteDetailView", () => {
	it("renders facts, domains, backups, lock and the bench tab", async () => {
		admin();
		routeGET({
			"sites.get": { data: site },
			"jobs.list": page([]),
			"playbooks.list": page([
				playbook("site.backup", { target_doctype: "Site", required_capability: "site" }),
			]),
		});
		const router = await withRouter("/sites/demo.iq");
		const w = mount(SiteDetailView, { global: { plugins: [router] } });
		await settle(6);
		expect(w.find('[data-testid="site-badges"]').text()).toContain("Maintenance");
		expect(w.find('[data-testid="site-domains"]').text()).toContain("www.demo.iq");
		expect(w.text()).toContain("BK-1");
		expect(w.text()).toContain("never tested");
		expect(w.find('[data-testid="lock-notice"]').text()).toContain("JOB-00042");
		expect(w.find('[data-testid="action-site.backup"]').attributes("disabled")).toBeDefined();
		await w.find("#tab-bench").trigger("click");
		await settle();
		expect(w.find('[data-testid="site-bench"]').text()).toContain("erpnext 15.80.0");
	});
});
