import { defineStore } from "pinia";
import { ref } from "vue";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { ApiError } from "@/api/errors";
import { unwrap } from "./_async";

type S = components["schemas"];
export type MetricName = S["MetricName"];
export type MetricPoint = S["MetricPoint"];
export type MetricSeries = S["MetricSeries"];
export const METRICS: readonly MetricName[] = ["cpu", "ram", "disk", "load1", "queue_backlog"];

/** Historical metric series. Realtime heartbeats extend the loaded series in place. */
export const useMetricsStore = defineStore("metrics", () => {
	const series = ref<Record<string, Partial<Record<MetricName, MetricSeries>>>>({});
	const loading = ref<Record<string, boolean>>({});
	const errors = ref<Record<string, ApiError | null>>({});

	async function fetchServer(server: string, hours = 24): Promise<void> {
		loading.value[server] = true;
		errors.value[server] = null;
		const to = new Date();
		const from = new Date(to.getTime() - hours * 60 * 60 * 1000);
		try {
			const rows = await Promise.all(
				METRICS.map(async (metric) =>
					unwrap(
						await api.GET("/api/method/infra_control.api.metrics.series", {
							params: {
								query: {
									server,
									metric,
									from: from.toISOString(),
									to: to.toISOString(),
								},
							},
						})
					)
				)
			);
			series.value[server] = Object.fromEntries(rows.map((row) => [row.metric, row]));
		} catch (error) {
			errors.value[server] =
				error instanceof ApiError
					? error
					: new ApiError(0, { code: "network_error", message: String(error) });
		} finally {
			loading.value[server] = false;
		}
	}

	function appendHeartbeat(
		server: string,
		beat: { ts: string; cpu: number; ram: number; disk: number }
	): void {
		const serverSeries = series.value[server];
		if (!serverSeries) return;
		for (const metric of ["cpu", "ram", "disk"] as const) {
			const row = serverSeries[metric];
			if (!row) continue;
			const point = { ts: beat.ts, value: beat[metric] };
			const last = row.points.at(-1);
			if (last?.ts === beat.ts) row.points[row.points.length - 1] = point;
			else row.points.push(point);
			row.points = row.points.slice(-1000);
			row.to = beat.ts;
		}
	}

	return { series, loading, errors, fetchServer, appendHeartbeat };
});
