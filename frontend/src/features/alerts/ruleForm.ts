import type { components } from "@/api/schema";

type S = components["schemas"];
export type AlertRule = S["AlertRule"];
export type AlertRuleKind = S["AlertRuleKind"];
export type AlertRuleInput = S["AlertRuleInput"];
export type AlertRuleUpdate = S["AlertRuleUpdate"];
export type MetricName = S["MetricName"];
export type Operator = S["Operator"];
export type Severity = S["Severity"];
export type AlertChannel = S["AlertChannel"];

export const METRICS: readonly { value: MetricName; label: string; unit: string }[] = [
	{ value: "cpu", label: "CPU", unit: "%" },
	{ value: "ram", label: "RAM", unit: "%" },
	{ value: "disk", label: "Disk", unit: "%" },
	{ value: "load1", label: "Load (1 min)", unit: "" },
	{ value: "queue_backlog", label: "Queue backlog", unit: "jobs" },
];
export const OPERATORS: readonly { value: Operator; label: string }[] = [
	{ value: "gt", label: "above (>)" },
	{ value: "gte", label: "at least (≥)" },
	{ value: "lt", label: "below (<)" },
	{ value: "lte", label: "at most (≤)" },
	{ value: "eq", label: "equal to (=)" },
];
export const SEVERITIES: readonly Severity[] = ["info", "warning", "critical"];
export const CHANNELS: readonly AlertChannel[] = ["telegram", "email"];

/** The rule editor's one model: strings for inputs, converted at the edges. */
export interface RuleForm {
	title: string;
	metric: MetricName;
	operator: Operator;
	threshold: string;
	for_minutes: string;
	severity: Severity;
	channels: AlertChannel[];
	enabled: boolean;
}

export type KindField = "metric" | "operator" | "threshold" | "for_minutes";

/**
 * Which kind-specific fields `alert_rules.update` accepts (contract `AlertRule` description).
 * `title`, `severity`, `channels`, `enabled` are editable for every kind.
 */
export function kindFields(kind: AlertRuleKind): readonly KindField[] {
	switch (kind) {
		case "metric":
			return ["metric", "operator", "threshold", "for_minutes"];
		case "heartbeat":
			return ["for_minutes"];
		case "ssl_expiry":
			return ["threshold"];
		default:
			return [];
	}
}

/** Label and hint for the threshold/for_minutes inputs depend on the kind. */
export function thresholdLabel(kind: AlertRuleKind): string {
	return kind === "ssl_expiry" ? "Days before expiry" : "Threshold";
}
export function forMinutesLabel(kind: AlertRuleKind): string {
	return kind === "heartbeat" ? "Minutes without heartbeat" : "For minutes (0 = immediate)";
}

export function emptyForm(): RuleForm {
	return {
		title: "",
		metric: "cpu",
		operator: "gt",
		threshold: "90",
		for_minutes: "5",
		severity: "warning",
		channels: ["telegram"],
		enabled: true,
	};
}

export function formFromRule(rule: AlertRule): RuleForm {
	return {
		title: rule.title,
		metric: rule.metric ?? "cpu",
		operator: rule.operator ?? "gt",
		threshold: rule.threshold === null ? "" : String(rule.threshold),
		for_minutes: rule.for_minutes === null ? "" : String(rule.for_minutes),
		severity: rule.severity,
		channels: [...rule.channels],
		enabled: rule.enabled,
	};
}

function num(v: string): number | null {
	if (v.trim() === "") return null;
	const n = Number(v);
	return Number.isFinite(n) ? n : null;
}

/** Validation messages per field; an empty map means the form can be submitted. */
export function validate(kind: AlertRuleKind, form: RuleForm): Partial<Record<string, string>> {
	const errors: Partial<Record<string, string>> = {};
	if (!form.title.trim()) errors.title = "Title is required.";
	const fields = kindFields(kind);
	if (fields.includes("threshold")) {
		const t = num(form.threshold);
		if (t === null) errors.threshold = "Enter a number.";
		else if (kind === "ssl_expiry" && t < 1) errors.threshold = "At least 1 day.";
	}
	if (fields.includes("for_minutes")) {
		const m = num(form.for_minutes);
		if (m === null || !Number.isInteger(m)) errors.for_minutes = "Enter a whole number.";
		else if (m < (kind === "heartbeat" ? 1 : 0) || m > 1440)
			errors.for_minutes =
				kind === "heartbeat" ? "Between 1 and 1440." : "Between 0 and 1440.";
	}
	if (!form.channels.length) errors.channels = "Choose at least one channel.";
	return errors;
}

/** Body of `alert_rules.create` (metric rules only). */
export function toInput(form: RuleForm): AlertRuleInput {
	return {
		title: form.title.trim(),
		kind: "metric",
		target_doctype: "Server",
		metric: form.metric,
		operator: form.operator,
		threshold: Number(form.threshold),
		for_minutes: Number(form.for_minutes),
		severity: form.severity,
		channels: [...form.channels],
		enabled: form.enabled,
	};
}

/**
 * Body of `alert_rules.update`: only the changed fields, and only those the kind allows, so a
 * built-in rule never sends a field the API would reject with 400.
 */
export function toUpdate(rule: AlertRule, form: RuleForm): AlertRuleUpdate {
	const body: AlertRuleUpdate = { rule: rule.name };
	const title = form.title.trim();
	if (title !== rule.title) body.title = title;
	if (form.severity !== rule.severity) body.severity = form.severity;
	if (form.enabled !== rule.enabled) body.enabled = form.enabled;
	const channels = CHANNELS.filter((c) => form.channels.includes(c));
	if (channels.join() !== [...rule.channels].sort().join()) body.channels = channels;
	const fields = kindFields(rule.kind);
	if (fields.includes("metric") && form.metric !== rule.metric) body.metric = form.metric;
	if (fields.includes("operator") && form.operator !== rule.operator)
		body.operator = form.operator;
	if (fields.includes("threshold") && Number(form.threshold) !== rule.threshold)
		body.threshold = Number(form.threshold);
	if (fields.includes("for_minutes") && Number(form.for_minutes) !== rule.for_minutes)
		body.for_minutes = Number(form.for_minutes);
	return body;
}

/** One-line human summary of a rule's condition, used in the rules table. */
export function describeRule(rule: AlertRule): string {
	switch (rule.kind) {
		case "metric": {
			const m = METRICS.find((x) => x.value === rule.metric);
			const op = OPERATORS.find((x) => x.value === rule.operator);
			const unit = m?.unit === "%" ? "%" : m?.unit ? ` ${m.unit}` : "";
			const dur = rule.for_minutes ? ` for ${rule.for_minutes} min` : "";
			return `${m?.label ?? rule.metric} ${op?.label.split(" (")[0] ?? rule.operator} ${rule.threshold}${unit}${dur}`;
		}
		case "heartbeat":
			return `No heartbeat for ${rule.for_minutes} min`;
		case "ssl_expiry":
			return `Certificate expires within ${rule.threshold} days`;
		case "drift":
			return "Inventory sync finds a difference";
		case "contract":
			return "Daily Press API contract test fails";
	}
}
