<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import {
	IcButton,
	IcCard,
	IcEmptyState,
	IcField,
	IcInput,
	IcPageHeader,
	IcProgress,
	IcSelect,
	IcSkeleton,
	IcStatusBadge,
} from "@/design/components";
import ErrorState from "@/features/system/ErrorState.vue";
import { relativeTime } from "@/lib/time";
import { useBulkStore } from "@/stores/bulk";
import { usePlaybooksStore } from "@/stores/playbooks";
const bulk = useBulkStore();
const playbooks = usePlaybooksStore();
const creating = ref(false);
const playbook = ref("");
const targetText = ref("");
const canary = ref("");
const batchSize = ref("5");
const failurePolicy = ref("halt");
const confirm = ref("");
const detail = computed(() => (bulk.selected ? bulk.details[bulk.selected] : undefined));
const names = computed(() => [
	...new Set(
		targetText.value
			.split(/\r?\n|,/)
			.map((v) => v.trim())
			.filter(Boolean)
	),
]);
const playbookOptions = computed(() =>
	playbooks.catalogue
		.filter((x) => x.target_doctype === "Site" && !x.creates)
		.map((x) => ({ value: x.key, label: x.title + " · " + x.risk }))
);
const canaryOptions = computed(() => names.value.map((value) => ({ value, label: value })));
const chosen = computed(() => playbooks.catalogue.find((x) => x.key === playbook.value));
const expected = computed(() => `${playbook.value}:${names.value.length}`);
const canSubmit = computed(
	() =>
		!!playbook.value &&
		names.value.includes(canary.value) &&
		(chosen.value?.risk !== "high" || confirm.value === expected.value)
);
async function submit(): Promise<void> {
	if (!canSubmit.value) return;
	const name = await bulk.create({
		playbook: playbook.value,
		targets: names.value.map((target_name) => ({ target_doctype: "Site", target_name })),
		canary_target: { target_doctype: "Site", target_name: canary.value },
		batch_size: Number(batchSize.value),
		failure_policy: failurePolicy.value as "halt" | "continue",
		params: {},
		...(confirm.value ? { confirm: confirm.value } : {}),
	});
	if (name) creating.value = false;
}
onMounted(() => {
	bulk.subscribe();
	void bulk.fetchList();
	void playbooks.fetchAll();
});
watch(
	() => bulk.selected,
	(name) => {
		if (name && !bulk.details[name]) void bulk.fetchDetail(name);
	}
);
watch(names, (value) => {
	if (!value.includes(canary.value)) canary.value = value[0] ?? "";
});
</script>

