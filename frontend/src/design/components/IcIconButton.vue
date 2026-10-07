<script setup lang="ts">
withDefaults(
	defineProps<{ label: string; size?: "sm" | "md"; active?: boolean; disabled?: boolean }>(),
	{ size: "md", active: false, disabled: false }
);
</script>

<template>
	<button
		type="button"
		class="ic-state-layer inline-flex shrink-0 items-center justify-center rounded text-fg-muted hover:text-fg disabled:cursor-not-allowed disabled:opacity-50"
		:class="[size === 'sm' ? 'size-7' : 'size-8', { 'bg-surface-3 text-fg': active }]"
		:aria-label="label"
		:title="label"
		:aria-pressed="active || undefined"
		:disabled="disabled"
	>
		<slot />
	</button>
</template>
