import { defineStore } from "pinia";
import { ref } from "vue";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { onEvent } from "@/realtime";
import { unwrap, useAsyncState } from "./_async";

export type OverviewSummary = components["schemas"]["OverviewSummary"];

export const useOverviewStore = defineStore("overview", () => {
	const summary = ref<OverviewSummary | null>(null);
	const { loading, error, run } = useAsyncState();

	async function fetch(): Promise<void> {
		await run(async () => {
			summary.value = unwrap(
				await api.GET("/api/method/infra_control.api.overview.summary")
			);
		});
	}

	// Live: running jobs and alerts change the counts; refetch cheaply on terminal events.
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
			if (e.status !== "Running" && e.status !== "Queued") void fetch();
		});
		onEvent("infra:alert.fired", () => void fetch());
		onEvent("infra:alert.resolved", () => void fetch());
	}

	return { summary, loading, error, fetch, subscribe };
});
