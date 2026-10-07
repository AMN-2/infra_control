<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import {
	IcBadge,
	IcCard,
	IcPageHeader,
	IcProgress,
	IcProviderBadge,
	IcSkeleton,
	IcStat,
	IcStatusBadge,
	IcTable,
	IcTabs,
	type Column,
	type TabItem,
} from "@/design/components";
import { providerLabel, type Tone } from "@/design/status";
import TargetActions from "@/features/jobs/TargetActions.vue";
import ErrorState from "@/features/system/ErrorState.vue";
import { relativeTime } from "@/lib/time";
import type { components } from "@/api/schema";
import { useInventoryStore } from "@/stores/inventory";
import { useJobsStore, type Job } from "@/stores/jobs";

type Backup = components["schemas"]["Backup"];

/** Site detail (plan §10.2): status, domains, backups, job history, capability-driven actions. */
const route = useRoute();
const router = useRouter();
const inventory = useInventoryStore();
const jobs = useJobsStore();

const name = computed(() => String(route.params.name ?? ""));
const site = computed(() => inventory.siteDetails[name.value]);
const now = ref(Date.now());

function load(): void {
	now.value = Date.now();
	void inventory.fetchSite(name.value);
	void jobs.fetchList({ target_doctype: "Site", target_name: name.value });
}
onMounted(() => {
	inventory.subscribe();
	jobs.subscribe();
	load();
});
watch(name, load);

const DAY = 86_400_000;
/** SSL: red when expired or inside 7 days, amber inside 30. */
const sslTone = computed<Tone>(() => {
	const t = site.value?.ssl_expiry ? Date.parse(site.value.ssl_expiry) : NaN;
	if (Number.isNaN(t)) return "neutral";
	const left = t - now.value;
	if (left < 7 * DAY) return "down";
	if (left < 30 * DAY) return "degraded";
	return "healthy";
});
/** Backups: amber when older than a day, red when older than three or never. */
const backupTone = computed<Tone>(() => {
	const t = site.value?.last_backup ? Date.parse(site.value.last_backup) : NaN;
	if (Number.isNaN(t)) return "down";
	const age = now.value - t;
	if (age > 3 * DAY) return "down";
	if (age > DAY) return "degraded";
	return "healthy";
});
const daysLeft = computed(() => {
	const t = site.value?.ssl_expiry ? Date.parse(site.value.ssl_expiry) : NaN;
	return Number.isNaN(t) ? 0 : Math.max(0, Math.round((t - now.value) / DAY));
});

const tab = ref("backups");
const jobHistory = computed<Job[]>(() =>
	jobs.items.filter((j) => j.target_doctype === "Site" && j.target_name === name.value)
);
const tabs = computed<TabItem[]>(() => [
	{ id: "backups", label: "Backups", count: site.value?.backups.length },
	{ id: "jobs", label: "Jobs", count: jobHistory.value.length },
	{ id: "bench", label: "Bench" },
]);

