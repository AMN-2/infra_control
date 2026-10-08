<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { IcButton, IcDialog, IcField, IcInput, IcSelect, IcSwitch } from "@/design/components";
import { useAlertRulesStore } from "@/stores/alertRules";
import {
	CHANNELS,
	METRICS,
	OPERATORS,
	SEVERITIES,
	emptyForm,
	forMinutesLabel,
	formFromRule,
	kindFields,
	thresholdLabel,
	toInput,
	toUpdate,
	validate,
	type AlertChannel,
	type AlertRule,
	type RuleForm,
} from "./ruleForm";

/**
 * Rule editor (B3.2). Without `rule` it creates a `metric` rule; with one it edits only the
 * fields the rule's kind allows, so built-in rules (heartbeat, ssl_expiry, drift, contract)
 * expose title, severity, channels, enabled and their one tunable.
 */
const props = defineProps<{ rule?: AlertRule | null }>();
const open = defineModel<boolean>({ default: false });
const emit = defineEmits<{ saved: [rule: AlertRule] }>();
const rules = useAlertRulesStore();

const form = ref<RuleForm>(emptyForm());
const touched = ref(false);
const kind = computed(() => props.rule?.kind ?? "metric");
const fields = computed(() => kindFields(kind.value));
const errors = computed(() => validate(kind.value, form.value));
const valid = computed(() => Object.keys(errors.value).length === 0);
const title = computed(() => (props.rule ? `Edit rule · ${props.rule.name}` : "New metric rule"));
const metricOptions = METRICS.map((m) => ({ value: m.value, label: m.label }));
const operatorOptions = OPERATORS.map((o) => ({ value: o.value, label: o.label }));
const severityOptions = SEVERITIES.map((s) => ({ value: s, label: s }));

watch(open, (v) => {
	if (!v) return;
	form.value = props.rule ? formFromRule(props.rule) : emptyForm();
	touched.value = false;
	rules.saveError = null;
});

function toggleChannel(c: AlertChannel, on: boolean): void {
	const set = new Set(form.value.channels);
	if (on) set.add(c);
	else set.delete(c);
	form.value.channels = CHANNELS.filter((x) => set.has(x));
}
function error(field: string): string | undefined {
	return touched.value ? errors.value[field] : undefined;
}
async function submit(): Promise<void> {
	touched.value = true;
	if (!valid.value || rules.saving) return;
	const saved = props.rule
		? await rules.update(toUpdate(props.rule, form.value))
		: await rules.create(toInput(form.value));
	if (saved) {
		emit("saved", saved);
		open.value = false;
	}
}
</script>

<template>
	<IcDialog v-model="open" :title="title" size="md">
		<form class="grid gap-4 sm:grid-cols-2" data-testid="rule-form" @submit.prevent="submit">
			<IcField
				class="sm:col-span-2"
				for-id="rule-title"
				label="Title"
				required
				:error="error('title')"
			>
				<IcInput id="rule-title" v-model="form.title" autofocus data-testid="rule-title" />
			</IcField>
			<IcField v-if="fields.includes('metric')" for-id="rule-metric" label="Metric" required>
				<IcSelect id="rule-metric" v-model="form.metric" :options="metricOptions" />
			</IcField>
			<IcField
				v-if="fields.includes('operator')"
				for-id="rule-operator"
				label="Condition"
				required
			>
				<IcSelect id="rule-operator" v-model="form.operator" :options="operatorOptions" />
			</IcField>
			<IcField
				v-if="fields.includes('threshold')"
				for-id="rule-threshold"
				:label="thresholdLabel(kind)"
				required
				:error="error('threshold')"
			>
				<IcInput
					id="rule-threshold"
					v-model="form.threshold"
					type="number"
					mono
					data-testid="rule-threshold"
				/>
			</IcField>
			<IcField
				v-if="fields.includes('for_minutes')"
				for-id="rule-for"
				:label="forMinutesLabel(kind)"
				required
				:error="error('for_minutes')"
			>
				<IcInput
					id="rule-for"
					v-model="form.for_minutes"
					type="number"
					mono
					data-testid="rule-for-minutes"
				/>
			</IcField>
			<IcField for-id="rule-severity" label="Severity" required>
				<IcSelect id="rule-severity" v-model="form.severity" :options="severityOptions" />
			</IcField>
			<IcField label="Channels" required :error="error('channels')">
				<div class="flex h-8 items-center gap-5">
					<label v-for="c in CHANNELS" :key="c" class="flex items-center gap-2 text-sm">
						<IcSwitch
							:model-value="form.channels.includes(c)"
							:label="c"
							:data-testid="`rule-channel-${c}`"
							@update:model-value="(on) => toggleChannel(c, on)"
						/>
						{{ c }}
					</label>
				</div>
			</IcField>
			<label class="flex items-center gap-2 text-sm sm:col-span-2">
				<IcSwitch v-model="form.enabled" label="Enabled" data-testid="rule-enabled" />
				Enabled
			</label>
			<p
				v-if="rules.saveError"
				class="text-xs text-down sm:col-span-2"
				role="alert"
				data-testid="rule-save-error"
			>
				{{ rules.saveError }}
			</p>
		</form>
		<template #footer="{ close }">
			<IcButton variant="ghost" @click="close">Cancel</IcButton>
			<IcButton
				variant="primary"
				:disabled="touched && !valid"
				:loading="rules.saving"
				data-testid="rule-submit"
				@click="submit"
				>{{ props.rule ? "Save changes" : "Create rule" }}</IcButton
			>
		</template>
	</IcDialog>
</template>
