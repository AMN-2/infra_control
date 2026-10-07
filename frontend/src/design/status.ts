/**
 * Status → tone (plan §10.1: green healthy, amber degraded, red down, blue running, identical
 * everywhere). States the plan does not colour are mapped per docs/questions/agent-b.md Q-B5.
 * The enums come from the generated contract types, so a contract change fails `vue-tsc`.
 */
import type { components } from "@/api/schema";

type S = components["schemas"];
export type ServerStatus = S["ServerStatus"];
export type SiteStatus = S["SiteStatus"];
export type JobStatus = S["JobStatus"];
export type StepStatus = S["StepStatus"];
export type BulkStatus = S["BulkStatus"];
export type BulkTargetStatus = S["BulkTargetStatus"];
export type AlertStatus = S["AlertStatus"];
export type Severity = S["Severity"];
export type Provider = S["Provider"];

export type Tone = "healthy" | "degraded" | "down" | "running" | "neutral";

export const serverStatusTone = {
	Provisioning: "running",
	Active: "healthy",
	Degraded: "degraded",
	Down: "down",
	Archived: "neutral",
} as const satisfies Record<ServerStatus, Tone>;

export const siteStatusTone = {
	Pending: "running",
	Active: "healthy",
	Maintenance: "degraded",
	Suspended: "neutral",
	Broken: "down",
	Archived: "neutral",
} as const satisfies Record<SiteStatus, Tone>;

export const jobStatusTone = {
	Queued: "running",
	Running: "running",
	Success: "healthy",
	Failed: "down",
	Cancelled: "neutral",
	Skipped: "neutral",
} as const satisfies Record<StepStatus, Tone>;

export const bulkStatusTone = {
	Queued: "running",
	Running: "running",
	Paused: "degraded",
	Halted: "down",
	Success: "healthy",
	Failed: "down",
	Cancelled: "neutral",
} as const satisfies Record<BulkStatus, Tone>;

export const bulkTargetStatusTone = {
	Pending: "neutral",
	Running: "running",
	Success: "healthy",
	Failed: "down",
	Skipped: "neutral",
} as const satisfies Record<BulkTargetStatus, Tone>;

/** `info` is blue without motion: informational, never "in motion" (Q-B5 follow-up). */
export const alertSeverityTone = {
	info: "running",
	warning: "degraded",
	critical: "down",
} as const satisfies Record<Severity, Tone>;

export const alertStatusTone = {
	firing: "down",
	acknowledged: "degraded",
	resolved: "healthy",
} as const satisfies Record<AlertStatus, Tone>;

export type StatusEntity =
	"server" | "site" | "job" | "step" | "bulk" | "bulkTarget" | "alert" | "severity";

const toneMaps: Record<StatusEntity, Readonly<Record<string, Tone>>> = {
	server: serverStatusTone,
	site: siteStatusTone,
	job: jobStatusTone,
	step: jobStatusTone,
	bulk: bulkStatusTone,
	bulkTarget: bulkTargetStatusTone,
	alert: alertStatusTone,
	severity: alertSeverityTone,
};

/** Tone for any entity's status; unknown values fall back to neutral so the UI never breaks. */
export function toneFor(entity: StatusEntity, status: string): Tone {
	return toneMaps[entity][status] ?? "neutral";
}

/**
 * Which states are genuinely live and may carry continuous motion (§10.3.8).
 * Queued and Pending are waiting, not moving, so they stay still.
 */
export const liveStates: ReadonlySet<string> = new Set(["Running", "Provisioning"]);

export const toneLabel: Record<Tone, string> = {
	healthy: "Healthy",
	degraded: "Degraded",
	down: "Down",
	running: "Running",
	neutral: "Inactive",
};

/** Tailwind needs literal class names, so tone → classes is a lookup, never interpolation. */
export const toneClass: Record<Tone, { text: string; soft: string; bg: string; border: string }> =
	{
		healthy: {
			text: "text-healthy",
			soft: "bg-healthy-soft",
			bg: "bg-healthy",
			border: "border-healthy",
		},
		degraded: {
			text: "text-degraded",
			soft: "bg-degraded-soft",
			bg: "bg-degraded",
			border: "border-degraded",
		},
		down: { text: "text-down", soft: "bg-down-soft", bg: "bg-down", border: "border-down" },
		running: {
			text: "text-running",
			soft: "bg-running-soft",
			bg: "bg-running",
			border: "border-running",
		},
		neutral: {
			text: "text-neutral",
			soft: "bg-neutral-soft",
			bg: "bg-neutral",
			border: "border-neutral",
		},
	};

export const providerLabel: Record<Provider, { short: string; long: string }> = {
	digitalocean: { short: "DO", long: "DigitalOcean" },
	frappe_cloud: { short: "FC", long: "Frappe Cloud" },
};
