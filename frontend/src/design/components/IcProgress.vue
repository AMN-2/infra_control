<script setup lang="ts">
import { computed } from "vue";
import { toneClass, type Tone } from "@/design/status";

const props = withDefaults(
	defineProps<{ value: number; tone?: Tone; label?: string; showValue?: boolean }>(),
	{ tone: "running", label: "Progress", showValue: true }
);
const clamped = computed(() => Math.max(0, Math.min(100, Math.round(props.value))));
</script>

<template>
	<div class="flex items-center gap-3">
		<div
			class="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-3"
			role="progressbar"
			:aria-label="label"
			:aria-valuenow="clamped"
			aria-valuemin="0"
			aria-valuemax="100"
		>
			<!-- Width is animated with a transform (§10.3.4), so the bar never reflows. -->
			<div
				class="h-full w-full origin-left rounded-full transition-transform duration-base ease-standard rtl:origin-right"
				:class="toneClass[tone].bg"
				:style="{ transform: `scaleX(${clamped / 100})` }"
			/>
		</div>
		<span v-if="showValue" class="numerals w-9 text-end text-xs text-fg-muted"
			>{{ clamped }}%</span
		>
	</div>
</template>
