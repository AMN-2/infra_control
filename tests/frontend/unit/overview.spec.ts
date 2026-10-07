import { createPinia, setActivePinia } from "pinia";
import { mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { nextTick } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { _resetForTests, injectEvent } from "@/realtime";
import { routes } from "@/router";
import { relativeTime, secondsSince, shortTime } from "@/lib/time";

const GET = vi.fn();
vi.mock("@/api/client", () => ({
	api: { GET: (...a: unknown[]) => GET(...a), POST: vi.fn() },
}));
// Motion is a visual concern; the view is tested on what it renders.
vi.mock("motion", () => ({
	animate: (_el: unknown, _kf: unknown, opts?: { onUpdate?: (v: number) => void }) => {
		opts?.onUpdate?.(0);
		return { stop: () => undefined };
	},
}));

const { useOverviewStore, HISTORY_MAX } = await import("@/stores/overview");
const { default: OverviewView } = await import("@/features/overview/OverviewView.vue");

function summary(overrides: Record<string, unknown> = {}) {
	return {
		servers: {
			total: 3,
			by_status: { Provisioning: 0, Active: 2, Degraded: 1, Down: 0, Archived: 0 },
		},
		sites: {
			total: 5,
			by_status: {
				Pending: 0,
				Active: 4,
				Maintenance: 1,
				Suspended: 0,
				Broken: 0,
				Archived: 0,
			},
		},
		jobs: { queued: 1, running: 1, success_24h: 12, failed_24h: 1 },
		alerts: { unresolved: 2, info: 0, warning: 1, critical: 1 },
		running_jobs: [
			{
				name: "JOB-00042",
				playbook: "site.migrate",
				playbook_title: "Migrate site",
				target_doctype: "Site",
				target_name: "demo.iq",
				params: {},
				status: "Running",
				progress: 40,
				steps_done: 2,
				steps_total: 5,
				triggered_by: "u@x",
				bulk_operation: null,
				retry_of: null,
				created: null,
				cancel_requested: false,
				created_at: "2026-10-07T09:30:00Z",
				started_at: "2026-10-07T09:30:04Z",
				ended_at: null,
				error: null,
			},
		],
		recent_alerts: [
			{
				name: "ALERT-1",
				rule: "RULE-1",
				rule_title: "Disk above 85%",
				kind: "metric",
				severity: "critical",
				status: "firing",
				target: { target_doctype: "Server", target_name: "SRV-0002" },
				metric: "disk",
				value: 88.4,
				message: "Disk usage 88.4% on SRV-0002",
				fired_at: "2026-10-07T09:12:00Z",
				acknowledged_by: null,
				acknowledged_at: null,
				resolved_at: null,
			},
		],
		generated_at: "2026-10-07T09:31:00Z",
		...overrides,
	};
}

beforeEach(() => {
	setActivePinia(createPinia());
	_resetForTests();
	GET.mockReset();
	vi.useRealTimers();
});

describe("overview store", () => {
	it("keeps a bounded history and exposes trends once two readings exist", async () => {
		const store = useOverviewStore();
		GET.mockResolvedValue({ data: summary() });
		await store.fetch();
		expect(store.trend.servers).toEqual([]);
		await store.fetch();
		expect(store.trend).toEqual({
			servers: [3, 3],
			sites: [5, 5],
			jobs: [2, 2],
			alerts: [2, 2],
		});
		for (let i = 0; i < HISTORY_MAX + 5; i++) await store.fetch();
		expect(store.history).toHaveLength(HISTORY_MAX);
	});

	it("patches a known running job in place and refetches once per burst otherwise", async () => {
		vi.useFakeTimers();
		const store = useOverviewStore();
		GET.mockResolvedValue({ data: summary() });
		await store.fetch();
		store.subscribe();
		injectEvent("infra:job.updated", { job: "JOB-00042", status: "Running", progress: 80 });
		expect(store.summary?.running_jobs[0]?.progress).toBe(80);
		expect(GET).toHaveBeenCalledTimes(1);
		injectEvent("infra:job.updated", { job: "JOB-00099", status: "Queued", progress: 0 });
		injectEvent("infra:job.updated", { job: "JOB-00099", status: "Running", progress: 10 });
		injectEvent("infra:alert.fired", {
			alert: "ALERT-2",
			rule: "RULE-1",
			severity: "warning",
			target_doctype: "Server",
			target_name: "SRV-0001",
			message: "x",
		});
		await vi.advanceTimersByTimeAsync(1100);
		expect(GET).toHaveBeenCalledTimes(2);
	});

	it("surfaces an ApiError and keeps the last summary", async () => {
		const store = useOverviewStore();
		GET.mockResolvedValueOnce({ data: summary() });
		await store.fetch();
		GET.mockRejectedValueOnce(new Error("boom"));
		await store.fetch();
		expect(store.error?.code).toBe("network_error");
		expect(store.summary?.servers.total).toBe(3);
	});
});

describe("OverviewView", () => {
	async function mountView() {
		const router = createRouter({ history: createMemoryHistory("/infra/"), routes });
		await router.push("/overview");
		await router.isReady();
		const w = mount(OverviewView, { global: { plugins: [router] } });
		await nextTick();
		await nextTick();
		return w;
	}

	it("shows skeletons while loading, then the four stats, jobs and alerts", async () => {
		let resolve: (v: unknown) => void = () => undefined;
		GET.mockReturnValue(new Promise((r) => (resolve = r)));
		const w = await mountView();
		expect(w.find('[data-testid="overview-loading"]').exists()).toBe(true);
		resolve({ data: summary() });
		await nextTick();
		await nextTick();
		await nextTick();
		expect(w.find('[data-testid="overview-loading"]').exists()).toBe(false);
		const stats = w.findAll('[data-testid="overview-stats"] [data-testid="stat-value"]');
		expect(stats).toHaveLength(4);
		expect(w.find('[data-testid="stat-servers"]').text()).toContain("2 active · 1 degraded");
		expect(w.find('[data-testid="stat-jobs"]').text()).toContain("1 running · 1 queued");
		expect(w.find('[data-testid="running-jobs"]').text()).toContain("Migrate site");
		expect(w.find('[data-testid="recent-alerts"]').text()).toContain("Disk usage 88.4%");
		expect(w.find('[data-testid="recent-alerts"] .border-s-down').exists()).toBe(true);
	});

	it("renders empty states and an error state with retry", async () => {
		GET.mockResolvedValue({ data: summary({ running_jobs: [], recent_alerts: [] }) });
		const w = await mountView();
		await nextTick();
		expect(w.text()).toContain("Nothing is running");
		expect(w.text()).toContain("No recent alerts");

		// A fresh store: the error state shows only when there is no summary to keep.
		setActivePinia(createPinia());
		GET.mockReset();
		GET.mockRejectedValue(new Error("down"));
		const w2 = await mountView();
		await nextTick();
		await nextTick();
		expect(w2.find('[data-testid="error-retry"]').exists()).toBe(true);
		GET.mockResolvedValue({ data: summary() });
		await w2.find('[data-testid="error-retry"]').trigger("click");
		await nextTick();
		await nextTick();
		expect(w2.find('[data-testid="overview-stats"]').exists()).toBe(true);
	});
});

describe("time helpers", () => {
	const now = Date.parse("2026-10-07T10:00:00Z");
	it("formats relative and short times", () => {
		expect(relativeTime("2026-10-07T09:59:50Z", now)).toBe("just now");
		expect(relativeTime("2026-10-07T09:12:00Z", now)).toBe("48 min ago");
		expect(relativeTime("2026-10-07T07:00:00Z", now)).toBe("3 h ago");
		expect(relativeTime("2026-10-01T10:00:00Z", now)).toBe("6 d ago");
		expect(relativeTime("2026-10-07T10:05:00Z", now)).toBe("in 5 min");
		expect(relativeTime("garbage", now)).toBe("");
		expect(secondsSince("2026-10-07T09:59:30Z", now)).toBe(30);
		expect(secondsSince("garbage", now)).toBeNull();
		expect(shortTime("2026-10-07T09:31:00Z", "en-GB")).toMatch(/\d{2}:\d{2}/);
	});
});
