import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { _resetForTests, injectEvent } from "@/realtime";

const GET = vi.fn();
const POST = vi.fn();
vi.mock("@/api/client", () => ({
	api: { GET: (...a: unknown[]) => GET(...a), POST: (...a: unknown[]) => POST(...a) },
}));

const { useJobsStore } = await import("@/stores/jobs");
const { useInventoryStore } = await import("@/stores/inventory");
const { useAlertsStore } = await import("@/stores/alerts");
const { useSessionStore } = await import("@/stores/session");

const job = (name: string, status = "Running") => ({
	name,
	playbook: "site.migrate",
	playbook_title: "Migrate site",
	target_doctype: "Site",
	target_name: "demo.iq",
	params: {},
	status,
	progress: 0,
	steps_done: 0,
	steps_total: 0,
	triggered_by: "u",
	bulk_operation: null,
	retry_of: null,
	created: null,
	cancel_requested: false,
	created_at: "2026-10-07T09:30:00Z",
	started_at: null,
	ended_at: null,
	error: null,
});

beforeEach(() => {
	setActivePinia(createPinia());
	_resetForTests();
	GET.mockReset();
	POST.mockReset();
});

describe("jobs store", () => {
	it("applies job.updated / job.step / job.log to the list and the detail", async () => {
		GET.mockResolvedValueOnce({ data: { items: [job("JOB-1")], next_cursor: null } });
		GET.mockResolvedValueOnce({
			data: {
				...job("JOB-1"),
				steps: [
					{
						idx: 0,
						title: "Backup",
						status: "Running",
						output: "",
						started_at: null,
						ended_at: null,
					},
				],
			},
		});
		const store = useJobsStore();
		store.subscribe();
		await store.fetchList();
		await store.fetchDetail("JOB-1");
		expect(store.running.map((j) => j.name)).toEqual(["JOB-1"]);

		injectEvent("infra:job.updated", { job: "JOB-1", status: "Running", progress: 50 });
		expect(store.items[0]?.progress).toBe(50);
		expect(store.details["JOB-1"]?.progress).toBe(50);

		injectEvent("infra:job.step", {
			job: "JOB-1",
			idx: 1,
			title: "Migrate",
			status: "Queued",
		});
		injectEvent("infra:job.step", {
			job: "JOB-1",
			idx: 0,
			title: "Backup",
			status: "Success",
		});
		expect(store.details["JOB-1"]?.steps.map((s) => `${s.idx}:${s.status}`)).toEqual([
			"0:Success",
			"1:Queued",
		]);
		expect(store.details["JOB-1"]?.steps_done).toBe(1);

		const chunks: string[] = [];
		store.onLog("JOB-1", (c) => chunks.push(c));
		injectEvent("infra:job.log", { job: "JOB-1", idx: 0, chunk: "line 1\n" });
		injectEvent("infra:job.log", { job: "JOB-1", idx: 0, chunk: "line 2\n" });
		expect(chunks).toEqual(["line 1\n", "line 2\n"]);
		expect(store.logs["JOB-1"]).toBe("line 1\nline 2\n");
		expect(store.details["JOB-1"]?.steps[0]?.output).toBe("line 1\nline 2\n");

		GET.mockResolvedValueOnce({ data: { ...job("JOB-1", "Success"), steps: [] } });
		injectEvent("infra:job.updated", { job: "JOB-1", status: "Success", progress: 100 });
		expect(store.items[0]?.status).toBe("Success");
		await vi.waitFor(() => expect(GET).toHaveBeenCalledTimes(3));
	});

	it("runPlaybook posts the contract body and prepends the job", async () => {
		POST.mockResolvedValueOnce({ data: { job: job("JOB-9", "Queued") } });
		const store = useJobsStore();
		const created = await store.runPlaybook({
			playbook: "site.backup",
			target_doctype: "Site",
			target_name: "demo.iq",
			params: {},
		});
		expect(created?.name).toBe("JOB-9");
		expect(POST).toHaveBeenCalledWith("/api/method/infra_control.api.jobs.run", {
			body: {
				playbook: "site.backup",
				target_doctype: "Site",
				target_name: "demo.iq",
				params: {},
			},
		});
		expect(store.items[0]?.name).toBe("JOB-9");
	});

	it("exposes ApiError state instead of throwing", async () => {
		const { ApiError } = await import("@/api/errors");
		GET.mockRejectedValueOnce(new ApiError(403, { code: "permission_denied", message: "no" }));
		const store = useJobsStore();
		await store.fetchList();
		expect(store.error?.code).toBe("permission_denied");
		expect(store.loading).toBe(false);
	});
});

