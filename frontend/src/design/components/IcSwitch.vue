<script setup lang="ts">
withDefaults(defineProps<{ label: string; disabled?: boolean }>(), { disabled: false });
const model = defineModel<boolean>({ default: false });
</script>

<template>
	<button
		type="button"
		role="switch"
		:aria-checked="model"
		:aria-label="label"
		:disabled="disabled"
		class="group inline-flex h-5 w-9 shrink-0 items-center rounded-full border border-line-strong p-px disabled:cursor-not-allowed disabled:opacity-50"
		:class="model ? 'bg-accent' : 'bg-surface-3'"
		@click="model = !model"
	>
		<!-- The knob slides with a transform (§10.3.4). -->
		<span
			class="size-4 rounded-full bg-fg transition-transform duration-press ease-standard"
			:class="model ? 'translate-x-4 rtl:-translate-x-4' : 'translate-x-0'"
		/>
	</button>
</template>
