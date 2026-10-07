<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
	defineProps<{
		variant?: "primary" | "secondary" | "ghost" | "danger";
		size?: "sm" | "md";
		type?: "button" | "submit";
		disabled?: boolean;
		/** Shows progress feedback and blocks clicks; the label stays visible (no spinner, §10.3.7). */
		loading?: boolean;
	}>(),
	{ variant: "secondary", size: "md", type: "button", disabled: false, loading: false }
);

const variantClass = {
	primary: "bg-accent text-accent-fg hover:bg-accent-hover active:bg-accent-press",
	secondary: "border border-line-strong bg-surface-2 text-fg",
	ghost: "text-fg-muted hover:text-fg",
	danger: "border border-down bg-down-soft text-down",
} as const;
const sizeClass = { sm: "h-7 px-2.5 text-xs gap-1.5", md: "h-8 px-3 text-sm gap-2" } as const;

const inert = computed(() => props.disabled || props.loading);
</script>

<template>
	<button
		:type="type"
		class="ic-state-layer inline-flex shrink-0 items-center justify-center rounded font-medium whitespace-nowrap select-none disabled:cursor-not-allowed disabled:opacity-50"
		:class="[variantClass[variant], sizeClass[size], { 'cursor-progress': loading }]"
		:disabled="inert"
		:aria-busy="loading || undefined"
	>
		<slot name="icon" />
		<slot />
	</button>
</template>
