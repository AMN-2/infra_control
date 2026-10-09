<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import {
	IcBadge,
	IcButton,
	IcCard,
	IcField,
	IcInput,
	IcSelect,
	IcSwitch,
	pushToast,
} from "@/design/components";
import { relativeTime } from "@/lib/time";
import { useBackupsStore, type BackupPolicy } from "@/stores/backups";
import { useSessionStore } from "@/stores/session";

/** Backup schedule + retention for one site (A4.2). Saving recomputes the next run. */
const props = defineProps<{ site: string }>();
const backups = useBackupsStore();
const session = useSessionStore();

const enabled = ref(true);
const frequency = ref<BackupPolicy["frequency"]>("daily");
const hour = ref("2");
const weekday = ref<BackupPolicy["weekday"]>("sun");
const withFiles = ref(true);
const retain = ref("14");
const dirty = ref(false);

const policy = computed(() => backups.policies[props.site] ?? null);
const WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;

function load(): void {
	void backups.fetchPolicy(props.site);
}
watch(
	policy,
	(p) => {
		if (!p) return;
		enabled.value = p.enabled;
		frequency.value = p.frequency;
		hour.value = String(p.hour);
		weekday.value = p.weekday;
		withFiles.value = p.with_files;
		retain.value = String(p.retain);
		dirty.value = false;
	},
	{ immediate: true }
);
watch([enabled, frequency, hour, weekday, withFiles, retain], () => (dirty.value = true));
onMounted(load);

async function save(): Promise<void> {
	const saved = await backups.savePolicy({
		site: props.site,
		enabled: enabled.value,
		frequency: frequency.value,
		hour: Math.min(23, Math.max(0, Number(hour.value) || 0)),
		weekday: weekday.value,
		with_files: withFiles.value,
		retain: Math.min(365, Math.max(0, Number(retain.value) || 0)),
	});
	if (saved) {
		dirty.value = false;
		pushToast({
			title: "Backup schedule saved",
			description: saved.next_run ? `next run ${relativeTime(saved.next_run)}` : props.site,
			tone: "healthy",
		});
	} else
		pushToast({
			title: "Could not save the schedule",
			description: backups.saveError ?? "",
			tone: "down",
		});
}
</script>

<template>
	<IcCard
		title="Schedule"
		subtitle="Automatic site.backup jobs and how many backups to keep per kind."
	>
		<form
			class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
			data-testid="backup-policy"
			@submit.prevent="save"
		>
			<label class="flex items-center gap-2 text-sm lg:col-span-3">
				<IcSwitch
					v-model="enabled"
					label="Scheduled backups enabled"
					:disabled="!session.canOperate"
					data-testid="policy-enabled"
				/>
				Scheduled backups
				<IcBadge v-if="policy?.next_run && policy.enabled" tone="running" class="ms-2"
					>next {{ relativeTime(policy.next_run) }}</IcBadge
				>
				<IcBadge v-else-if="!policy" tone="neutral" class="ms-2">no schedule yet</IcBadge>
			</label>
			<IcField for-id="policy-frequency" label="Frequency">
				<IcSelect
					id="policy-frequency"
					v-model="frequency"
					:options="[
						{ value: 'hourly', label: 'Every hour' },
						{ value: 'daily', label: 'Every day' },
						{ value: 'weekly', label: 'Every week' },
					]"
					:disabled="!session.canOperate"
					data-testid="policy-frequency"
				/>
			</IcField>
			<IcField
				v-if="frequency !== 'hourly'"
				for-id="policy-hour"
				label="At hour (server time)"
				hint="0–23"
			>
				<IcInput
					id="policy-hour"
					v-model="hour"
					type="number"
					mono
					:disabled="!session.canOperate"
					data-testid="policy-hour"
				/>
			</IcField>
			<IcField v-if="frequency === 'weekly'" for-id="policy-weekday" label="On">
				<IcSelect
					id="policy-weekday"
					v-model="weekday"
					:options="WEEKDAYS.map((d) => ({ value: d, label: d }))"
					:disabled="!session.canOperate"
				/>
			</IcField>
			<IcField
				for-id="policy-retain"
				label="Keep per kind"
				hint="0 keeps everything; older backups are deleted from Spaces daily"
			>
				<IcInput
					id="policy-retain"
					v-model="retain"
					type="number"
					mono
					:disabled="!session.canOperate"
					data-testid="policy-retain"
				/>
			</IcField>
			<label class="flex items-center gap-2 text-sm">
				<IcSwitch
					v-model="withFiles"
					label="Include files"
					:disabled="!session.canOperate"
				/>
				Include public and private files
			</label>
			<div class="flex items-center gap-3 lg:col-span-3">
				<IcButton
					v-if="session.canOperate"
					type="submit"
					variant="primary"
					:disabled="!dirty"
					:loading="backups.saving"
					data-testid="policy-save"
					>Save schedule</IcButton
				>
				<span v-if="policy?.last_run" class="text-xs text-fg-subtle">
					last run {{ relativeTime(policy.last_run) }}
					<RouterLink
						v-if="policy.last_job"
						:to="`/jobs/${encodeURIComponent(policy.last_job)}`"
						class="font-mono hover:underline"
						>{{ policy.last_job }}</RouterLink
					>
				</span>
				<span v-if="backups.saveError" class="text-xs text-down" role="alert">{{
					backups.saveError
				}}</span>
			</div>
		</form>
	</IcCard>
</template>
