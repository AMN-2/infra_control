import type { Tone } from "@/design/status";
import type { Bench, InstalledApp } from "@/stores/inventory";

/** Roll-up of a bench's apps (ADR 0009): how many are behind, and whether any was checked. */
export interface UpdateSummary {
	behind: number;
	upToDate: number;
	unknown: number;
	/** "update_available" if any app is behind, "up_to_date" if all checked are current, else "unknown". */
	state: InstalledApp["update_state"];
	lastChecked: string | null;
}

export function summarize(apps: readonly InstalledApp[]): UpdateSummary {
	let behind = 0;
	let upToDate = 0;
	let unknown = 0;
	let lastChecked: string | null = null;
	for (const a of apps) {
		if (a.update_state === "update_available") behind += 1;
		else if (a.update_state === "up_to_date") upToDate += 1;
		else unknown += 1;
		if (a.checked_at && (!lastChecked || a.checked_at > lastChecked))
			lastChecked = a.checked_at;
	}
	const state: InstalledApp["update_state"] =
		behind > 0 ? "update_available" : upToDate > 0 ? "up_to_date" : "unknown";
	return { behind, upToDate, unknown, state, lastChecked };
}

export const updateTone: Record<InstalledApp["update_state"], Tone> = {
	update_available: "degraded",
	up_to_date: "healthy",
	unknown: "neutral",
};

export const updateLabel: Record<InstalledApp["update_state"], string> = {
	update_available: "Update available",
	up_to_date: "Up to date",
	unknown: "Not checked",
};

export function benchState(b: Pick<Bench, "apps">): InstalledApp["update_state"] {
	return summarize(b.apps).state;
}

/** `v15.101.0` is newer than version `15.98.1`: a release the bench could move to. */
export function newerTag(app: Pick<InstalledApp, "version" | "latest_tag">): string | null {
	if (!app.latest_tag) return null;
	const parse = (v: string): number[] | null => {
		const m = /^v?(\d+(?:\.\d+)*)/.exec(v.trim());
		const digits = m?.[1];
		return digits ? digits.split(".").map(Number) : null;
	};
	const tag = parse(app.latest_tag);
	const cur = app.version ? parse(app.version) : null;
	if (!tag) return null;
	if (!cur) return app.latest_tag;
	for (let i = 0; i < Math.max(tag.length, cur.length); i += 1) {
		const t = tag[i] ?? 0;
		const c = cur[i] ?? 0;
		if (t !== c) return t > c ? app.latest_tag : null;
	}
	return null;
}
