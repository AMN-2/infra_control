<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { liveStates, toneClass, toneFor } from "@/design/status";
import { transitions } from "@/design/motion";
import IcStatusDot from "./IcStatusDot.vue";

export interface TimelineStep {
	idx: number;
	title: string;
	status: string;
	started_at?: string | null;
	ended_at?: string | null;
	output?: string;
}
const props = defineProps<{ steps: readonly TimelineStep[] }>();

/** Signature moment (Job viewer): the running step is expanded; finished ones collapse. */
const expanded = ref<number | null>(null);
const running = computed(() => props.steps.find((s) => liveStates.has(s.status))?.idx ?? null);
watch(running, (idx) => (expanded.value = idx), { immediate: true });

function toggle(idx: number): void {
	expanded.value = expanded.value === idx ? null : idx;
}
function durationOf(step: TimelineStep): string {
	if (!step.started_at) return "";
	const end = step.ended_at ? Date.parse(step.ended_at) : Date.now();
	const s = Math.max(0, Math.round((end - Date.parse(step.started_at)) / 1000));
	return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
}
</script>

<template>
	<ol class="flex flex-col" data-testid="timeline">
		<li
			v-for="s in steps"
			:key="s.idx"
			class="relative flex flex-col ps-6 pb-4 last:pb-0"
			:data-status="s.status"
		>
			<!-- Connector between dots -->
			<span class="absolute inset-y-0 start-[3px] border-s border-line" aria-hidden="true" />
			<span class="absolute start-0 top-1.5">
				<IcStatusDot :tone="toneFor('step', s.status)" :live="liveStates.has(s.status)" />
			</span>
			<button
				type="button"
				class="flex items-center gap-3 text-start"
				:aria-expanded="expanded === s.idx"
				@click="toggle(s.idx)"
			>
				<span class="numerals text-xs text-fg-subtle">{{ s.idx + 1 }}</span>
				<span :class="[toneClass[toneFor('step', s.status)].text, 'font-medium']">{{
					s.title
				}}</span>
				<span class="ms-auto font-mono text-xs text-fg-subtle">{{ durationOf(s) }}</span>
			</button>
			<Transition :name="transitions.fade">
				<pre
					v-if="expanded === s.idx && s.output"
					class="mt-2 max-h-64 overflow-auto rounded-sm border border-line bg-canvas p-3 font-mono text-xs leading-snug whitespace-pre-wrap text-fg-muted"
					>{{ s.output }}</pre>
			</Transition>
		</li>
	</ol>
</template>
