<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import {
	IcBadge,
	IcButton,
	IcCard,
	IcPageHeader,
	IcProviderBadge,
	IcSkeleton,
	IcStat,
	IcStatusBadge,
	IcTable,
	IcTabs,
	pushToast,
	type Column,
	type TabItem,
} from "@/design/components";
import ErrorState from "@/features/system/ErrorState.vue";
import RunPlaybookDialog from "@/features/jobs/RunPlaybookDialog.vue";
import TargetActions from "@/features/jobs/TargetActions.vue";
import CreateSiteDialog from "@/features/sites/CreateSiteDialog.vue";
import { providerLabel } from "@/design/status";
import { relativeTime } from "@/lib/time";
import { useInventoryStore, type InstalledApp } from "@/stores/inventory";
import { useJobsStore, type Job } from "@/stores/jobs";
import { usePlaybooksStore } from "@/stores/playbooks";
import { useSessionStore } from "@/stores/session";
import SwitchVersionDialog from "./SwitchVersionDialog.vue";
import { newerTag, summarize, updateLabel, updateTone } from "./updates";

/**
 * One bench (ADR 0009): apps with branch, version and commit against upstream, "check for
 * updates", per-app update and version switch (both `bench.update` jobs), the sites on it
 * and its job history. Every mutation is a job through the engine; this screen only reads.
 */
const route = useRoute();
const router = useRouter();
const inventory = useInventoryStore();
const jobs = useJobsStore();
const playbooks = usePlaybooksStore();
const session = useSessionStore();
const name = computed(() => String(route.params.name ?? ""));
const bench = computed(() => inventory.benchDetails[name.value]);
const tab = ref("apps");
const now = ref(Date.now());
const checking = ref(false);
const updateApp = ref<InstalledApp | null>(null);
const switchApp = ref<InstalledApp | null>(null);
const updateOpen = ref(false);
const switchOpen = ref(false);
const createSite = ref(false);
let clock: ReturnType<typeof setInterval> | undefined;

function load(): void {
	void inventory.fetchBench(name.value);
	void jobs.fetchList({ target_doctype: "Bench", target_name: name.value });
	void playbooks.fetchFor("Bench", name.value);
}
onMounted(() => {
	inventory.subscribe();
	jobs.subscribe();
	load();
	clock = setInterval(() => (now.value = Date.now()), 30_000);
});
onBeforeUnmount(() => {
	clearInterval(clock);
});
watch(name, load);

const summary = computed(() => summarize(bench.value?.apps ?? []));
const updatePlaybook = computed(() =>
	(playbooks.forTarget[`Bench:${name.value}`] ?? []).find((p) => p.key === "bench.update")
);
const canUpdate = computed(
	() => session.canOperate && !!updatePlaybook.value && !bench.value?.running_job
);
const hostOf = computed(
	() =>
		inventory.servers.find((s) => s.name === bench.value?.server)?.hostname ??
		bench.value?.server
);

const jobHistory = computed<Job[]>(() =>
	jobs.items.filter((j) => j.target_doctype === "Bench" && j.target_name === name.value)
);
const tabs = computed<TabItem[]>(() => [
	{ id: "apps", label: "Apps", count: bench.value?.apps.length },
	{ id: "sites", label: "Sites", count: bench.value?.sites.length },
	{ id: "jobs", label: "Jobs", count: jobHistory.value.length },
]);

type AppRow = InstalledApp & { newer: string | null; actions: null };
const appRows = computed<AppRow[]>(() =>
	(bench.value?.apps ?? [])
		.map((a) => ({ ...a, newer: newerTag(a), actions: null }))
		.sort((a, b) =>
			a.app === "frappe" ? -1 : b.app === "frappe" ? 1 : a.app.localeCompare(b.app)
		)
);
const appColumns: Column<AppRow>[] = [
	{ key: "app", label: "App" },
	{ key: "branch", label: "Branch" },
	{ key: "version", label: "Version" },
	{ key: "commit", label: "Commit" },
	{ key: "update_state", label: "Upstream" },
	{ key: "actions", label: "", align: "end" },
];
type JobRow = Job & { when: string };
const jobRows = computed<JobRow[]>(() =>
	jobHistory.value.map((j) => ({ ...j, when: relativeTime(j.created_at, now.value) }))
);
const jobColumns: Column<JobRow>[] = [
	{ key: "name", label: "Job", mono: true },
	{ key: "playbook_title", label: "Playbook" },
	{ key: "status", label: "Status" },
	{ key: "triggered_by", label: "By", mono: true },
	{ key: "when", label: "Created", align: "end" },
];

