<script setup lang="ts">
import IcBreadcrumbs, { type Crumb } from "./IcBreadcrumbs.vue";

withDefaults(
	defineProps<{ title: string; subtitle?: string; crumbs?: readonly Crumb[]; mono?: boolean }>(),
	{ subtitle: undefined, crumbs: undefined, mono: false }
);
</script>

<template>
	<header class="flex flex-col gap-3 pb-5">
		<IcBreadcrumbs v-if="crumbs" :items="crumbs" />
		<div class="flex flex-wrap items-center gap-3">
			<div class="flex min-w-0 flex-col gap-1">
				<h1 class="truncate text-2xl" :class="{ 'font-mono tracking-normal': mono }">
					{{ title }}
				</h1>
				<p v-if="subtitle" class="text-fg-muted">{{ subtitle }}</p>
			</div>
			<div v-if="$slots.badges" class="flex items-center gap-2">
				<slot name="badges" />
			</div>
			<div v-if="$slots.actions" class="ms-auto flex items-center gap-2">
				<slot name="actions" />
			</div>
		</div>
	</header>
</template>
