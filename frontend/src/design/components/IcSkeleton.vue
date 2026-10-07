<script setup lang="ts">
/** Loading placeholder (§10.3.7: skeletons, never spinners). Breathes via opacity only. */
withDefaults(defineProps<{ variant?: "text" | "block" | "circle"; lines?: number }>(), {
	variant: "text",
	lines: 1,
});
</script>

<template>
	<div class="flex flex-col gap-2" aria-busy="true" aria-live="polite" role="status">
		<span class="sr-only">Loading</span>
		<template v-if="variant === 'text'">
			<span
				v-for="i in lines"
				:key="i"
				class="ic-live ic-skeleton block h-3 rounded-sm bg-surface-3"
				:class="i === lines && lines > 1 ? 'w-2/3' : 'w-full'"
			/>
		</template>
		<span
			v-else-if="variant === 'circle'"
			class="ic-live ic-skeleton size-8 rounded-full bg-surface-3"
		/>
		<span v-else class="ic-live ic-skeleton block h-24 w-full rounded bg-surface-3" />
	</div>
</template>
