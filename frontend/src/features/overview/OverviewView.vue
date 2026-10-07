<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import {
	IcCard,
	IcEmptyState,
	IcPageHeader,
	IcProgress,
	IcSkeleton,
	IcSparkline,
	IcStat,
	IcStatusBadge,
} from "@/design/components";
import { transitions } from "@/design/motion";
import { toneFor, type Tone } from "@/design/status";
import ErrorState from "@/features/system/ErrorState.vue";
import { relativeTime, shortTime } from "@/lib/time";
import { useOverviewStore, type OverviewSummary } from "@/stores/overview";

/**
 * Overview (plan §10.2): health counts, running jobs, recent alerts. Signature moment: the
 * numbers count up and the sparklines draw in on arrival. Everything comes from one endpoint
 * (`overview.summary`) kept live by the store.
 */
const overview = useOverviewStore();

const now = ref(Date.now());
let clock: ReturnType<typeof setInterval> | undefined;
onMounted(() => {
	overview.subscribe();
	void overview.fetch();
	clock = setInterval(() => {
		now.value = Date.now();
	}, 30_000);
});
onBeforeUnmount(() => {
	clearInterval(clock);
});

type ServerCounts = OverviewSummary["servers"]["by_status"];
type SiteCounts = OverviewSummary["sites"]["by_status"];

/** Worst status present decides the card tone (down > degraded > healthy); archived is ignored. */
function worstTone(entity: "server" | "site", counts: Record<string, number>): Tone {
	const present = Object.entries(counts)
		.filter(([status, n]) => n > 0 && status !== "Archived")
		.map(([status]) => toneFor(entity, status));
	if (present.includes("down")) return "down";
	if (present.includes("degraded")) return "degraded";
	if (present.includes("running")) return "running";
	return present.length ? "healthy" : "neutral";
}
/** "2 active · 1 degraded": only statuses that occur, in contract order. */
function breakdown(counts: Record<string, number>): string {
	return (
		Object.entries(counts)
			.filter(([, n]) => n > 0)
			.map(([status, n]) => `${n} ${status.toLowerCase()}`)
			.join(" · ") || "none"
	);
}
function present(counts: ServerCounts | SiteCounts): [string, number][] {
	return Object.entries(counts).filter(([, n]) => n > 0);
}

interface Stat {
	key: string;
	label: string;
	value: number;
	tone: Tone;
	note: string;
	points: number[];
	to: string;
}

const stats = computed((): Stat[] => {
	const s = overview.summary;
	if (!s) return [];
	const t = overview.trend;
	const alertTone: Tone = s.alerts.critical ? "down" : s.alerts.warning ? "degraded" : "healthy";
	return [
		{
			key: "servers",
			label: "Servers",
			value: s.servers.total,
			tone: worstTone("server", s.servers.by_status),
			note: breakdown(s.servers.by_status),
			points: t.servers,
			to: "/servers",
		},
		{
			key: "sites",
			label: "Sites",
			value: s.sites.total,
			tone: worstTone("site", s.sites.by_status),
			note: breakdown(s.sites.by_status),
			points: t.sites,
			to: "/sites",
		},
		{
			key: "jobs",
			label: "Jobs in flight",
			value: s.jobs.running + s.jobs.queued,
			tone: s.jobs.running + s.jobs.queued ? "running" : "neutral",
			note: `${s.jobs.running} running · ${s.jobs.queued} queued · ${s.jobs.success_24h} ok / ${s.jobs.failed_24h} failed in 24 h`,
			points: t.jobs,
			to: "/jobs",
		},
		{
			key: "alerts",
			label: "Unresolved alerts",
			value: s.alerts.unresolved,
			tone: s.alerts.unresolved ? alertTone : "healthy",
			note: s.alerts.unresolved
				? `${s.alerts.critical} critical · ${s.alerts.warning} warning · ${s.alerts.info} info`
				: "all clear",
			points: t.alerts,
			to: "/alerts",
		},
	];
});
</script>