<template>
	<div class="flex flex-col gap-6">
		<IcPageHeader
			title="Bulk rollouts"
			subtitle="Backup first, prove the canary, then advance through controlled batches."
		>
			<template #actions
				><IcButton variant="primary" @click="creating = !creating">{{
					creating ? "Close" : "New rollout"
				}}</IcButton></template
			>
		</IcPageHeader>
		<IcCard v-if="creating" title="Create rollout" data-testid="bulk-create">
			<form class="grid gap-4 md:grid-cols-2" @submit.prevent="submit">
				<IcField label="Playbook" required
					><IcSelect
						v-model="playbook"
						:options="playbookOptions"
						placeholder="Choose action"
				/></IcField>
				<IcField label="Canary" required
					><IcSelect
						v-model="canary"
						:options="canaryOptions"
						placeholder="Add targets first"
				/></IcField>
				<IcField
					class="md:col-span-2"
					label="Target sites"
					required
					hint="One site per line or comma-separated."
				>
					<textarea
						v-model="targetText"
						class="min-h-28 w-full rounded border border-line-strong bg-surface-2 p-2.5 font-mono text-sm text-fg"
						placeholder="site-a.example.com&#10;site-b.example.com"
					/>
				</IcField>
				<IcField label="Batch size" required
					><IcInput v-model="batchSize" type="number"
				/></IcField>
				<IcField label="Failure policy" required
					><IcSelect
						v-model="failurePolicy"
						:options="[
							{ value: 'halt', label: 'Halt on first failure' },
							{ value: 'continue', label: 'Continue on failure' },
						]"
				/></IcField>
				<IcField
					v-if="chosen?.risk === 'high'"
					class="md:col-span-2"
					label="Typed confirmation"
					:hint="'Type ' + expected"
					required
					><IcInput v-model="confirm" mono
				/></IcField>
				<div class="flex items-center gap-3 md:col-span-2">
					<IcButton
						type="submit"
						variant="primary"
						:disabled="!canSubmit"
						:loading="bulk.loading"
						>Start rollout</IcButton
					><span class="text-xs text-fg-subtle">{{ names.length }} targets</span>
				</div>
			</form>
		</IcCard>
		<IcCard v-if="bulk.error" :padded="false"
			><ErrorState :error="bulk.error" @retry="bulk.fetchList()"
		/></IcCard>
		<div v-else-if="bulk.loading && !bulk.items.length" class="grid gap-4 lg:grid-cols-3">
			<IcSkeleton v-for="i in 3" :key="i" variant="block" />
		</div>
		<IcEmptyState
			v-else-if="!bulk.items.length"
			title="No rollouts yet"
			description="Create a rollout to run a playbook safely across multiple sites."
		/>
		<div v-else class="grid gap-5 xl:grid-cols-[22rem_1fr]">
			<IcCard title="Operations" :padded="false">
				<button
					v-for="item in bulk.items"
					:key="item.name"
					class="flex w-full flex-col gap-2 border-b border-line p-4 text-start hover:bg-surface-2"
					:class="{ 'bg-surface-2': bulk.selected === item.name }"
					@click="bulk.fetchDetail(item.name)"
				>
					<span class="flex items-center justify-between gap-2"
						><span class="font-mono text-xs">{{ item.name }}</span
						><IcStatusBadge entity="bulk" :status="item.status"
					/></span>
					<span class="text-sm font-medium">{{ item.playbook_title }}</span>
					<IcProgress
						:value="item.total ? (item.done / item.total) * 100 : 0"
						:label="item.name + ' progress'"
					/>
					<span class="text-2xs text-fg-subtle"
						>{{ item.done }}/{{ item.total }} ·
						{{ relativeTime(item.created_at) }}</span
					>
				</button>
				<div v-if="bulk.nextCursor" class="p-3">
					<IcButton size="sm" @click="bulk.fetchList(bulk.nextCursor ?? undefined)"
						>Load more</IcButton
					>
				</div>
			</IcCard>
			<IcCard v-if="detail" :title="detail.playbook_title" :subtitle="detail.name">
				<div class="mb-5 flex flex-wrap items-center gap-2">
					<IcStatusBadge entity="bulk" :status="detail.status" /><span
						class="text-xs text-fg-subtle"
						>Phase {{ detail.phase }} · batch {{ detail.current_batch }}/{{
							detail.batches_total
						}}</span
					>
					<div class="ms-auto flex gap-2">
						<IcButton
							v-if="['Queued', 'Running'].includes(detail.status)"
							size="sm"
							@click="bulk.action('pause', detail.name)"
							>Pause</IcButton
						>
						<IcButton
							v-if="['Paused', 'Halted'].includes(detail.status)"
							size="sm"
							@click="bulk.action('resume', detail.name)"
							>Resume</IcButton
						>
						<IcButton
							v-if="
								['Queued', 'Running', 'Paused', 'Halted'].includes(detail.status)
							"
							size="sm"
							variant="danger"
							@click="bulk.action('cancel', detail.name)"
							>Cancel</IcButton
						>
					</div>
				</div>
				<div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3" data-testid="bulk-targets">
					<div
						v-for="target in detail.targets"
						:key="target.target_name"
						class="rounded border border-line bg-surface-2 p-3"
					>
						<span class="flex items-center justify-between gap-2"
							><span class="truncate font-mono text-xs">{{
								target.target_name
							}}</span
							><IcStatusBadge entity="bulkTarget" :status="target.status"
						/></span>
						<span class="mt-2 block text-2xs text-fg-subtle"
							>{{ target.batch === 0 ? "Canary" : "Batch " + target.batch
							}}<span v-if="target.job"> · {{ target.job }}</span></span
						>
					</div>
				</div>
			</IcCard>
		</div>
	</div>
</template>
