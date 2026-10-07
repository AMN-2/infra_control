<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
	IcButton,
	IcCard,
	IcPageHeader,
	IcProgress,
	IcSelect,
	IcStatusBadge,
	IcTable,
	type Column,
} from "@/design/components";
import ErrorState from "@/features/system/ErrorState.vue";
import { relativeTime } from "@/lib/time";
import { useJobsStore, type Job } from "@/stores/jobs";

/** Jobs list: running first, filter by status from the query, cursor paging. */
const jobs = useJobsStore();
const route = useRoute();
const router = useRouter();

const statusOptions = ["Queued", "Running", "Success", "Failed", "Cancelled"].map((s) => ({
	value: s,
	label: s,
}));
const status = computed(() => {
	const s = route.query.status;
	return typeof s === "string" ? s : "";
});
const now = ref(Date.now());
let clock: ReturnType<typeof setInterval> | undefined;

function query(): { status?: Job["status"] } {
	return status.value ? { status: status.value as Job["status"] } : {};
}
function load(): void {
	void jobs.fetchList(query());
}
onMounted(() => {
	jobs.subscribe();
	load();
	clock = setInterval(() => {
		now.value = Date.now();
	}, 30_000);
});
onBeforeUnmount(() => {
	clearInterval(clock);
});
watch(status, load);

function setStatus(v: string): void {
	void router.replace({ query: { ...route.query, status: v || undefined } });
}

type Row = Job & { when: string; target: string };
const order: Record<Job["status"], number> = {
	Running: 0,
	Queued: 1,
	Failed: 2,
	Success: 3,
	Cancelled: 4,
};
const rows = computed<Row[]>(() =>
	[...jobs.items]
		.sort(
			(a, b) => order[a.status] - order[b.status] || b.created_at.localeCompare(a.created_at)
		)
		.map((j) => ({
			...j,
			when: relativeTime(j.created_at, now.value),
			target: `${j.target_doctype} · ${j.target_name}`,
		}))
);
const columns: Column<Row>[] = [
	{ key: "name", label: "Job", mono: true },
	{ key: "playbook_title", label: "Playbook" },
	{ key: "target", label: "Target", mono: true },
	{ key: "status", label: "Status" },
	{ key: "progress", label: "Progress", width: "11rem" },
	{ key: "triggered_by", label: "By", mono: true },
	{ key: "when", label: "Created", align: "end" },
];
function progressTone(j: Job): "down" | "healthy" | "running" | "neutral" {
	if (j.status === "Failed") return "down";
	if (j.status === "Success") return "healthy";
	if (j.status === "Cancelled") return "neutral";
	return "running";
}
</script>

<template>
	<div class="flex flex-col gap-4">
		<IcPageHeader title="Jobs" :subtitle="`${jobs.running.length} in flight`" />
		<div class="flex flex-wrap items-center gap-3">
			<label class="text-xs text-fg-muted" for="jobs-status">Status</label>
			<div class="w-44">
				<IcSelect
					id="jobs-status"
					:model-value="status"
					:options="statusOptions"
					placeholder="All statuses"
					@update:model-value="setStatus"
				/>
			</div>
		</div>
		<IcCard v-if="jobs.error && !jobs.items.length" :padded="false">
			<ErrorState :error="jobs.error" @retry="load" />
		</IcCard>
		<IcCard v-else :padded="false">
			<IcTable
				:columns="columns"
				:rows="rows"
				row-key="name"
				:loading="jobs.loading && !rows.length"
				clickable
				empty-title="No jobs"
				:empty-description="
					status
						? 'Nothing matches this status.'
						: 'Run a playbook from a server or site; every job lands here.'
				"
				@row-click="(r: Row) => router.push(`/jobs/${encodeURIComponent(r.name)}`)"
			>
				<template #cell-status="{ row }">
					<IcStatusBadge entity="job" :status="row.status" />
				</template>
				<template #cell-progress="{ row }">
					<IcProgress
						:value="row.progress"
						:tone="progressTone(row)"
						:label="`${row.name} progress`"
						show-value
					/>
				</template>
			</IcTable>
			<template v-if="jobs.nextCursor" #footer>
				<div class="flex justify-center">
					<IcButton
						variant="ghost"
						size="sm"
						:loading="jobs.loading"
						data-testid="jobs-more"
						@click="jobs.fetchList(query(), jobs.nextCursor ?? undefined)"
					>
						Load older jobs
					</IcButton>
				</div>
			</template>
		</IcCard>
	</div>
</template>
