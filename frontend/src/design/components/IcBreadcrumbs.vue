<script setup lang="ts">
import { RouterLink } from "vue-router";
import { ChevronRight } from "lucide-vue-next";

export interface Crumb {
	label: string;
	to?: string;
}
defineProps<{ items: readonly Crumb[] }>();
</script>

<template>
	<nav aria-label="Breadcrumb">
		<ol class="flex items-center gap-1 text-xs text-fg-subtle">
			<li v-for="(c, i) in items" :key="c.label" class="flex items-center gap-1">
				<RouterLink v-if="c.to" :to="c.to" class="hover:text-fg">{{ c.label }}</RouterLink>
				<span
					v-else
					class="text-fg-muted"
					:aria-current="i === items.length - 1 ? 'page' : undefined"
				>
					{{ c.label }}
				</span>
				<ChevronRight
					v-if="i < items.length - 1"
					:size="12"
					class="rtl:-scale-x-100"
					aria-hidden="true"
				/>
			</li>
		</ol>
	</nav>
</template>