<template>
	<div class="flex flex-col gap-6">
		<IcPageHeader
			title="Overview"
			:subtitle="
				overview.summary
					? `Generated ${shortTime(overview.summary.generated_at)} · live`
					: undefined
			"
		/>

		<IcCard v-if="overview.error && !overview.summary" :padded="false">
			<ErrorState :error="overview.error" @retry="overview.fetch()" />
		</IcCard>

		<template v-else-if="!overview.summary">
			<div class="grid grid-cols-2 gap-3 xl:grid-cols-4" data-testid="overview-loading">
				<div
					v-for="i in 4"
					:key="i"
					class="flex flex-col gap-3 rounded border border-line bg-surface-2 p-4"
				>
					<IcSkeleton />
					<IcSkeleton variant="block" />
				</div>
			</div>
			<div class="grid gap-4 lg:grid-cols-2">
				<IcCard title="Running jobs"><IcSkeleton :lines="3" /></IcCard>
				<IcCard title="Recent alerts"><IcSkeleton :lines="3" /></IcCard>
			</div>
		</template>

		<template v-else>
			<!-- Headline numbers: count up on arrival, sparkline draws in once two readings exist. -->
			<div class="grid grid-cols-2 gap-3 xl:grid-cols-4" data-testid="overview-stats">
				<RouterLink
					v-for="s in stats"
					:key="s.key"
					:to="s.to"
					class="flex rounded outline-none focus-visible:ring-2 focus-visible:ring-accent"
					:data-testid="`stat-${s.key}`"
				>
					<IcStat
						:label="s.label"
						:value="s.value"
						:note="s.note"
						:tone="s.tone"
						class="flex-1"
					>
						<IcSparkline
							v-if="s.points.length >= 2"
							:key="s.points.length"
							:points="s.points"
							:tone="s.tone"
						/>
						<div v-else class="h-8" aria-hidden="true" />
					</IcStat>
				</RouterLink>
			</div>

			<!-- Status breakdown -->
			<div class="grid gap-4 lg:grid-cols-2">
				<IcCard title="Servers by status" :padded="true">
					<div class="flex flex-wrap gap-2">
						<RouterLink
							v-for="[status, n] in present(overview.summary.servers.by_status)"
							:key="status"
							:to="{ path: '/servers', query: { status } }"
							class="flex items-center gap-2 rounded-full border border-line px-1.5 py-1 pe-3 text-xs"
						>
							<IcStatusBadge entity="server" :status="status" />
							<span class="numerals">{{ n }}</span>
						</RouterLink>
						<span
							v-if="!present(overview.summary.servers.by_status).length"
							class="text-xs text-fg-subtle"
							>No servers yet</span
						>
					</div>
				</IcCard>
				<IcCard title="Sites by status" :padded="true">
					<div class="flex flex-wrap gap-2">
						<RouterLink
							v-for="[status, n] in present(overview.summary.sites.by_status)"
							:key="status"
							:to="{ path: '/sites', query: { status } }"
							class="flex items-center gap-2 rounded-full border border-line px-1.5 py-1 pe-3 text-xs"
						>
							<IcStatusBadge entity="site" :status="status" />
							<span class="numerals">{{ n }}</span>
						</RouterLink>
						<span
							v-if="!present(overview.summary.sites.by_status).length"
							class="text-xs text-fg-subtle"
							>No sites yet</span
						>
					</div>
				</IcCard>
			</div>

			<div class="grid gap-4 lg:grid-cols-2">
				<!-- Running jobs: real progress, never a spinner (§10.3.7). -->
				<IcCard
					title="Running jobs"
					:subtitle="`${overview.summary.jobs.running} running · ${overview.summary.jobs.queued} queued`"
					:padded="false"
					:live="overview.summary.running_jobs.length > 0"
				>
					<template #actions>
						<RouterLink to="/jobs" class="text-xs text-accent-text"
							>All jobs</RouterLink
						>
					</template>
					<IcEmptyState
						v-if="overview.summary.running_jobs.length === 0"
						title="Nothing is running"
						description="Jobs appear here the moment they are queued."
					/>
					<TransitionGroup
						v-else
						tag="ul"
						:name="transitions.rise"
						class="flex flex-col divide-y divide-line"
						data-testid="running-jobs"
					>
						<li v-for="j in overview.summary.running_jobs" :key="j.name">
							<RouterLink
								:to="`/jobs/${encodeURIComponent(j.name)}`"
								class="ic-state-layer flex flex-col gap-2 px-5 py-3"
							>
								<div class="flex items-center gap-3">
									<span class="min-w-0 flex-1 truncate text-sm">
										{{ j.playbook_title }}
										<span class="font-mono text-xs text-fg-muted"
											>· {{ j.target_name }}</span
										>
									</span>
									<IcStatusBadge entity="job" :status="j.status" />
								</div>
								<IcProgress
									:value="j.progress"
									tone="running"
									:label="`${j.playbook_title} progress`"
									show-value
								/>
								<span class="font-mono text-2xs text-fg-subtle">
									{{ j.name }} · step {{ j.steps_done }}/{{
										j.steps_total || "?"
									}}
									·
									{{ j.triggered_by }}
								</span>
							</RouterLink>
						</li>
					</TransitionGroup>
				</IcCard>

				<!-- Recent alerts: severity accent on the alert, not the row. -->
				<IcCard
					title="Recent alerts"
					:subtitle="`${overview.summary.alerts.unresolved} unresolved`"
					:padded="false"
				>
					<template #actions>
						<RouterLink to="/alerts" class="text-xs text-accent-text"
							>All alerts</RouterLink
						>
					</template>
					<IcEmptyState
						v-if="overview.summary.recent_alerts.length === 0"
						title="No recent alerts"
						description="Firing and recently resolved alerts show up here."
					/>
					<TransitionGroup
						v-else
						tag="ul"
						:name="transitions.rise"
						class="flex flex-col gap-2 p-3"
						aria-live="polite"
						data-testid="recent-alerts"
					>
						<li
							v-for="a in overview.summary.recent_alerts"
							:key="a.name"
							class="flex items-center gap-3 rounded-sm border border-line border-s-2 bg-surface-2 px-3 py-2.5"
							:class="{
								'border-s-down': a.severity === 'critical',
								'border-s-degraded': a.severity === 'warning',
								'border-s-running': a.severity === 'info',
							}"
						>
							<div class="flex min-w-0 flex-1 flex-col">
								<span class="truncate text-sm">{{ a.message }}</span>
								<span class="truncate font-mono text-xs text-fg-subtle">
									{{ a.target.target_name }} · {{ a.rule_title }} ·
									{{ relativeTime(a.fired_at, now) }}
								</span>
							</div>
							<IcStatusBadge entity="severity" :status="a.severity" />
							<IcStatusBadge entity="alert" :status="a.status" />
						</li>
					</TransitionGroup>
				</IcCard>
			</div>
		</template>
	</div>
</template>
