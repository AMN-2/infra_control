<script setup lang="ts">
withDefaults(
	defineProps<{
		id?: string;
		type?: "text" | "search" | "password" | "number" | "email";
		placeholder?: string;
		mono?: boolean;
		invalid?: boolean;
		disabled?: boolean;
		autocomplete?: string;
	}>(),
	{
		id: undefined,
		type: "text",
		placeholder: undefined,
		mono: false,
		invalid: false,
		disabled: false,
		autocomplete: "off",
	}
);
const model = defineModel<string>({ default: "" });
</script>

<template>
	<input
		:id="id"
		v-model="model"
		:type="type"
		:placeholder="placeholder"
		:disabled="disabled"
		:autocomplete="autocomplete"
		:aria-invalid="invalid || undefined"
		class="h-8 w-full rounded border bg-surface-2 px-2.5 text-sm text-fg placeholder:text-fg-subtle disabled:cursor-not-allowed disabled:opacity-50"
		:class="[invalid ? 'border-down' : 'border-line-strong', { 'font-mono': mono }]"
	/>
</template>
