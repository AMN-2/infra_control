<script setup lang="ts">
defineProps<{ id: string; title: string; lead?: string }>();
</script>

<template>
	<section :id="id" :aria-labelledby="`${id}-title`" class="scroll-mt-20">
		<header class="mb-6 flex flex-col gap-1.5 border-b border-line pb-4">
			<h2 :id="`${id}-title`" class="text-xl">{{ title }}</h2>
			<p v-if="lead" class="max-w-3xl text-fg-muted">{{ lead }}</p>
		</header>
		<slot />
	</section>
</template>
