<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import {
	IcBadge,
	IcCard,
	IcEmptyState,
	IcMetricChip,
	IcPageHeader,
	IcProgress,
	IcProviderBadge,
	IcSkeleton,
	IcSparkline,
	IcStatusBadge,
	IcTable,
	IcTabs,
	type Column,
	type TabItem,
} from "@/design/components";
import { providerLabel } from "@/design/status";
import TargetActions from "@/features/jobs/TargetActions.vue";
import ErrorState from "@/features/system/ErrorState.vue";
import { relativeTime } from "@/lib/time";
import { useInventoryStore, type Bench } from "@/stores/inventory";
import { useJobsStore, type Job } from "@/stores/jobs";

/**
 * Server detail (plan §10.2): metrics, benches, job history, capability-driven actions.
 * Metrics update in place from `infra:server.heartbeat`; the session trend feeds sparklines
 * until the real metric series arrives in B3.1.
 */
const route = useRoute();
const router = useRouter();
const inventory = useInventoryStore();
const jobs = useJobsStore();

const name = computed(() => String(route.params.name ?? ""));
const server = computed(() => inventory.serverDetails[name.value]);
const history = computed(() => inventory.metricHistory[name.value] ?? []);
const now = ref(Date.now());

function load(): void {
	void inventory.fetchServer(name.value);
	void jobs.fetchList({ target_doctype: "Server", target_name: name.value });
}
onMounted(() => {
	inventory.subscribe();
	jobs.subscribe();
	load();
});
watch(name, load);
watch(
	() => server.value?.latest_metrics?.ts,
	() => {
		now.value = Date.now();
	}
);

const tab = ref("benches");
const tabs = computed<TabItem[]>(() => [
	{ id: "benches", label: "Benches", count: server.value?.benches.length },
	{ id: "jobs", label: "Jobs", count: jobHistory.value.length },
	{ id: "details", label: "Details" },
]);
const jobHistory = computed<Job[]>(() =>
	jobs.items.filter((j) => j.target_doctype === "Server" && j.target_name === name.value)
);

type BenchRow = Bench & { apps_label: string };
const benchRows = computed<BenchRow[]>(() =>
	(server.value?.benches ?? []).map((b) => ({
		...b,
		apps_label: b.apps.map((a) => a.app).join(", "),
	}))
);
const benchColumns: Column<BenchRow>[] = [
	{ key: "title", label: "Bench", mono: true },
	{ key: "frappe_version", label: "Frappe", mono: true },
	{ key: "apps_label", label: "Apps" },
	{ key: "site_count", label: "Sites", align: "end" },
];
type JobRow = Job & { when: string };
const jobRows = computed<JobRow[]>(() =>
	jobHistory.value.map((j) => ({ ...j, when: relativeTime(j.created_at, now.value) }))
);
const jobColumns: Column<JobRow>[] = [
	{ key: "name", label: "Job", mono: true },
	{ key: "playbook_title", label: "Playbook" },
	{ key: "status", label: "Status" },
	{ key: "progress", label: "Progress", width: "10rem" },
	{ key: "triggered_by", label: "By", mono: true },
	{ key: "when", label: "Created", align: "end" },
];
const series = computed(() => ({
	cpu: history.value.map((h) => h.cpu),
	ram: history.value.map((h) => h.ram),
	disk: history.value.map((h) => h.disk),
}));
</script>

