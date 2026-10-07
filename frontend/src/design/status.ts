/**
 * Status → tone (plan §10.1: green healthy, amber degraded, red down, blue running, identical
 * everywhere). States the plan does not colour are mapped per docs/QUESTIONS.md Q-B5.
 * Enum values are from plan §5; they will be checked against the generated contract types
 * once contracts/openapi.yaml merges.
 */
export type Tone = "healthy" | "degraded" | "down" | "running" | "neutral";

export const serverStatusTone = {
	Provisioning: "running",
	Active: "healthy",
	Degraded: "degraded",
	Down: "down",
	Archived: "neutral",
} as const satisfies Record<string, Tone>;

export const siteStatusTone = {
	Pending: "running",
	Active: "healthy",
	Maintenance: "degraded",
	Suspended: "neutral",
	Broken: "down",
	Archived: "neutral",
} as const satisfies Record<string, Tone>;

export const jobStatusTone = {
	Queued: "running",
	Running: "running",
	Success: "healthy",
	Failed: "down",
	Cancelled: "neutral",
	Skipped: "neutral",
} as const satisfies Record<string, Tone>;

export const alertSeverityTone = {
	critical: "down",
	warning: "degraded",
} as const satisfies Record<string, Tone>;

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
