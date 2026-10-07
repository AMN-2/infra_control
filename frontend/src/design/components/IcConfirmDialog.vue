<script setup lang="ts">
import { computed, ref, watch } from "vue";
import IcButton from "./IcButton.vue";
import IcDialog from "./IcDialog.vue";
import IcField from "./IcField.vue";
import IcInput from "./IcInput.vue";

/**
 * Typed confirmation for high-risk actions (plan §6.1, security 6): the user must type the
 * expected string exactly; the API also enforces it (400 confirmation_required).
 */
const props = withDefaults(
	defineProps<{
		title: string;
		description?: string;
		/** What the user must type: the target name, or `<playbook>:<count>` for bulk. */
		expected: string;
		confirmLabel?: string;
		busy?: boolean;
	}>(),
	{ description: undefined, confirmLabel: "Confirm", busy: false }
);
const open = defineModel<boolean>({ default: false });
const emit = defineEmits<{ confirm: [value: string] }>();

const typed = ref("");
const matches = computed(() => typed.value === props.expected);
watch(open, (v) => {
	if (!v) typed.value = "";
});
function submit(): void {
	if (matches.value && !props.busy) emit("confirm", typed.value);
}
</script>

<template>
	<IcDialog v-model="open" :title="title" :description="description" size="sm">
		<form class="flex flex-col gap-3" @submit.prevent="submit">
			<IcField for-id="confirm-input" :label="`Type ${expected} to confirm`">
				<IcInput
					id="confirm-input"
					v-model="typed"
					mono
					autofocus
					:placeholder="expected"
					:invalid="typed.length > 0 && !matches"
					data-testid="confirm-input"
				/>
			</IcField>
		</form>
		<template #footer="{ close }">
			<IcButton variant="ghost" @click="close">Cancel</IcButton>
			<IcButton
				variant="danger"
				:disabled="!matches"
				:loading="busy"
				data-testid="confirm-submit"
				@click="submit"
			>
				{{ confirmLabel }}
			</IcButton>
		</template>
	</IcDialog>
</template>