async function check(): Promise<void> {
	if (checking.value) return;
	checking.value = true;
	const d = await inventory.checkBenchUpdates(name.value);
	checking.value = false;
	if (!d) {
		const e = inventory.error;
		pushToast({ title: "Update check failed", description: e?.message ?? "", tone: "down" });
		return;
	}
	const s = summarize(d.apps);
	pushToast({
		title: s.behind ? `${s.behind} app(s) have updates` : "Every app is current",
		description: s.unknown
			? `${s.unknown} app(s) are not on GitHub and were skipped.`
			: undefined,
		tone: s.behind ? "degraded" : "healthy",
	});
}
function openUpdate(a: InstalledApp): void {
	updateApp.value = a;
	updateOpen.value = true;
}
function openSwitch(a: InstalledApp): void {
	switchApp.value = a;
	switchOpen.value = true;
}
</script>

<template>
	<div class="flex flex-col gap-6">
		<IcCard v-if="inventory.error && !bench" :padded="false">
			<ErrorState
				:error="inventory.error"
				:title="inventory.error.status === 404 ? 'Bench not found' : undefined"
				@retry="load"
			/>
		</IcCard>
		<template v-else-if="!bench">
			<IcSkeleton :lines="2" />
			<div class="grid gap-3 md:grid-cols-4" data-testid="bench-loading">
				<IcSkeleton v-for="i in 4" :key="i" variant="block" />
			</div>
		</template>
		<template v-else>
			<IcPageHeader
				:title="bench.title"
				:crumbs="[{ label: 'Benches', to: '/benches' }, { label: bench.title }]"
				:subtitle="`${providerLabel[bench.provider].long}${bench.path ? ` · ${bench.path}` : ''} · Frappe ${bench.frappe_version ?? '?'}`"
			>
				<template #actions>
					<IcButton
						v-if="session.canOperate"
						:loading="checking"
						data-testid="bench-check-updates"
						@click="check"
						>Check for updates</IcButton
					>
					<IcButton
						v-if="session.canOperate && bench.capabilities.includes('site')"
						variant="primary"
						:disabled="!!bench.running_job"
						data-testid="bench-new-site"
						@click="createSite = true"
						>New site</IcButton
					>
				</template>
			</IcPageHeader>
			<div class="-mt-4 flex flex-wrap items-center gap-2" data-testid="bench-badges">
				<IcBadge :tone="updateTone[summary.state]" dot>{{
					summary.state === "update_available"
						? `${summary.behind} app(s) behind upstream`
						: updateLabel[summary.state]
				}}</IcBadge>
				<IcProviderBadge :provider="bench.provider" long />
				<RouterLink
					v-if="bench.server"
					:to="`/servers/${encodeURIComponent(bench.server)}`"
					><IcBadge mono>{{ hostOf }}</IcBadge></RouterLink
				>
				<RouterLink
					v-if="bench.running_job"
					:to="`/jobs/${encodeURIComponent(bench.running_job)}`"
					><IcBadge tone="running" dot live mono>{{
						bench.running_job
					}}</IcBadge></RouterLink
				>
			</div>

			<div class="grid grid-cols-2 gap-3 md:grid-cols-4" data-testid="bench-facts">
				<IcStat
					label="Apps"
					:value="bench.apps.length"
					tone="neutral"
					:note="
						bench.frappe_version ? `Frappe ${bench.frappe_version}` : 'version unknown'
					"
					:animate="false"
				/>
				<IcStat
					label="Updates available"
					:value="summary.behind"
					:tone="summary.behind ? 'degraded' : summary.upToDate ? 'healthy' : 'neutral'"
					:note="summary.unknown ? `${summary.unknown} not checked` : 'all apps checked'"
					:animate="false"
				/>
				<IcStat
					label="Sites"
					:value="bench.sites.length"
					tone="neutral"
					:note="`${bench.sites.filter((s) => s.status === 'Active').length} active`"
					:animate="false"
				/>
				<IcStat
					label="Last check"
					:value="
						summary.lastChecked
							? Math.max(
									0,
									Math.round((now - Date.parse(summary.lastChecked)) / 3_600_000)
								)
							: 0
					"
					:tone="summary.lastChecked ? 'neutral' : 'degraded'"
					:note="summary.lastChecked ? 'hours ago' : 'never checked'"
					:animate="false"
				/>
			</div>

			<IcCard>
				<TargetActions
					target-doctype="Bench"
					:target-name="bench.name"
					:target-label="bench.title"
					:capabilities="bench.capabilities"
					:running-job="bench.running_job"
				/>
			</IcCard>

			<IcCard :padded="false">
				<template #header
					><IcTabs v-model="tab" :tabs="tabs" label="Bench sections"
				/></template>
				<div v-if="tab === 'apps'" id="panel-apps" role="tabpanel">
					<IcTable
						:columns="appColumns"
						:rows="appRows"
						row-key="app"
						empty-title="No apps discovered"
						empty-description="Run inventory discovery on the server to list the apps."
						data-testid="bench-apps"
					>
						<template #cell-app="{ row }">
							<span class="font-medium">{{ row.app }}</span>
							<a
								v-if="row.remote"
								:href="row.remote"
								target="_blank"
								rel="noopener"
								class="block max-w-xs truncate font-mono text-2xs text-fg-subtle hover:text-fg"
								>{{ row.remote }}</a
							>
						</template>
						<template #cell-branch="{ row }"
							><IcBadge mono>{{ row.branch ?? "detached" }}</IcBadge></template
						>
						<template #cell-version="{ row }">
							<span class="font-mono text-xs">{{ row.version ?? "?" }}</span>
							<span v-if="row.newer" class="block text-2xs text-degraded"
								>latest {{ row.newer }}</span
							>
							<span v-else-if="row.latest_tag" class="block text-2xs text-fg-subtle"
								>latest {{ row.latest_tag }}</span
							>
						</template>
						<template #cell-commit="{ row }">
							<span class="font-mono text-xs">{{ row.commit ?? "?" }}</span>
							<span
								v-if="row.upstream_commit && row.upstream_commit !== row.commit"
								class="block font-mono text-2xs text-fg-subtle"
								>upstream {{ row.upstream_commit }}</span
							>
						</template>
						<template #cell-update_state="{ row }">
							<IcBadge
								:tone="updateTone[row.update_state]"
								dot
								:data-testid="`app-state-${row.app}`"
							>
								{{
									row.update_state === "update_available" && row.behind
										? `${row.behind} commit(s) behind`
										: updateLabel[row.update_state]
								}}
							</IcBadge>
							<span v-if="row.checked_at" class="block text-2xs text-fg-subtle">{{
								relativeTime(row.checked_at, now)
							}}</span>
						</template>
						<template #cell-actions="{ row }">
							<div
								v-if="session.canOperate"
								class="flex justify-end gap-2"
								@click.stop
							>
								<IcButton
									size="sm"
									:variant="
										row.update_state === 'update_available'
											? 'primary'
											: 'secondary'
									"
									:disabled="!canUpdate"
									:title="
										bench.running_job
											? `Wait for ${bench.running_job}`
											: `Pull ${row.app} on ${row.branch ?? 'its branch'}`
									"
									:data-testid="`app-update-${row.app}`"
									@click="openUpdate(row)"
									>Update</IcButton
								>
								<IcButton
									size="sm"
									:disabled="!canUpdate || !row.remote?.includes('github.com')"
									:data-testid="`app-switch-${row.app}`"
									@click="openSwitch(row)"
									>Switch version…</IcButton
								>
							</div>
						</template>
					</IcTable>
				</div>
				<div
					v-else-if="tab === 'sites'"
					id="panel-sites"
					role="tabpanel"
					class="divide-y divide-line"
				>
					<RouterLink
						v-for="s in bench.sites"
						:key="s.name"
						:to="`/sites/${encodeURIComponent(s.name)}`"
						class="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-2"
						data-testid="bench-site-row"
					>
						<span class="font-mono text-sm">{{ s.domain }}</span>
						<IcStatusBadge entity="site" :status="s.status" />
						<span class="ms-auto text-xs text-fg-subtle">{{
							s.last_backup
								? `backup ${relativeTime(s.last_backup, now)}`
								: "never backed up"
						}}</span>
					</RouterLink>
					<p
						v-if="!bench.sites.length"
						class="px-4 py-6 text-center text-sm text-fg-subtle"
					>
						No sites on this bench yet.
					</p>
				</div>
				<div v-else id="panel-jobs" role="tabpanel">
					<IcTable
						:columns="jobColumns"
						:rows="jobRows"
						row-key="name"
						clickable
						empty-title="No jobs yet"
						@row-click="
							(j: JobRow) => router.push(`/jobs/${encodeURIComponent(j.name)}`)
						"
					>
						<template #cell-status="{ row }"
							><IcStatusBadge entity="job" :status="row.status"
						/></template>
					</IcTable>
				</div>
			</IcCard>

			<RunPlaybookDialog
				v-if="updatePlaybook && updateApp"
				v-model="updateOpen"
				:playbook="updatePlaybook"
				target-doctype="Bench"
				:target-name="bench.name"
				:target-label="`${bench.title} · ${updateApp.app}`"
				:initial-params="{ apps: [updateApp.app] }"
			/>
			<SwitchVersionDialog
				v-if="switchApp"
				v-model="switchOpen"
				:bench="bench.name"
				:app="switchApp"
			/>
			<CreateSiteDialog v-model="createSite" :bench="bench.name" />
		</template>
	</div>
</template>
