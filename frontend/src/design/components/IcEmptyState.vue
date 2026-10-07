<script setup lang="ts">
withDefaults(defineProps<{ title: string; description?: string }>(), { description: undefined });
</script>

<template>
	<div class="flex flex-col items-center gap-3 px-6 py-12 text-center" data-testid="empty-state">
		<div v-if="$slots.icon" class="text-fg-subtle">
			<slot name="icon" />
		</div>
		<p class="text-md text-fg">{{ title }}</p>
		<p v-if="description" class="max-w-md text-fg-muted">{{ description }}</p>
		<div v-if="$slots.action" class="mt-2">
			<slot name="action" />
		</div>
	</div>
</template>
