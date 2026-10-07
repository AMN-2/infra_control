<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, useTemplateRef, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import {
	IcBadge,
	IcButton,
	IcCard,
	IcConfirmDialog,
	IcPageHeader,
	IcProgress,
	IcSkeleton,
	IcStatusBadge,
	IcTerminal,
	IcTimeline,
	pushToast,
} from "@/design/components";
import ErrorState from "@/features/system/ErrorState.vue";
import { relativeTime, shortTime } from "@/lib/time";
import { useJobsStore } from "@/stores/jobs";
import { useSessionStore } from "@/stores/session";

/**
 * Job viewer (plan §10.2): step timeline plus live terminal. Signature moment: each step
 * expands and colours as it executes while the log streams. Steps and log come from the jobs
 * store (`infra:job.step`, `infra:job.log`); the terminal gets the stored output first, then
 * every new chunk through `onLog`, buffered by IcTerminal at 50 ms.
 */
const route = useRoute();
const jobs = useJobsStore();
const session = useSessionStore();

const name = computed(() => String(route.params.name ?? ""));
const job = computed(() => jobs.details[name.value]);
const terminal = useTemplateRef<InstanceType<typeof IcTerminal>>("terminal");
const now = ref(Date.now());
let clock: ReturnType<typeof setInterval> | undefined;
let stopLog: (() => void) | undefined;

const isLive = computed(() => job.value?.status === "Running" || job.value?.status === "Queued");
const terminal_initial = computed(() =>
	(job.value?.steps ?? [])
		.filter((s) => s.output)
		.map((s) => `── ${s.title}\n${s.output.endsWith("\n") ? s.output : `${s.output}\n`}`)
		.join("")
);

function attachLog(): void {
	stopLog?.();
	stopLog = jobs.onLog(name.value, (chunk) => {
		terminal.value?.write(chunk);
	});
}
function load(): void {
	void jobs.fetchDetail(name.value);
	attachLog();
}
onMounted(() => {
	jobs.subscribe();
	load();
	clock = setInterval(() => {
		now.value = Date.now();
	}, 1000);
});
onBeforeUnmount(() => {
	clearInterval(clock);
	stopLog?.();
});
watch(name, load);

const targetRoute = computed(() => {
	const j = job.value;
	if (!j) return null;
	const n = encodeURIComponent(j.target_name);
	switch (j.target_doctype) {
		case "Server":
			return `/servers/${n}`;
		case "Site":
			return `/sites/${n}`;
		case "Bench":
			return { path: "/sites", query: { bench: j.target_name } };
		default:
			return { path: "/servers", query: { provider_account: j.target_name } };
	}
});
const createdRoute = computed(() => {
	const c = job.value?.created;
	if (!c) return null;
	return c.target_doctype === "Server"
		? `/servers/${encodeURIComponent(c.target_name)}`
		: `/sites/${encodeURIComponent(c.target_name)}`;
});
const duration = computed(() => {
	const j = job.value;
	if (!j?.started_at) return null;
	const end = j.ended_at ? Date.parse(j.ended_at) : now.value;
	const s = Math.max(0, Math.round((end - Date.parse(j.started_at)) / 1000));
	return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
});
const progressTone = computed(() => {
	switch (job.value?.status) {
		case "Failed":
			return "down";
		case "Success":
			return "healthy";
		case "Cancelled":
			return "neutral";
		default:
			return "running";
	}
});

// --- operator actions ---------------------------------------------------------------------
const cancelOpen = ref(false);
const busy = ref(false);
async function cancel(): Promise<void> {
	busy.value = true;
	const j = await jobs.cancel(name.value);
	busy.value = false;
	cancelOpen.value = false;
	if (j) pushToast({ title: "Cancel requested", description: j.name, tone: "degraded" });
	else if (jobs.error)
		pushToast({ title: "Cancel failed", description: jobs.error.message, tone: "down" });
}
async function retry(): Promise<void> {
	busy.value = true;
	const j = await jobs.retry(name.value);
	busy.value = false;
	if (j) {
		// Stay on the original job; the "retried as" badge links to the new one.
		pushToast({
			title: "Retry queued",
			description: `${j.name} resumes from the failed step`,
			tone: "running",
		});
	} else if (jobs.error)
		pushToast({ title: "Retry failed", description: jobs.error.message, tone: "down" });
}
const retried = computed(() => jobs.items.find((j) => j.retry_of === name.value)?.name ?? null);
</script>