type BackupRow = Backup & { when: string; size: string; restore: string };
const backupRows = computed<BackupRow[]>(() =>
	(site.value?.backups ?? []).map((b) => ({
		...b,
		when: relativeTime(b.created_at, now.value),
		size: `${Math.round(b.size_mb)} MB`,
		restore:
			b.restore_test_ok === null
				? "never tested"
				: b.restore_test_ok
					? `ok ${b.last_restore_test ? relativeTime(b.last_restore_test, now.value) : ""}`
					: "failed",
	}))
);
const backupColumns: Column<BackupRow>[] = [
	{ key: "name", label: "Backup", mono: true },
	{ key: "kind", label: "Kind" },
	{ key: "size", label: "Size", align: "end" },
	{ key: "location", label: "Location", mono: true },
	{ key: "restore", label: "Restore test" },
	{ key: "when", label: "Created", align: "end" },
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
</script>

<template>
	<div class="flex flex-col gap-6">
		<IcCard v-if="inventory.error && !site" :padded="false">
			<ErrorState
				:error="inventory.error"
				:title="inventory.error.status === 404 ? 'Site not found' : undefined"
				@retry="load"
			/>
		</IcCard>

		<template v-else-if="!site">
			<IcSkeleton :lines="2" />
			<div class="grid gap-3 md:grid-cols-3" data-testid="site-loading">
				<IcSkeleton v-for="i in 3" :key="i" variant="block" />
			</div>
		</template>

		<template v-else>
			<IcPageHeader
				:title="site.domain"
				mono
				:crumbs="[{ label: 'Sites', to: '/sites' }, { label: site.domain }]"
				:subtitle="`${providerLabel[site.provider].long} · bench ${site.bench_info.title}${site.plan ? ` · plan ${site.plan}` : ''}`"
			/>
			<div class="-mt-4 flex flex-wrap items-center gap-2" data-testid="site-badges">
				<IcStatusBadge entity="site" :status="site.status" />
				<IcProviderBadge :provider="site.provider" long />
				<RouterLink v-if="site.server" :to="`/servers/${encodeURIComponent(site.server)}`">
					<IcBadge mono>{{ site.server }}</IcBadge>
				</RouterLink>
				<RouterLink
					v-if="site.running_job"
					:to="`/jobs/${encodeURIComponent(site.running_job)}`"
				>
					<IcBadge tone="running" dot live mono>{{ site.running_job }}</IcBadge>
				</RouterLink>
			</div>

			<div class="grid gap-3 md:grid-cols-3" data-testid="site-facts">
				<IcStat
					label="SSL days left"
					:value="daysLeft"
					:tone="sslTone"
					:note="
						site.ssl_expiry
							? `expires ${relativeTime(site.ssl_expiry, now)}`
							: 'no certificate recorded'
					"
				/>
				<IcStat
					label="Database"
					:value="Math.round(site.db_size_mb ?? 0)"
					tone="neutral"
					:note="site.db_size_mb === null ? 'size unknown' : 'MB'"
				/>
				<IcStat
					label="Backups"
					:value="site.backups.length"
					:tone="backupTone"
					:note="
						site.last_backup
							? `last ${relativeTime(site.last_backup, now)}`
							: 'never backed up'
					"
				/>
			</div>

			<IcCard title="Domains" :subtitle="`${1 + site.custom_domains.length} total`">
				<ul class="flex flex-wrap gap-2" data-testid="site-domains">
					<li>
						<IcBadge tone="healthy" dot mono>{{ site.domain }}</IcBadge>
					</li>
					<li v-for="d in site.custom_domains" :key="d">
						<IcBadge mono>{{ d }}</IcBadge>
					</li>
				</ul>
			</IcCard>

			<TargetActions
				target-doctype="Site"
				:target-name="site.name"
				:target-label="site.domain"
				:capabilities="site.capabilities"
				:running-job="site.running_job"
			/>

			<IcCard :padded="false">
				<template #header>
					<IcTabs v-model="tab" :tabs="tabs" label="Site sections" />
				</template>
				<div v-if="tab === 'backups'" id="panel-backups" role="tabpanel">
					<IcTable
						:columns="backupColumns"
						:rows="backupRows"
						row-key="name"
						empty-title="No backups yet"
						empty-description="Run site.backup, or wait for the scheduled one."
					>
						<template #cell-restore="{ row }">
							<span
								:class="
									row.restore_test_ok === null
										? 'text-fg-subtle'
										: row.restore_test_ok
											? 'text-healthy'
											: 'text-down'
								"
								>{{ row.restore }}</span
							>
						</template>
					</IcTable>
				</div>
				<div v-else-if="tab === 'jobs'" id="panel-jobs" role="tabpanel">
					<IcTable
						:columns="jobColumns"
						:rows="jobRows"
						row-key="name"
						:loading="jobs.loading && !jobRows.length"
						clickable
						empty-title="No jobs yet"
						empty-description="Every action on this site is recorded here."
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
					id="panel-bench"
					role="tabpanel"
					class="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 p-5 text-sm"
					data-testid="site-bench"
				>
					<dt class="text-fg-muted">Bench</dt>
					<dd class="font-mono">
						<RouterLink :to="{ path: '/sites', query: { bench: site.bench } }">{{
							site.bench_info.title
						}}</RouterLink>
					</dd>
					<dt class="text-fg-muted">Frappe</dt>
					<dd class="font-mono">{{ site.bench_info.frappe_version ?? "—" }}</dd>
					<dt class="text-fg-muted">Path</dt>
					<dd class="font-mono">{{ site.bench_info.path ?? "—" }}</dd>
					<dt class="text-fg-muted">Apps</dt>
					<dd class="flex flex-wrap gap-1">
						<IcBadge v-for="a in site.bench_info.apps" :key="a.app" mono>
							{{ a.app }}{{ a.version ? ` ${a.version}` : "" }}
						</IcBadge>
					</dd>
					<dt class="text-fg-muted">Provider ref</dt>
					<dd class="font-mono break-all">{{ site.provider_ref }}</dd>
					<dt class="text-fg-muted">Capabilities</dt>
					<dd class="flex flex-wrap gap-1">
						<IcBadge v-for="c in site.capabilities" :key="c" mono>{{ c }}</IcBadge>
					</dd>
				</dl>
			</IcCard>
		</template>
	</div>
</template>
