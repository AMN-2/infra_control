import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { onEvent } from "@/realtime";
import { trailing, unwrap, useAsyncState } from "./_async";

export type OverviewSummary = components["schemas"]["OverviewSummary"];

/** One fetch of the summary, reduced to the four headline numbers (for the sparklines). */
export interface OverviewSnapshot {
	ts: string;
	servers: number;
	sites: number;
	jobs: number;
	alerts: number;
}

/** How many snapshots the sparklines keep. The contract has no trend series (Q-B8). */
export const HISTORY_MAX = 24;

export const useOverviewStore = defineStore("overview", () => {
	const summary = ref<OverviewSummary | null>(null);
	const history = ref<OverviewSnapshot[]>([]);
	const { loading, error, run } = useAsyncState();

	async function fetch(): Promise<void> {
		await run(async () => {
			const s = unwrap(await api.GET("/api/method/infra_control.api.overview.summary"));
			summary.value = s;
			history.value = [
				...history.value,
				{
					ts: s.generated_at,
					servers: s.servers.total,
					sites: s.sites.total,
					jobs: s.jobs.running + s.jobs.queued,
					alerts: s.alerts.unresolved,
				},
			].slice(-HISTORY_MAX);
		});
	}

	/** Sparkline series per headline; empty until two snapshots exist. */
	const trend = computed(() => {
		const h = history.value;
		const pick = (k: keyof Omit<OverviewSnapshot, "ts">): number[] =>
			h.length >= 2 ? h.map((s) => s[k]) : [];
		return {
			servers: pick("servers"),
			sites: pick("sites"),
			jobs: pick("jobs"),
			alerts: pick("alerts"),
		};
	});

	// Live: a running job's progress is patched in place; anything that changes the counts
	// (a job starting or ending, an alert firing or resolving) refetches once per burst.
	const refetch = trailing(() => void fetch(), 1000);
	let subscribed = false;
	function subscribe(): void {
		if (subscribed) return;
		subscribed = true;
		onEvent("infra:job.updated", (e) => {
			const s = summary.value;
			if (!s) return;
			const job = s.running_jobs.find((j) => j.name === e.job);
			if (job) {
				job.status = e.status;
				job.progress = e.progress;
			}
			if (!job || e.status !== "Running") refetch();
		});
		onEvent("infra:alert.fired", refetch);
		onEvent("infra:alert.resolved", refetch);
	}

	return { summary, history, trend, loading, error, fetch, subscribe };
});
