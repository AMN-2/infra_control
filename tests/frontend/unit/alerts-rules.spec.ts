import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

const GET = vi.fn();
const POST = vi.fn();
vi.mock("@/api/client", () => ({
	api: { GET: (...a: unknown[]) => GET(...a), POST: (...a: unknown[]) => POST(...a) },
}));

const { useAlertRulesStore } = await import("@/stores/alertRules");
const { describeRule, formFromRule, kindFields, toInput, toUpdate, validate, emptyForm } =
	await import("@/features/alerts/ruleForm");
type AlertRule = import("@/features/alerts/ruleForm").AlertRule;

const metricRule: AlertRule = {
	name: "RULE-0002",
	title: "CPU above 90%",
	kind: "metric",
	target_doctype: "Server",
	metric: "cpu",
	operator: "gt",
	threshold: 90,
	for_minutes: 5,
	severity: "critical",
	channels: ["telegram"],
	enabled: true,
	builtin: false,
	modified_at: "2026-09-01T10:00:00Z",
};
const heartbeat: AlertRule = {
	...metricRule,
	name: "RULE-0001",
	title: "Server heartbeat missing",
	kind: "heartbeat",
	metric: null,
	operator: null,
	threshold: null,
	for_minutes: 3,
	channels: ["telegram", "email"],
	builtin: true,
};

beforeEach(() => {
	setActivePinia(createPinia());
	GET.mockReset();
	POST.mockReset();
});

describe("rule form helpers (B3.2)", () => {
	it("exposes only the fields the contract lets each kind edit", () => {
		expect(kindFields("metric")).toEqual(["metric", "operator", "threshold", "for_minutes"]);
		expect(kindFields("heartbeat")).toEqual(["for_minutes"]);
		expect(kindFields("ssl_expiry")).toEqual(["threshold"]);
		expect(kindFields("drift")).toEqual([]);
		expect(kindFields("contract")).toEqual([]);
	});

	it("validates per kind", () => {
		const form = emptyForm();
		expect(validate("metric", form)).toHaveProperty("title");
		form.title = "x";
		expect(validate("metric", form)).toEqual({});
		form.for_minutes = "2000";
		expect(validate("metric", form)).toHaveProperty("for_minutes");
		form.for_minutes = "0";
		expect(validate("metric", form)).toEqual({});
		expect(validate("heartbeat", form)).toHaveProperty("for_minutes");
		form.channels = [];
		expect(validate("drift", form)).toHaveProperty("channels");
	});

	it("builds a create body for a metric rule and a minimal diff for updates", () => {
		const form = {
			...emptyForm(),
			title: " RAM high ",
			metric: "ram" as const,
			threshold: "80",
		};
		expect(toInput(form)).toEqual({
			title: "RAM high",
			kind: "metric",
			target_doctype: "Server",
			metric: "ram",
			operator: "gt",
			threshold: 80,
			for_minutes: 5,
			severity: "warning",
			channels: ["telegram"],
			enabled: true,
		});
		// Unchanged form → only the key.
		expect(toUpdate(metricRule, formFromRule(metricRule))).toEqual({ rule: "RULE-0002" });
		// Built-in heartbeat: the metric/operator/threshold fields never reach the body.
		const hb = formFromRule(heartbeat);
		hb.for_minutes = "10";
		hb.metric = "disk";
		hb.threshold = "5";
		hb.channels = ["email"];
		expect(toUpdate(heartbeat, hb)).toEqual({
			rule: "RULE-0001",
			for_minutes: 10,
			channels: ["email"],
		});
	});

	it("describes rules in one line", () => {
		expect(describeRule(metricRule)).toBe("CPU above 90% for 5 min");
		expect(describeRule(heartbeat)).toBe("No heartbeat for 3 min");
		expect(
			describeRule({ ...heartbeat, kind: "ssl_expiry", threshold: 14, for_minutes: null })
		).toBe("Certificate expires within 14 days");
	});
});

describe("alert rules store (B3.2)", () => {
	it("lists, creates, toggles optimistically with rollback, and deletes", async () => {
		GET.mockResolvedValueOnce({ data: { items: [heartbeat, metricRule], next_cursor: null } });
		const store = useAlertRulesStore();
		await store.fetchList();
		expect(store.items.map((r) => r.name)).toEqual(["RULE-0001", "RULE-0002"]);

		const created = { ...metricRule, name: "RULE-0009", title: "RAM high" };
		POST.mockResolvedValueOnce({ data: { rule: created } });
		expect(await store.create(toInput({ ...emptyForm(), title: "RAM high" }))).toEqual(
			created
		);
		expect(store.items).toHaveLength(3);
		expect(POST.mock.calls[0]?.[0]).toBe("/api/method/infra_control.api.alert_rules.create");

		const { ApiError } = await import("@/api/errors");
		POST.mockRejectedValueOnce(new ApiError(403, { code: "forbidden", message: "nope" }));
		const pending = store.setEnabled("RULE-0001", false);
		expect(store.items[0]?.enabled).toBe(false);
		await pending;
		expect(store.items[0]?.enabled).toBe(true);
		expect(store.saveError).toBe("nope");

		POST.mockResolvedValueOnce({ data: { rule: { ...heartbeat, enabled: false } } });
		await store.setEnabled("RULE-0001", false);
		expect(store.items[0]?.enabled).toBe(false);
		expect(store.saveError).toBeNull();

		POST.mockResolvedValueOnce({ data: { rule: "RULE-0009", deleted: true } });
		expect(await store.remove("RULE-0009")).toBe(true);
		expect(store.items).toHaveLength(2);
		// The list's own error state is untouched by mutations.
		expect(store.error).toBeNull();
	});
});
