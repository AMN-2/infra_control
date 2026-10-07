import { createPinia, setActivePinia } from "pinia";
import { mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { defineComponent, h, nextTick } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { _resetForTests, injectEvent } from "@/realtime";
import { routes } from "@/router";
import { clearToasts, toasts } from "@/design/components";

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
// xterm needs a real canvas; a stand-in records what the viewer writes.
const written: string[] = [];
vi.mock("@/design/components/IcTerminal.vue", () => ({
	default: defineComponent({
		name: "IcTerminal",
		props: { rows: { type: Number, default: 18 }, initial: { type: String, default: "" } },
		setup(props, { expose }) {
			written.push(`[initial]${props.initial}`);
			expose({
				write: (chunk: string) => {
					written.push(chunk);
				},
				clear: () => undefined,
			});
			return () => h("div", { "data-testid": "terminal" }, props.initial);
		},
	}),
}));

const { useSessionStore } = await import("@/stores/session");
const { default: JobsView } = await import("@/features/jobs/JobsView.vue");
const { default: JobDetailView } = await import("@/features/jobs/JobDetailView.vue");

const job = (name: string, status = "Running", extra: Record<string, unknown> = {}) => ({
	name,
	playbook: "site.migrate",
	playbook_title: "Migrate site",
	target_doctype: "Site",
	target_name: "demo.iq",
	params: { skip_search_index: false },
	status,
	progress: 40,
	steps_done: 2,
	steps_total: 5,
	triggered_by: "ameen@x",
	bulk_operation: null,
	retry_of: null,
	created: null,
	cancel_requested: false,
	created_at: "2026-10-07T09:30:00Z",
	started_at: "2026-10-07T09:30:04Z",
	ended_at: null,
	error: null,
	...extra,
});
const detail = (name: string, status = "Running", extra: Record<string, unknown> = {}) => ({
	...job(name, status, extra),
	steps: [
		{
			idx: 0,
			title: "Acquire lock",
			status: "Success",
			output: "lock acquired",
			started_at: "2026-10-07T09:30:04Z",
			ended_at: "2026-10-07T09:30:04Z",
		},
		{
			idx: 1,
			title: "Backup",
			status: "Success",
			output: "saved 96 MB\n",
			started_at: "2026-10-07T09:30:05Z",
			ended_at: "2026-10-07T09:31:20Z",
		},
		{
			idx: 2,
			title: "bench migrate",
			status: "Running",
			output: "",
			started_at: "2026-10-07T09:31:21Z",
			ended_at: null,
		},
	],
});

async function settle(n = 5) {
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
	written.length = 0;
	delete window.infra_boot;
});

describe("JobsView", () => {
	it("lists running jobs first and pages with the cursor", async () => {
		admin();
		GET.mockResolvedValueOnce({
			data: {
				items: [job("JOB-1", "Success"), job("JOB-2", "Running"), job("JOB-3", "Failed")],
				next_cursor: "c2",
			},
		}).mockResolvedValueOnce({
			data: { items: [job("JOB-0", "Cancelled")], next_cursor: null },
		});
		const router = await withRouter("/jobs");
		const w = mount(JobsView, { global: { plugins: [router] } });
		await settle();
		const names = w.findAll("tbody tr td:first-child").map((td) => td.text());
		expect(names).toEqual(["JOB-2", "JOB-3", "JOB-1"]);
		await w.find('[data-testid="jobs-more"]').trigger("click");
		await settle();
		expect(GET).toHaveBeenCalledTimes(2);
		expect(w.findAll("tbody tr")).toHaveLength(4);
		expect(w.find('[data-testid="jobs-more"]').exists()).toBe(false);
	});
});

