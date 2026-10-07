<script setup lang="ts">
defineProps<{ name: string; note?: string }>();
</script>

<template>
	<span class="flex flex-col gap-0.5">
		<code class="text-xs text-fg">{{ name }}</code>
		<span v-if="note" class="text-xs text-fg-subtle">{{ note }}</span>
	</span>
</template>