<template>
	<div class="flex flex-col gap-6">
		<IcCard v-if="inventory.error && !server" :padded="false">
			<ErrorState
				:error="inventory.error"
				:title="inventory.error.status === 404 ? 'Server not found' : undefined"
				@retry="load"
			/>
		</IcCard>

		<template v-else-if="!server">
			<IcSkeleton :lines="2" />
			<div class="grid gap-3 md:grid-cols-3" data-testid="server-loading">
				<IcSkeleton v-for="i in 3" :key="i" variant="block" />
			</div>
		</template>

		<template v-else>
			<IcPageHeader
				:title="server.hostname"
				mono
				:crumbs="[{ label: 'Servers', to: '/servers' }, { label: server.hostname }]"
				:subtitle="`${providerLabel[server.provider].long} · ${server.region} · ${server.size} · role ${server.role}${server.public_ip ? ` · ${server.public_ip}` : ''}`"
			>
			</IcPageHeader>
			<div class="-mt-4 flex flex-wrap items-center gap-2" data-testid="server-badges">
				<IcStatusBadge entity="server" :status="server.status" />
				<IcProviderBadge :provider="server.provider" long />
				<IcBadge v-for="t in server.tags" :key="t" mono>{{ t }}</IcBadge>
				<RouterLink
					v-if="server.running_job"
					:to="`/jobs/${encodeURIComponent(server.running_job)}`"
				>
					<IcBadge tone="running" dot live mono>{{ server.running_job }}</IcBadge>
				</RouterLink>
				<span class="ms-auto text-xs text-fg-subtle">
					Heartbeat
					{{
						server.last_heartbeat ? relativeTime(server.last_heartbeat, now) : "never"
					}}
				</span>
			</div>

			<!-- Metrics: live chips and the session trend -->
			<IcCard
				title="Metrics"
				:subtitle="
					server.latest_metrics
						? `Updated ${relativeTime(server.latest_metrics.ts, now)}`
						: 'No readings yet'
				"
				:live="
					!!server.latest_metrics &&
					(server.status === 'Active' || server.status === 'Degraded')
				"
			>
				<IcEmptyState
					v-if="!server.latest_metrics"
					title="No metrics yet"
					description="The collector writes a reading every minute once the server sends heartbeats."
				/>
				<div v-else class="grid gap-4 md:grid-cols-3" data-testid="server-metrics">
					<div
						v-for="m in ['cpu', 'ram', 'disk'] as const"
						:key="m"
						class="flex flex-col gap-2 rounded border border-line bg-surface-2 p-3"
					>
						<IcMetricChip :label="m" :value="server.latest_metrics[m]" />
						<IcSparkline
							v-if="series[m].length >= 2"
							:key="series[m].length"
							:points="series[m]"
							tone="running"
						/>
						<span v-else class="text-2xs text-fg-subtle"
							>Trend appears after two heartbeats</span
						>
					</div>
					<div class="flex flex-wrap gap-2 md:col-span-3">
						<IcMetricChip
							label="load1"
							:value="server.latest_metrics.load1"
							unit=""
							:warn="4"
							:crit="8"
						/>
						<IcMetricChip
							label="queue backlog"
							:value="server.latest_metrics.queue_backlog"
							unit=""
							:warn="100"
							:crit="500"
						/>
					</div>
				</div>
			</IcCard>

			<TargetActions
				target-doctype="Server"
				:target-name="server.name"
				:target-label="server.hostname"
				:capabilities="server.capabilities"
				:running-job="server.running_job"
			/>

			<IcCard :padded="false">
				<template #header>
					<IcTabs v-model="tab" :tabs="tabs" label="Server sections" />
				</template>
				<div v-if="tab === 'benches'" id="panel-benches" role="tabpanel">
					<IcTable
						:columns="benchColumns"
						:rows="benchRows"
						row-key="name"
						clickable
						empty-title="No benches"
						empty-description="Benches appear after inventory.sync or server.provision."
						@row-click="
							(b: BenchRow) =>
								router.push({ path: '/sites', query: { bench: b.name } })
						"
					/>
				</div>
				<div v-else-if="tab === 'jobs'" id="panel-jobs" role="tabpanel">
					<IcTable
						:columns="jobColumns"
						:rows="jobRows"
						row-key="name"
						:loading="jobs.loading && !jobRows.length"
						clickable
						empty-title="No jobs yet"
						empty-description="Every action on this server is recorded here."
						@row-click="
							(j: JobRow) => router.push(`/jobs/${encodeURIComponent(j.name)}`)
						"
					>
						<template #cell-status="{ row }">
							<IcStatusBadge entity="job" :status="row.status" />
						</template>
						<template #cell-progress="{ row }">
							<IcProgress
								:value="row.progress"
								:tone="
									row.status === 'Failed'
										? 'down'
										: row.status === 'Success'
											? 'healthy'
											: 'running'
								"
								:label="`${row.name} progress`"
							/>
						</template>
					</IcTable>
				</div>
				<dl
					v-else
					id="panel-details"
					role="tabpanel"
					class="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 p-5 text-sm"
					data-testid="server-details"
				>
					<dt class="text-fg-muted">Name</dt>
					<dd class="font-mono">{{ server.name }}</dd>
					<dt class="text-fg-muted">Provider ref</dt>
					<dd class="font-mono">{{ server.provider_ref || "—" }}</dd>
					<dt class="text-fg-muted">Account</dt>
					<dd class="font-mono">{{ server.provider_account }}</dd>
					<dt class="text-fg-muted">Public IP</dt>
					<dd class="font-mono">{{ server.public_ip ?? "—" }}</dd>
					<dt class="text-fg-muted">Private IP</dt>
					<dd class="font-mono">{{ server.private_ip ?? "—" }}</dd>
					<dt class="text-fg-muted">Capabilities</dt>
					<dd class="flex flex-wrap gap-1">
						<IcBadge v-for="c in server.capabilities" :key="c" mono>{{ c }}</IcBadge>
					</dd>
				</dl>
			</IcCard>
		</template>
	</div>
</template>
