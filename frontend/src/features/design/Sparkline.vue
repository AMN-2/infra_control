<script setup lang="ts">
import { computed, onMounted, useTemplateRef } from "vue";
import { reveal } from "@/design/motion";
import type { Tone } from "@/design/status";

const props = defineProps<{ points: readonly number[]; tone: Tone }>();

const outer = useTemplateRef<HTMLDivElement>("outer");
const inner = useTemplateRef<HTMLDivElement>("inner");

const strokeClass: Record<Tone, string> = {
	healthy: "stroke-healthy",
	degraded: "stroke-degraded",
	down: "stroke-down",
	running: "stroke-running",
	neutral: "stroke-neutral",
};

const path = computed(() => {
	const max = Math.max(...props.points);
	const min = Math.min(...props.points);
	const span = max - min || 1;
	const step = 100 / Math.max(1, props.points.length - 1);
	return props.points
		.map(
			(p, i) =>
				`${i === 0 ? "M" : "L"}${(i * step).toFixed(2)},${(30 - ((p - min) / span) * 28).toFixed(2)}`
		)
		.join(" ");
});

// Signature moment (Overview): the line draws in once, on arrival.
onMounted(() => {
	if (outer.value && inner.value) reveal(outer.value, inner.value);
});
</script>

<template>
	<div ref="outer" class="h-8 overflow-hidden" aria-hidden="true">
		<div ref="inner" class="size-full">
			<svg
				viewBox="0 0 100 32"
				preserveAspectRatio="none"
				class="size-full overflow-visible"
			>
				<path
					:d="path"
					fill="none"
					:class="strokeClass[tone]"
					stroke-width="1.5"
					stroke-linejoin="round"
					stroke-linecap="round"
					vector-effect="non-scaling-stroke"
				/>
			</svg>
		</div>
	</div>
</template>
