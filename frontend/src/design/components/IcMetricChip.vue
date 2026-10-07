<script setup lang="ts">
import { computed } from "vue";
import { toneClass, type Tone } from "@/design/status";

/** One metric with a tone that reflects thresholds (cpu/ram/disk %), for server rows and detail. */
const props = withDefaults(
	defineProps<{
		label: string;
		value: number | null;
		unit?: string;
		warn?: number;
		crit?: number;
	}>(),
	{ unit: "%", warn: 80, crit: 90 }
);
const tone = computed<Tone>(() => {
	if (props.value === null) return "neutral";
	if (props.value >= props.crit) return "down";
	if (props.value >= props.warn) return "degraded";
	return "healthy";
});
</script>

<template>
	<span class="inline-flex items-baseline gap-1 rounded-sm bg-surface-2 px-2 py-1">
		<span class="eyebrow">{{ label }}</span>
		<span class="numerals text-sm" :class="toneClass[tone].text">
			{{ value === null ? "–" : `${Math.round(value)}${unit}` }}
		</span>
	</span>
</template>
