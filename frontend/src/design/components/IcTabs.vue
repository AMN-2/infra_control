<script setup lang="ts">
export interface TabItem {
	id: string;
	label: string;
	count?: number;
}
const props = defineProps<{ tabs: readonly TabItem[]; label: string }>();
const model = defineModel<string>({ required: true });

function move(delta: number): void {
	const i = props.tabs.findIndex((t) => t.id === model.value);
	const next = props.tabs[(i + delta + props.tabs.length) % props.tabs.length];
	if (next) model.value = next.id;
}
</script>

<template>
	<div role="tablist" :aria-label="label" class="flex gap-1 border-b border-line">
		<button
			v-for="t in tabs"
			:id="`tab-${t.id}`"
			:key="t.id"
			type="button"
			role="tab"
			:aria-selected="model === t.id"
			:aria-controls="`panel-${t.id}`"
			:tabindex="model === t.id ? 0 : -1"
			class="ic-state-layer -mb-px inline-flex items-center gap-2 rounded-t-sm border-b-2 px-3 py-2 text-sm"
			:class="
				model === t.id
					? 'border-accent text-fg'
					: 'border-transparent text-fg-muted hover:text-fg'
			"
			@click="model = t.id"
			@keydown.arrow-right.prevent="move(1)"
			@keydown.arrow-left.prevent="move(-1)"
		>
			{{ t.label }}
			<span
				v-if="t.count !== undefined"
				class="numerals rounded-full bg-surface-3 px-1.5 text-2xs text-fg-muted"
			>
				{{ t.count }}
			</span>
		</button>
	</div>
</template>
