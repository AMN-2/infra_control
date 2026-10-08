<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
	IcBadge,
	IcButton,
	IcDialog,
	IcField,
	IcInput,
	IcSelect,
	IcSwitch,
	pushToast,
} from "@/design/components";
import { toneFor } from "@/design/status";
import { useJobsStore } from "@/stores/jobs";
import GitPickers from "./GitPickers.vue";
import type { Playbook, TargetDoctype } from "@/stores/playbooks";
import {
	fieldsFrom,
	initialValues,
	splitList,
	toParams,
	validate,
	type ParamValues,
} from "./schemaForm";

/**
 * Run a playbook on a target (plan §10.2 "run-playbook dialog with typed confirmation").
 * The form comes from `params_schema`; high-risk playbooks also require typing the target name
 * (the backend enforces the same with `confirm`). On success the operator is taken to the job.
 */
const props = defineProps<{
	playbook: Playbook;
	targetDoctype: TargetDoctype;
	targetName: string;
	/** Shown in the title; defaults to the target name. */
	targetLabel?: string;
}>();
const open = defineModel<boolean>({ default: false });
const emit = defineEmits<{ queued: [job: string] }>();

const jobs = useJobsStore();
const router = useRouter();

const fields = computed(() => fieldsFrom(props.playbook.params_schema));
/** Fields with an `x-picker` are rendered together by GitPickers (ADR 0005). */
const pickerFields = computed(() => fields.value.filter((f) => f.picker));
const plainFields = computed(() => fields.value.filter((f) => !f.picker));
const pickerWants = computed(() => ({
	connection: pickerFields.value.some((f) => f.picker === "git_connection"),
	repo: pickerFields.value.some((f) => f.picker === "git_repo"),
	branch: pickerFields.value.some((f) => f.picker === "git_ref"),
}));
function pickerName(kind: "git_connection" | "git_repo" | "git_ref"): string {
	return pickerFields.value.find((f) => f.picker === kind)?.name ?? kind;
}
const values = ref<ParamValues>({});
const listText = ref<Record<string, string>>({});
const touched = ref(false);
const typed = ref("");
const submitError = ref<string | null>(null);
const busy = ref(false);

function reset(): void {
	values.value = initialValues(fields.value);
	listText.value = Object.fromEntries(
		fields.value
			.filter((f) => f.kind === "strings")
			.map((f) => {
				const v = values.value[f.name];
				return [f.name, Array.isArray(v) ? v.join(", ") : ""];
			})
	);
	touched.value = false;
	typed.value = "";
	submitError.value = null;
}
watch(
	() => [open.value, props.playbook.key],
	([isOpen]) => {
		if (isOpen) reset();
	},
	{ immediate: true }
);

const errors = computed(() => validate(fields.value, values.value));
const highRisk = computed(() => props.playbook.risk === "high");
const confirmed = computed(() => !highRisk.value || typed.value === props.targetName);
const canSubmit = computed(
	() => Object.keys(errors.value).length === 0 && confirmed.value && !busy.value
);
const riskTone = computed(() => toneFor("severity", riskToSeverity[props.playbook.risk]));
const riskToSeverity = { low: "info", medium: "warning", high: "critical" } as const;

function setList(name: string, text: string): void {
	listText.value[name] = text;
	values.value[name] = splitList(text);
}
function stringValue(name: string): string {
	const v = values.value[name];
	if (typeof v === "string") return v;
	if (typeof v === "number") return String(v);
	return "";
}
function boolValue(name: string): boolean {
	return values.value[name] === true;
}

async function submit(): Promise<void> {
	touched.value = true;
	if (!canSubmit.value) return;
	busy.value = true;
	submitError.value = null;
	const job = await jobs.runPlaybook({
		playbook: props.playbook.key,
		target_doctype: props.targetDoctype,
		target_name: props.targetName,
		params: toParams(fields.value, values.value),
		...(highRisk.value ? { confirm: typed.value } : {}),
	});
	busy.value = false;
	if (!job) {
		const e = jobs.error;
		submitError.value = e ? `${e.message} (${e.code})` : "The job could not be created.";
		return;
	}
	pushToast({
		title: `${props.playbook.title} queued`,
		description: `${job.name} on ${props.targetLabel ?? props.targetName}`,
		tone: "running",
	});
	emit("queued", job.name);
	open.value = false;
	void router.push(`/jobs/${encodeURIComponent(job.name)}`);
}
</script>

