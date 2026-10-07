<script setup lang="ts">
withDefaults(
	defineProps<{
		label: string;
		forId?: string;
		hint?: string;
		error?: string;
		required?: boolean;
	}>(),
	{ forId: undefined, hint: undefined, error: undefined, required: false }
);
</script>

<template>
	<div class="flex flex-col gap-1.5">
		<label :for="forId" class="text-xs font-medium text-fg-muted">
			{{ label }}<span v-if="required" class="text-down" aria-hidden="true"> *</span>
		</label>
		<slot />
		<p v-if="error" class="text-xs text-down" role="alert">{{ error }}</p>
		<p v-else-if="hint" class="text-xs text-fg-subtle">{{ hint }}</p>
	</div>
</template>
