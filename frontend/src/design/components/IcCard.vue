<script setup lang="ts">
withDefaults(
	defineProps<{
		title?: string;
		subtitle?: string;
		/** Elevation: 1 for panels on the canvas, 2 for cards inside panels. */
		level?: 1 | 2;
		padded?: boolean;
		/** Live: a running job inside; the card glows (§10.3.8). */
		live?: boolean;
	}>(),
	{ title: undefined, subtitle: undefined, level: 1, padded: true, live: false }
);
</script>

<template>
	<section
		class="flex flex-col rounded border"
		:class="[
			level === 1 ? 'bg-surface-1' : 'bg-surface-2',
			live ? 'ic-glow border-running' : 'border-line',
		]"
	>
		<header
			v-if="title || $slots.header || $slots.actions"
			class="flex items-start gap-4 border-b border-line px-5 py-3"
		>
			<div class="flex min-w-0 flex-col">
				<slot name="header">
					<h3 v-if="title" class="truncate text-md">{{ title }}</h3>
					<p v-if="subtitle" class="truncate text-xs text-fg-subtle">{{ subtitle }}</p>
				</slot>
			</div>
			<div v-if="$slots.actions" class="ms-auto flex shrink-0 items-center gap-2">
				<slot name="actions" />
			</div>
		</header>
		<div class="flex min-h-0 flex-1 flex-col" :class="{ 'p-5': padded }">
			<slot />
		</div>
		<footer v-if="$slots.footer" class="border-t border-line px-5 py-3">
			<slot name="footer" />
		</footer>
	</section>
</template>
