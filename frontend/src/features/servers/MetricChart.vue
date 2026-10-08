<script setup lang="ts">
import { onBeforeUnmount, onMounted, useTemplateRef, watch } from "vue";
import { duration, reducedMotion } from "@/design/motion";
import { chartGrid, token } from "@/design/tokens";
import type { MetricPoint } from "@/stores/metrics";

const props = defineProps<{ label: string; points: MetricPoint[]; unit?: string }>();
const root = useTemplateRef<HTMLDivElement>("root");
let chart: import("echarts/core").ECharts | undefined;
let observer: ResizeObserver | undefined;
let disposed = false;

function option(): import("echarts/core").EChartsCoreOption {
	return {
		animation: !reducedMotion.value,
		animationDuration: duration.emphasis * 1000,
		grid: chartGrid,
		tooltip: {
			trigger: "axis",
			backgroundColor: token("--ic-surface-3"),
			borderColor: token("--ic-line-strong"),
			textStyle: { color: token("--ic-fg") },
			valueFormatter: (value: unknown) =>
				typeof value === "number" || typeof value === "string"
					? `${value}${props.unit ?? ""}`
					: "—",
		},
		xAxis: {
			type: "time",
			axisLine: { lineStyle: { color: token("--ic-line-strong") } },
			axisLabel: { color: token("--ic-fg-subtle"), hideOverlap: true },
			splitLine: { show: false },
		},
		yAxis: {
			type: "value",
			min: props.unit === "%" ? 0 : undefined,
			max: props.unit === "%" ? 100 : undefined,
			axisLabel: { color: token("--ic-fg-subtle"), formatter: `{value}${props.unit ?? ""}` },
			splitLine: { lineStyle: { color: token("--ic-line") } },
		},
		series: [
			{
				name: props.label,
				type: "line",
				showSymbol: false,
				connectNulls: false,
				lineStyle: { color: token("--ic-running"), width: 2 },
				areaStyle: { color: token("--ic-running-soft"), opacity: 0.22 },
				data: props.points.map((point) => [point.ts, point.value]),
			},
		],
	};
}

onMounted(async () => {
	const el = root.value;
	if (!el) return;
	const { initMetricChart } = await import("./chartEngine");
	if (disposed) return;
	chart = initMetricChart(el);
	chart.setOption(option());
	if (typeof ResizeObserver !== "undefined") {
		observer = new ResizeObserver(() => chart?.resize());
		observer.observe(el);
	}
});

watch(
	() => props.points,
	() => chart?.setOption(option()),
	{ deep: true }
);
watch(reducedMotion, () => chart?.setOption(option()));
onBeforeUnmount(() => {
	disposed = true;
	observer?.disconnect();
	chart?.dispose();
});
</script>

<template>
	<div
		ref="root"
		class="h-52 w-full"
		role="img"
		:aria-label="`${label} metric history, ${points.length} readings`"
	/>
</template>