describe("inventory store", () => {
	it("updates server status from heartbeats and refetches on inventory.changed", async () => {
		const server = {
			name: "SRV-1",
			hostname: "a",
			provider: "digitalocean",
			provider_account: "DO",
			provider_ref: "1",
			public_ip: null,
			private_ip: null,
			role: "all",
			region: "fra1",
			size: "s",
			tags: [],
			status: "Active",
			last_heartbeat: null,
			capabilities: [],
			bench_count: 0,
			site_count: 0,
		};
		GET.mockResolvedValue({ data: { items: [server], next_cursor: null } });
		const store = useInventoryStore();
		store.subscribe();
		await store.fetchServers();
		injectEvent("infra:server.heartbeat", {
			server: "SRV-1",
			status: "Degraded",
			cpu: 90,
			ram: 50,
			disk: 10,
			ts: "2026-10-07T09:30:00Z",
		});
		expect(store.servers[0]?.status).toBe("Degraded");
		expect(store.heartbeats["SRV-1"]?.cpu).toBe(90);
		GET.mockResolvedValue({
			data: { nodes: [], edges: [], generated_at: "2026-10-07T09:30:00Z" },
		});
		injectEvent("infra:inventory.changed", { doctype: "Bench", name: "B", change: "updated" });
		await vi.waitFor(() =>
			expect(GET.mock.calls.some((c) => String(c[0]).endsWith("benches.list"))).toBe(true)
		);
	});
});

describe("alerts store", () => {
	it("acknowledges optimistically and rolls back on failure", async () => {
		const alert = {
			name: "ALERT-1",
			rule: "R",
			rule_title: "r",
			kind: "metric",
			severity: "warning",
			status: "firing",
			target: { target_doctype: "Server", target_name: "SRV-1" },
			metric: "disk",
			value: 90,
			message: "m",
			fired_at: "2026-10-07T09:00:00Z",
			acknowledged_by: null,
			acknowledged_at: null,
			resolved_at: null,
		};
		GET.mockResolvedValueOnce({ data: { items: [alert], next_cursor: null } });
		const store = useAlertsStore();
		await store.fetchList();
		const { ApiError } = await import("@/api/errors");
		POST.mockRejectedValueOnce(new ApiError(409, { code: "invalid_state", message: "x" }));
		const pending = store.acknowledge("ALERT-1", "me");
		expect(store.items[0]?.status).toBe("acknowledged");
		await pending;
		expect(store.items[0]?.status).toBe("firing");
		POST.mockResolvedValueOnce({
			data: { alert: { ...alert, status: "acknowledged", acknowledged_by: "me" } },
		});
		await store.acknowledge("ALERT-1", "me");
		expect(store.items[0]?.acknowledged_by).toBe("me");
		store.subscribe();
		injectEvent("infra:alert.resolved", {
			alert: "ALERT-1",
			rule: "R",
			target: { target_doctype: "Server", target_name: "SRV-1" },
			severity: "warning",
		});
		expect(store.items[0]?.status).toBe("resolved");
	});
});

describe("session store", () => {
	it("reads boot data and role helpers", () => {
		window.infra_boot = {
			session_user: "u@x",
			roles: ["Infra Operator", "Infra Viewer"],
			site_name: "s",
		};
		const s = useSessionStore();
		expect(s.load()).toBe(true);
		expect(s.canOperate).toBe(true);
		expect(s.isAdmin).toBe(false);
		expect(s.site).toBe("s");
		delete window.infra_boot;
	});
});
