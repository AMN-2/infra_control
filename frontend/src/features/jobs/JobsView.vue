<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import {
	IcBadge,
	IcButton,
	IcCard,
	IcEmptyState,
	IcField,
	IcInput,
	IcPageHeader,
	IcProgress,
	IcSelect,
	IcSkeleton,
	IcStat,
	IcStatusBadge,
} from "@/design/components";
import ErrorState from "@/features/system/ErrorState.vue";
import { relativeTime, secondsSince } from "@/lib/time";
import { useJobsStore, type Job } from "@/stores/jobs";

/**
 * Jobs: a live strip of what is in flight, then history. One table keeps row semantics
 * (deep links, keyboard, tests); groups separate live from finished work. Filters come from
 * the URL so a filtered view can be shared.
 */
const jobs = useJobsStore();
const route = useRoute();
const router = useRouter();

const STATUSES = ["Running", "Queued", "Failed", "Success", "Cancelled"] as const;
const status = computed(() => (typeof route.query.status === "string" ? route.query.status : ""));
const targetType = computed(() =>
	typeof route.query.target_doctype === "string" ? route.query.target_doctype : ""
);
const search = ref("");
const now = ref(Date.now());
let clock: ReturnType<typeof setInterval> | undefined;

function query(): Parameters<typeof jobs.fetchList>[0] {
	return {
		...(status.value ? { status: status.value as Job["status"] } : {}),
		...(targetType.value ? { target_doctype: targetType.value as Job["target_doctype"] } : {}),
	};
}
function load(): void {
	void jobs.fetchList(query());
}
function setFilter(key: "status" | "target_doctype", v: string): void {
	void router.replace({ query: { ...route.query, [key]: v || undefined } });
}
onMounted(() => {
	jobs.subscribe();
	load();
	clock = setInterval(() => (now.value = Date.now()), 1000);
});
onBeforeUnmount(() => {
	clearInterval(clock);
});
watch([status, targetType], load);

const counts = computed(() => {
	const c: Record<string, number> = {
		Running: 0,
		Queued: 0,
		Failed: 0,
		Success: 0,
		Cancelled: 0,
	};
	for (const j of jobs.items) c[j.status] = (c[j.status] ?? 0) + 1;
	return c;
});
const filtered = computed(() => {
	const q = search.value.trim().toLowerCase();
	if (!q) return jobs.items;
	return jobs.items.filter((j) =>
		[j.name, j.playbook_title, j.playbook, j.target_name, j.triggered_by].some((v) =>
			String(v ?? "")
				.toLowerCase()
				.includes(q)
		)
	);
});
const order: Record<Job["status"], number> = {
	Running: 0,
	Queued: 1,
	Failed: 2,
	Success: 3,
	Cancelled: 4,
};
const live = computed(() =>
	filtered.value
		.filter((j) => j.status === "Running" || j.status === "Queued")
		.sort(
			(a, b) => order[a.status] - order[b.status] || b.created_at.localeCompare(a.created_at)
		)
);
const history = computed(() =>
	filtered.value
		.filter((j) => j.status !== "Running" && j.status !== "Queued")
		.sort((a, b) => b.created_at.localeCompare(a.created_at))
);

function duration(j: Job): string {
	const start = j.started_at ?? j.created_at;
	const end = j.ended_at ? Date.parse(j.ended_at) : now.value;
	const s = Math.max(0, Math.round((end - Date.parse(start)) / 1000));
	if (!j.started_at && !j.ended_at) return "waiting";
	if (s < 60) return `${s}s`;
	if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
	return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}
function elapsed(j: Job): number {
	return secondsSince(j.started_at ?? j.created_at, now.value) ?? 0;
}
function targetTo(j: Job): string | null {
	if (j.target_doctype === "Server") return `/servers/${encodeURIComponent(j.target_name)}`;
	if (j.target_doctype === "Site") return `/sites/${encodeURIComponent(j.target_name)}`;
	return null;
}
function progressTone(j: Job): "down" | "healthy" | "running" | "neutral" {
	if (j.status === "Failed") return "down";
	if (j.status === "Success") return "healthy";
	if (j.status === "Cancelled") return "neutral";
	return "running";
}
const doctypeTone = {
	Server: "running",
	Site: "healthy",
	Bench: "degraded",
	"Provider Account": "neutral",
} as const;
</script>