<template>
	<IcDialog v-model="open" :title="playbook.title" :description="playbook.description" size="md">
		<form class="flex flex-col gap-4" data-testid="run-dialog" @submit.prevent="submit">
			<div class="flex flex-wrap items-center gap-2 text-xs text-fg-muted">
				<span>Target</span>
				<span class="font-mono text-fg">{{ targetLabel ?? targetName }}</span>
				<IcBadge :tone="riskTone" uppercase class="ms-auto"
					>{{ playbook.risk }} risk</IcBadge
				>
			</div>

			<GitPickers
				v-if="pickerFields.length"
				:connection="stringValue(pickerName('git_connection'))"
				:repo="stringValue(pickerName('git_repo'))"
				:branch="stringValue(pickerName('git_ref'))"
				:wants="pickerWants"
				:invalid-repo="touched && !!errors[pickerName('git_repo')]"
				@update:connection="(v: string) => (values[pickerName('git_connection')] = v)"
				@update:repo="(v: string) => (values[pickerName('git_repo')] = v)"
				@update:branch="(v: string) => (values[pickerName('git_ref')] = v)"
			/>
			<p
				v-if="touched && pickerWants.repo && errors[pickerName('git_repo')]"
				class="text-xs text-down"
				role="alert"
			>
				Repository: {{ errors[pickerName("git_repo")] }}
			</p>

			<IcField
				v-for="f in plainFields"
				:key="f.name"
				:label="f.label"
				:for-id="`param-${f.name}`"
				:required="f.required"
				:hint="f.description"
				:error="touched ? errors[f.name] : undefined"
			>
				<IcSwitch
					v-if="f.kind === 'boolean'"
					:model-value="boolValue(f.name)"
					:label="f.label"
					@update:model-value="(v: boolean) => (values[f.name] = v)"
				/>
				<IcSelect
					v-else-if="f.kind === 'enum'"
					:id="`param-${f.name}`"
					:model-value="stringValue(f.name)"
					:options="(f.options ?? []).map((o) => ({ value: o, label: o }))"
					placeholder="Choose…"
					@update:model-value="(v: string) => (values[f.name] = v)"
				/>
				<IcInput
					v-else-if="f.kind === 'strings'"
					:id="`param-${f.name}`"
					:model-value="listText[f.name] ?? ''"
					mono
					placeholder="comma separated"
					:invalid="touched && !!errors[f.name]"
					@update:model-value="(v: string) => setList(f.name, v)"
				/>
				<IcInput
					v-else
					:id="`param-${f.name}`"
					:model-value="stringValue(f.name)"
					:type="
						f.kind === 'password'
							? 'password'
							: f.kind === 'number' || f.kind === 'integer'
								? 'number'
								: 'text'
					"
					:mono="f.kind !== 'password'"
					:autocomplete="f.kind === 'password' ? 'new-password' : undefined"
					:invalid="touched && !!errors[f.name]"
					@update:model-value="
						(v: string) =>
							(values[f.name] =
								f.kind === 'number' || f.kind === 'integer'
									? v === ''
										? null
										: Number(v)
									: v)
					"
				/>
			</IcField>

			<IcField
				v-if="highRisk"
				for-id="confirm-input"
				:label="`Type ${targetName} to confirm`"
				hint="High-risk playbook: the server requires the target name as confirmation."
			>
				<IcInput
					id="confirm-input"
					v-model="typed"
					mono
					:placeholder="targetName"
					:invalid="typed.length > 0 && !confirmed"
					data-testid="confirm-input"
				/>
			</IcField>

			<p v-if="submitError" class="text-xs text-down" role="alert" data-testid="run-error">
				{{ submitError }}
			</p>
		</form>
		<template #footer="{ close }">
			<IcButton variant="ghost" @click="close">Cancel</IcButton>
			<IcButton
				:variant="highRisk ? 'danger' : 'primary'"
				:disabled="!canSubmit"
				:loading="busy"
				data-testid="run-submit"
				@click="submit"
			>
				Run {{ playbook.title.toLowerCase() }}
			</IcButton>
		</template>
	</IcDialog>
</template>
