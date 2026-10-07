<script setup lang="ts">
export interface SelectOption {
	value: string;
	label: string;
	disabled?: boolean;
}
withDefaults(
	defineProps<{
		id?: string;
		options: readonly SelectOption[];
		placeholder?: string;
		disabled?: boolean;
	}>(),
	{ id: undefined, placeholder: undefined, disabled: false }
);
const model = defineModel<string>({ default: "" });
</script>

<template>
	<select
		:id="id"
		v-model="model"
		:disabled="disabled"
		class="h-8 w-full rounded border border-line-strong bg-surface-2 px-2 text-sm text-fg disabled:cursor-not-allowed disabled:opacity-50"
	>
		<option v-if="placeholder" value="" disabled>{{ placeholder }}</option>
		<option v-for="o in options" :key="o.value" :value="o.value" :disabled="o.disabled">
			{{ o.label }}
		</option>
	</select>
</template>