<template>
	<div class="flex flex-col gap-6">
		<IcCard v-if="jobs.error && !job" :padded="false">
			<ErrorState
				:error="jobs.error"
				:title="jobs.error.status === 404 ? 'Job not found' : undefined"
				@retry="load"
			/>
		</IcCard>

		<template v-else-if="!job">
			<IcSkeleton :lines="2" />
			<div
				class="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]"
				data-testid="job-loading"
			>
				<IcSkeleton variant="block" />
				<IcSkeleton variant="block" />
			</div>
		</template>

		<template v-else>
			<IcPageHeader
				:title="job.playbook_title"
				:crumbs="[{ label: 'Jobs', to: '/jobs' }, { label: job.name }]"
				:subtitle="`${job.name} · ${job.target_doctype} ${job.target_name} · by ${job.triggered_by} · created ${shortTime(job.created_at)}`"
			/>
			<div class="-mt-4 flex flex-wrap items-center gap-2" data-testid="job-badges">
				<IcStatusBadge entity="job" :status="job.status" />
				<RouterLink v-if="targetRoute" :to="targetRoute">
					<IcBadge mono>{{ job.target_name }}</IcBadge>
				</RouterLink>
				<IcBadge
					v-if="job.cancel_requested && job.status === 'Running'"
					tone="degraded"
					dot
				>
					cancel requested
				</IcBadge>
				<RouterLink v-if="job.retry_of" :to="`/jobs/${encodeURIComponent(job.retry_of)}`">
					<IcBadge mono>retry of {{ job.retry_of }}</IcBadge>
				</RouterLink>
				<RouterLink v-if="retried" :to="`/jobs/${encodeURIComponent(retried)}`">
					<IcBadge tone="running" mono>retried as {{ retried }}</IcBadge>
				</RouterLink>
				<RouterLink
					v-if="job.bulk_operation"
					:to="{ path: '/bulk', query: { bulk: job.bulk_operation } }"
				>
					<IcBadge mono>bulk {{ job.bulk_operation }}</IcBadge>
				</RouterLink>
				<RouterLink
					v-if="createdRoute && job.created"
					:to="createdRoute"
					data-testid="job-created"
				>
					<IcBadge tone="healthy" dot mono
						>created {{ job.created.target_name }}</IcBadge
					>
				</RouterLink>
				<span class="ms-auto font-mono text-xs text-fg-subtle">
					<template v-if="duration"
						>{{ isLive ? "running for" : "took" }} {{ duration }}</template
					>
					<template v-else>queued {{ relativeTime(job.created_at, now) }}</template>
				</span>
			</div>

			<div class="flex flex-wrap items-center gap-4">
				<div class="min-w-64 flex-1">
					<IcProgress
						:value="job.progress"
						:tone="progressTone"
						:label="`${job.name} progress`"
						show-value
					/>
				</div>
				<span class="font-mono text-xs text-fg-subtle"
					>step {{ job.steps_done }}/{{ job.steps_total || "?" }}</span
				>
				<template v-if="session.canOperate">
					<IcButton
						v-if="isLive"
						variant="danger"
						size="sm"
						:disabled="job.cancel_requested"
						data-testid="job-cancel"
						@click="cancelOpen = true"
					>
						Cancel job
					</IcButton>
					<IcButton
						v-if="job.status === 'Failed' && !retried"
						variant="primary"
						size="sm"
						:loading="busy"
						data-testid="job-retry"
						@click="retry"
					>
						Retry from failed step
					</IcButton>
				</template>
			</div>

			<p
				v-if="job.error"
				class="rounded border border-down bg-down-soft px-4 py-3 font-mono text-xs text-down"
				role="alert"
				data-testid="job-error"
			>
				{{ job.error }}
			</p>

			<div class="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
				<IcCard title="Steps" :subtitle="`${job.steps.length} steps`" :live="isLive">
					<IcTimeline v-if="job.steps.length" :steps="job.steps" />
					<p v-else class="text-xs text-fg-subtle">
						Steps appear once the worker picks the job up.
					</p>
				</IcCard>
				<IcCard
					title="Log"
					:subtitle="isLive ? 'streaming' : 'final output'"
					:padded="false"
				>
					<div class="p-3">
						<IcTerminal
							ref="terminal"
							:key="job.name"
							:rows="22"
							:initial="terminal_initial"
						/>
					</div>
				</IcCard>
			</div>

			<IcCard
				v-if="Object.keys(job.params).length"
				title="Parameters"
				:subtitle="'secrets are masked'"
			>
				<dl
					class="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1 font-mono text-xs"
					data-testid="job-params"
				>
					<template v-for="(v, k) in job.params" :key="k">
						<dt class="text-fg-muted">{{ k }}</dt>
						<dd class="break-all">
							{{ typeof v === "string" ? v : JSON.stringify(v) }}
						</dd>
					</template>
				</dl>
			</IcCard>

			<IcConfirmDialog
				v-model="cancelOpen"
				title="Cancel this job?"
				description="A queued job is cancelled at once; a running one stops when the worker reaches the next step."
				:expected="job.name"
				confirm-label="Cancel job"
				:busy="busy"
				@confirm="cancel"
			/>
		</template>
	</div>
</template>