describe("JobDetailView", () => {
	it("renders the timeline and seeds the terminal, then streams step and log events", async () => {
		admin();
		GET.mockResolvedValue({ data: detail("JOB-1") });
		const router = await withRouter("/jobs/JOB-1");
		const w = mount(JobDetailView, { global: { plugins: [router] } });
		expect(w.find('[data-testid="job-loading"]').exists()).toBe(true);
		await settle();
		expect(w.find('[data-testid="job-badges"]').text()).toContain("Running");
		expect(w.findAll('[data-testid="timeline"] li')).toHaveLength(3);
		expect(w.find('[data-testid="timeline"] li[data-status="Running"]').text()).toContain(
			"bench migrate"
		);
		expect(written[0]).toContain("── Backup\nsaved 96 MB");
		expect(w.find('[data-testid="job-cancel"]').exists()).toBe(true);
		expect(w.find('[data-testid="job-retry"]').exists()).toBe(false);

		injectEvent("infra:job.log", { job: "JOB-1", idx: 2, chunk: "Migrating demo.iq\n" });
		injectEvent("infra:job.step", {
			job: "JOB-1",
			idx: 2,
			title: "bench migrate",
			status: "Success",
		});
		injectEvent("infra:job.step", {
			job: "JOB-1",
			idx: 3,
			title: "Disable maintenance",
			status: "Running",
		});
		injectEvent("infra:job.updated", { job: "JOB-1", status: "Running", progress: 75 });
		await settle();
		expect(written).toContain("Migrating demo.iq\n");
		expect(w.findAll('[data-testid="timeline"] li')).toHaveLength(4);
		expect(w.find('[data-testid="timeline"] li[data-status="Running"]').text()).toContain(
			"Disable maintenance"
		);
		expect(w.find('[role="progressbar"]').attributes("aria-valuenow")).toBe("75");
		expect(w.find('[data-testid="job-params"]').text()).toContain("skip_search_index");
	});

	it("cancels through the typed confirmation and offers retry on failure", async () => {
		admin();
		GET.mockResolvedValue({ data: detail("JOB-1") });
		POST.mockResolvedValue({
			data: { job: job("JOB-1", "Running", { cancel_requested: true }) },
		});
		const router = await withRouter("/jobs/JOB-1");
		const w = mount(JobDetailView, { global: { plugins: [router] }, attachTo: document.body });
		await settle();
		await w.find('[data-testid="job-cancel"]').trigger("click");
		await settle();
		const input = document.querySelector<HTMLInputElement>('[data-testid="confirm-input"]');
		const submit = document.querySelector<HTMLButtonElement>('[data-testid="confirm-submit"]');
		if (!input || !submit) throw new Error("confirm dialog missing");
		input.value = "JOB-1";
		input.dispatchEvent(new Event("input"));
		await settle();
		submit.click();
		await settle(6);
		expect(POST).toHaveBeenCalledWith("/api/method/infra_control.api.jobs.cancel", {
			body: { job: "JOB-1" },
		});
		expect(toasts.items[0]?.title).toBe("Cancel requested");
		expect(w.find('[data-testid="job-badges"]').text()).toContain("cancel requested");
		w.unmount();

		setActivePinia(createPinia());
		admin();
		GET.mockReset();
		GET.mockResolvedValue({
			data: detail("JOB-9", "Failed", { error: "bench migrate exited 1", progress: 40 }),
		});
		POST.mockReset();
		POST.mockResolvedValue({ data: { job: job("JOB-10", "Queued", { retry_of: "JOB-9" }) } });
		const router2 = await withRouter("/jobs/JOB-9");
		const w2 = mount(JobDetailView, { global: { plugins: [router2] } });
		await settle();
		expect(w2.find('[data-testid="job-error"]').text()).toContain("exited 1");
		await w2.find('[data-testid="job-retry"]').trigger("click");
		await settle(6);
		expect(POST).toHaveBeenCalledWith("/api/method/infra_control.api.jobs.retry", {
			body: { job: "JOB-9" },
		});
		expect(w2.find('[data-testid="job-badges"]').text()).toContain("retried as JOB-10");
		expect(w2.find('[data-testid="job-retry"]').exists()).toBe(false);
	});

	it("hides operator controls from viewers", async () => {
		window.infra_boot = { session_user: "v@x", roles: ["Infra Viewer"], site_name: "s" };
		useSessionStore().load();
		GET.mockResolvedValue({ data: detail("JOB-1") });
		const router = await withRouter("/jobs/JOB-1");
		const w = mount(JobDetailView, { global: { plugins: [router] } });
		await settle();
		expect(w.find('[data-testid="job-cancel"]').exists()).toBe(false);
	});
});