<template>
	<div class="flex flex-col gap-5">
		<IcPageHeader
			title="Jobs"
			subtitle="Everything that touches a server runs as a job: audited, locked per server, streamed live."
		>
			<template #actions>
				<IcBadge v-if="live.length" tone="running" dot live data-testid="jobs-live-count"
					>{{ live.length }} in flight</IcBadge
				>
			</template>
		</IcPageHeader>

		<div class="grid grid-cols-2 gap-3 md:grid-cols-5" data-testid="jobs-stats">
			<button
				v-for="s in STATUSES"
				:key="s"
				type="button"
				class="rounded border text-start transition-colors"
				:class="
					status === s ? 'border-accent bg-surface-2' : 'border-line hover:bg-surface-2'
				"
				:aria-pressed="status === s"
				:data-testid="`jobs-stat-${s}`"
				@click="setFilter('status', status === s ? '' : s)"
			>
				<IcStat
					:label="s"
					:value="counts[s] ?? 0"
					:tone="
						s === 'Running'
							? 'running'
							: s === 'Failed'
								? 'down'
								: s === 'Success'
									? 'healthy'
									: 'neutral'
					"
					:animate="false"
				/>
			</button>
		</div>

		<div class="flex flex-wrap items-end gap-3">
			<IcField for-id="jobs-search" label="Search" class="min-w-64 flex-1">
				<IcInput
					id="jobs-search"
					v-model="search"
					type="search"
					mono
					placeholder="job id, playbook, target, user…"
					data-testid="jobs-search"
				/>
			</IcField>
			<IcField for-id="jobs-status" label="Status">
				<IcSelect
					id="jobs-status"
					:model-value="status"
					:options="STATUSES.map((s) => ({ value: s, label: s }))"
					placeholder="All statuses"
					@update:model-value="(v: string) => setFilter('status', v)"
				/>
			</IcField>
			<IcField for-id="jobs-target" label="Target type">
				<IcSelect
					id="jobs-target"
					:model-value="targetType"
					:options="
						['Server', 'Site', 'Bench', 'Provider Account'].map((s) => ({
							value: s,
							label: s,
						}))
					"
					placeholder="Any"
					@update:model-value="(v: string) => setFilter('target_doctype', v)"
				/>
			</IcField>
			<IcButton
				v-if="status || targetType || search"
				size="sm"
				variant="ghost"
				@click="
					search = '';
					router.replace({ query: {} });
				"
				>Clear</IcButton
			>
		</div>

		<IcCard v-if="jobs.error && !jobs.items.length" :padded="false"
			><ErrorState :error="jobs.error" @retry="load"
		/></IcCard>
		<div v-else-if="jobs.loading && !jobs.items.length" class="flex flex-col gap-2">
			<IcSkeleton v-for="i in 4" :key="i" variant="block" />
		</div>
		<IcEmptyState
			v-else-if="!live.length && !history.length"
			title="No jobs"
			:description="
				status || targetType || search
					? 'Nothing matches these filters.'
					: 'Run a playbook from a server or site; every job lands here.'
			"
		/>
		<IcCard v-else :padded="false">
			<div class="overflow-x-auto">
				<table class="w-full border-collapse text-sm" data-testid="jobs-table">
					<thead>
						<tr class="border-b border-line">
							<th scope="col" class="eyebrow px-4 py-2.5 text-start font-medium">
								Job
							</th>
							<th scope="col" class="eyebrow px-4 py-2.5 text-start font-medium">
								Playbook
							</th>
							<th scope="col" class="eyebrow px-4 py-2.5 text-start font-medium">
								Target
							</th>
							<th scope="col" class="eyebrow px-4 py-2.5 text-start font-medium">
								Status
							</th>
							<th
								scope="col"
								class="eyebrow px-4 py-2.5 text-start font-medium"
								style="inline-size: 12rem"
							>
								Progress
							</th>
							<th scope="col" class="eyebrow px-4 py-2.5 text-end font-medium">
								Duration
							</th>
							<th scope="col" class="eyebrow px-4 py-2.5 text-start font-medium">
								By
							</th>
							<th scope="col" class="eyebrow px-4 py-2.5 text-end font-medium">
								Created
							</th>
						</tr>
					</thead>
					<tbody>
						<template v-if="live.length">
							<tr class="bg-surface-2/60">
								<th
									scope="rowgroup"
									colspan="8"
									class="px-4 py-1.5 text-start text-2xs font-medium tracking-wide text-fg-subtle uppercase"
								>
									In flight
								</th>
							</tr>
							<tr
								v-for="j in live"
								:key="j.name"
								class="cursor-pointer border-b border-line hover:bg-surface-2"
								:class="{ 'ic-glow': j.status === 'Running' }"
								role="row"
								tabindex="0"
								:aria-label="`${j.name} ${j.playbook_title} ${j.target_name}`"
								@click="router.push(`/jobs/${encodeURIComponent(j.name)}`)"
								@keydown.enter="router.push(`/jobs/${encodeURIComponent(j.name)}`)"
							>
								<td class="px-4 py-2.5 font-mono text-xs">{{ j.name }}</td>
								<td class="px-4 py-2.5 font-medium">{{ j.playbook_title }}</td>
								<td class="px-4 py-2.5">
									<span class="flex items-center gap-2"
										><IcBadge
											:tone="doctypeTone[j.target_doctype]"
											uppercase
											>{{ j.target_doctype }}</IcBadge
										><RouterLink
											v-if="targetTo(j)"
											:to="targetTo(j)!"
											class="truncate font-mono text-xs hover:underline"
											@click.stop
											>{{ j.target_name }}</RouterLink
										><span v-else class="truncate font-mono text-xs">{{
											j.target_name
										}}</span></span
									>
								</td>
								<td class="px-4 py-2.5">
									<IcStatusBadge entity="job" :status="j.status" />
								</td>
								<td class="px-4 py-2.5">
									<IcProgress
										:value="j.progress"
										:tone="progressTone(j)"
										:label="`${j.name} progress`"
										show-value
									/><span class="text-2xs text-fg-subtle"
										>{{ j.steps_done }}/{{ j.steps_total || "?" }} steps</span
									>
								</td>
								<td
									class="px-4 py-2.5 text-end font-mono text-xs"
									:title="`${elapsed(j)} s`"
								>
									{{ duration(j) }}
								</td>
								<td class="px-4 py-2.5 font-mono text-xs text-fg-muted">
									{{ j.triggered_by }}
								</td>
								<td
									class="px-4 py-2.5 text-end text-xs text-fg-subtle"
									:title="j.created_at"
								>
									{{ relativeTime(j.created_at, now) }}
								</td>
							</tr>
						</template>
						<template v-if="history.length">
							<tr v-if="live.length" class="bg-surface-2/60">
								<th
									scope="rowgroup"
									colspan="8"
									class="px-4 py-1.5 text-start text-2xs font-medium tracking-wide text-fg-subtle uppercase"
								>
									History
								</th>
							</tr>
							<tr
								v-for="j in history"
								:key="j.name"
								class="cursor-pointer border-b border-line hover:bg-surface-2"
								:class="{ 'opacity-70': j.status === 'Cancelled' }"
								role="row"
								tabindex="0"
								:aria-label="`${j.name} ${j.playbook_title} ${j.target_name}`"
								@click="router.push(`/jobs/${encodeURIComponent(j.name)}`)"
								@keydown.enter="router.push(`/jobs/${encodeURIComponent(j.name)}`)"
							>
								<td class="px-4 py-2.5 font-mono text-xs">{{ j.name }}</td>
								<td class="px-4 py-2.5">
									{{ j.playbook_title
									}}<span
										v-if="j.error"
										class="block max-w-md truncate text-2xs text-down"
										:title="j.error"
										>{{ j.error }}</span
									>
								</td>
								<td class="px-4 py-2.5">
									<span class="flex items-center gap-2"
										><IcBadge
											:tone="doctypeTone[j.target_doctype]"
											uppercase
											>{{ j.target_doctype }}</IcBadge
										><RouterLink
											v-if="targetTo(j)"
											:to="targetTo(j)!"
											class="truncate font-mono text-xs hover:underline"
											@click.stop
											>{{ j.target_name }}</RouterLink
										><span v-else class="truncate font-mono text-xs">{{
											j.target_name
										}}</span></span
									>
								</td>
								<td class="px-4 py-2.5">
									<IcStatusBadge entity="job" :status="j.status" />
								</td>
								<td class="px-4 py-2.5">
									<IcProgress
										:value="j.progress"
										:tone="progressTone(j)"
										:label="`${j.name} progress`"
									/><span class="text-2xs text-fg-subtle"
										>{{ j.steps_done }}/{{ j.steps_total || "?" }} steps</span
									>
								</td>
								<td class="px-4 py-2.5 text-end font-mono text-xs">
									{{ duration(j) }}
								</td>
								<td class="px-4 py-2.5 font-mono text-xs text-fg-muted">
									{{ j.triggered_by }}
								</td>
								<td
									class="px-4 py-2.5 text-end text-xs text-fg-subtle"
									:title="j.created_at"
								>
									{{ relativeTime(j.created_at, now) }}
								</td>
							</tr>
						</template>
					</tbody>
				</table>
			</div>
			<template v-if="jobs.nextCursor" #footer>
				<div class="flex justify-center">
					<IcButton
						variant="ghost"
						size="sm"
						:loading="jobs.loading"
						data-testid="jobs-more"
						@click="jobs.fetchList(query(), jobs.nextCursor ?? undefined)"
						>Load older jobs</IcButton
					>
				</div>
			</template>
		</IcCard>
	</div>
</template>
