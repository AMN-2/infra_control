<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { countUp } from "@/design/motion";
import { toneClass, type Tone } from "@/design/status";

const props = withDefaults(
	defineProps<{ label: string; value: number; note?: string; tone?: Tone; animate?: boolean }>(),
	{ note: undefined, tone: undefined, animate: true }
);

// Signature moment (Overview): numbers count up on arrival and on every change.
const shown = ref(props.animate ? 0 : props.value);
function run(from: number, to: number): void {
	countUp(from, to, (v) => {
		shown.value = Math.round(v);
	});
}
onMounted(() => {
	if (props.animate) run(0, props.value);
});
watch(
	() => props.value,
	(to, from) => {
		if (props.animate) run(from, to);
		else shown.value = to;
	}
);
</script>

<template>
	<div class="flex flex-col gap-3 rounded border border-line bg-surface-2 p-4">
		<span class="eyebrow">{{ label }}</span>
		<span class="numerals text-3xl leading-none font-medium" data-testid="stat-value">
			{{ shown }}
		</span>
		<slot />
		<span v-if="note" class="text-xs" :class="tone ? toneClass[tone].text : 'text-fg-subtle'">
			{{ note }}
		</span>
	</div>
</template>
