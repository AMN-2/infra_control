<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, useTemplateRef, watch } from "vue";
import { RouterLink } from "vue-router";
import {
	IcBadge,
	IcButton,
	IcField,
	IcInput,
	IcSelect,
	IcStatusBadge,
	IcTerminal,
} from "@/design/components";
import { relativeTime } from "@/lib/time";
import { useInventoryStore, type Bench } from "@/stores/inventory";
import { useJobsStore, type Job } from "@/stores/jobs";
import { useSessionStore } from "@/stores/session";

/**
 * Log reader (A3.8): a read-only `server.logs` job per read, so every look at a log is
 * audited and streamed like any other job; the output lands in the terminal below.
 */
const props = defineProps<{
	server: string;
	benches: readonly Bench[];
	runningJob?: string | null;
}>();
const jobs = useJobsStore();
const inventory = useInventoryStore();
const session = useSessionStore();

const SOURCES: readonly { value: string; label: string; group: string }[] = [
	{ value: "nginx_access", label: "nginx access", group: "Web" },
	{ value: "nginx_error", label: "nginx error", group: "Web" },
	{ value: "bench_web", label: "bench web", group: "Bench" },
	{ value: "bench_worker", label: "bench worker", group: "Bench" },
	{ value: "bench_schedule", label: "bench scheduler", group: "Bench" },
	{ value: "bench_error", label: "bench errors (web + worker)", group: "Bench" },
	{ value: "frappe", label: "frappe.log", group: "Bench" },
	{ value: "database", label: "database queries (database.log)", group: "Bench" },
	{ value: "site", label: "one site (sites/<site>/logs/frappe.log)", group: "Bench" },
	{ value: "mariadb", label: "MariaDB (journal)", group: "System" },
	{ value: "redis", label: "Redis (journal)", group: "System" },
	{ value: "supervisor", label: "supervisor", group: "System" },
	{ value: "system", label: "system journal", group: "System" },
];
const source = ref("bench_error");
const benchPath = ref("");
const site = ref("");
const lines = ref("200");
const match = ref("");
const current = ref<string | null>(null);
const busy = ref(false);
const submitError = ref<string | null>(null);
const terminal = useTemplateRef<InstanceType<typeof IcTerminal>>("terminal");

const needsBench = computed(() =>
	[
		"bench_web",
		"bench_worker",
		"bench_schedule",
		"bench_error",
		"frappe",
		"database",
		"site",
	].includes(source.value)
);
const benchOptions = computed(() =>
	props.benches
		.filter((b) => b.path)
		.map((b) => ({ value: b.path ?? "", label: `${b.title} · ${b.path}` }))
);
const siteOptions = computed(() =>
	inventory.sites
		.filter((s) => s.server === props.server)
		.map((s) => ({ value: s.domain, label: s.domain }))
);
const history = computed<Job[]>(() =>
	jobs.items
		.filter((j) => j.playbook === "server.logs" && j.target_name === props.server)
		.slice(0, 8)
);
const detail = computed(() => (current.value ? jobs.details[current.value] : undefined));
const output = computed(() => {
	const steps = detail.value?.steps ?? [];
	const log = steps.find((s) => s.title === "Log");
	if (log?.output)
		return log.output
			.replace(/^ok: \[[^\]]+\] => \{\s*"msg": "/, "")
			.replace(/"\s*\}\s*$/, "");
	const failed = steps.find((s) => s.status === "Failed");
	return failed ? `${failed.title}: ${failed.output}` : "";
});
const params = computed(() => ({
	source: source.value,
	...(needsBench.value && benchPath.value ? { bench_path: benchPath.value } : {}),
	...(source.value === "site" ? { site: site.value } : {}),
	lines: Math.min(2000, Math.max(1, Number(lines.value) || 200)),
	...(match.value.trim() ? { match: match.value.trim() } : {}),
}));
function sourceOf(p: unknown): string {
	return p && typeof p === "object" && "source" in p ? String(p.source) : "";
}
/** Reads never take the server lock (engine READ_ONLY_PLAYBOOKS), so a running job is no reason to wait. */
const canRead = computed(() => !busy.value && (source.value !== "site" || !!site.value));

async function read(): Promise<void> {
	if (!canRead.value) return;
	busy.value = true;
	submitError.value = null;
	const job = await jobs.runPlaybook({
		playbook: "server.logs",
		target_doctype: "Server",
		target_name: props.server,
		params: params.value,
	});
	busy.value = false;
	if (!job) {
		const e = jobs.error;
		submitError.value = e ? `${e.message} (${e.code})` : "The read could not be started.";
		return;
	}
	show(job.name);
}
function show(name: string): void {
	current.value = name;
	void jobs.fetchDetail(name);
}
let poll: ReturnType<typeof setInterval> | undefined;
watch(
	() => detail.value?.status,
	(status) => {
		if (poll !== undefined) clearInterval(poll);
		if (status === "Queued" || status === "Running")
			poll = setInterval(() => current.value && void jobs.fetchDetail(current.value), 2000);
	},
	{ immediate: true }
);
watch(output, (text) => {
	terminal.value?.clear?.();
	if (text) terminal.value?.write(text.replace(/\\n/g, "\n") + "\n");
});
watch(
	benchOptions,
	(opts) => {
		if (!benchPath.value && opts[0]) benchPath.value = opts[0].value;
	},
	{ immediate: true }
);
onMounted(() => {
	if (!inventory.sites.length) void inventory.fetchSites({ server: props.server });
});
onBeforeUnmount(() => {
	if (poll !== undefined) clearInterval(poll);
});
</script>

<template>
	<div class="flex flex-col gap-4 p-5" data-testid="log-reader">
		<form
			class="grid gap-3 md:grid-cols-[1fr_1fr_6rem_1fr_auto] md:items-end"
			@submit.prevent="read"
		>
			<IcField for-id="log-source" label="Source" required>
				<IcSelect
					id="log-source"
					v-model="source"
					:options="
						SOURCES.map((s) => ({ value: s.value, label: `${s.group} · ${s.label}` }))
					"
					data-testid="log-source"
				/>
			</IcField>
			<IcField v-if="source === 'site'" for-id="log-site" label="Site" required>
				<IcSelect
					id="log-site"
					v-model="site"
					:options="siteOptions"
					placeholder="Choose site"
					data-testid="log-site"
				/>
			</IcField>
			<IcField v-else-if="needsBench" for-id="log-bench" label="Bench" required>
				<IcSelect
					id="log-bench"
					v-model="benchPath"
					:options="benchOptions"
					placeholder="/home/frappe/frappe-bench"
				/>
			</IcField>
			<div v-else />
			<IcField for-id="log-lines" label="Lines">
				<IcInput
					id="log-lines"
					v-model="lines"
					type="number"
					mono
					data-testid="log-lines"
				/>
			</IcField>
			<IcField for-id="log-match" label="Filter" hint="case-insensitive substring">
				<IcInput
					id="log-match"
					v-model="match"
					mono
					placeholder="error, 500, a site name…"
					data-testid="log-match"
				/>
			</IcField>
			<IcButton
				type="submit"
				variant="primary"
				:disabled="!canRead"
				:loading="busy"
				data-testid="log-read"
				>Read</IcButton
			>
		</form>
		<p v-if="!session.canOperate" class="text-xs text-fg-subtle">
			Reading logs needs the Infra Operator role.
		</p>
		<p v-if="submitError" class="text-xs text-down" role="alert" data-testid="log-error">
			{{ submitError }}
		</p>

		<div
			class="flex flex-wrap items-center gap-2 text-xs text-fg-subtle"
			data-testid="log-status"
		>
			<template v-if="detail">
				<IcStatusBadge entity="job" :status="detail.status" />
				<RouterLink
					:to="`/jobs/${encodeURIComponent(detail.name)}`"
					class="font-mono hover:text-fg hover:underline"
					>{{ detail.name }}</RouterLink
				>
				<IcBadge mono>{{ sourceOf(detail.params) }}</IcBadge>
				<span v-if="detail.ended_at">{{ relativeTime(detail.ended_at) }}</span>
			</template>
			<span v-else>Each read is a job: audited, masked, and listed below.</span>
		</div>
		<IcTerminal ref="terminal" :rows="22" data-testid="log-terminal" />

		<div v-if="history.length" class="flex flex-col gap-1" data-testid="log-history">
			<span class="eyebrow">Recent reads</span>
			<button
				v-for="j in history"
				:key="j.name"
				type="button"
				class="flex items-center gap-3 rounded px-2 py-1 text-start text-xs hover:bg-surface-2"
				:class="{ 'bg-surface-2': j.name === current }"
				@click="show(j.name)"
			>
				<span class="font-mono text-fg-muted">{{ j.name }}</span>
				<IcStatusBadge entity="job" :status="j.status" />
				<span class="truncate text-fg-subtle">{{ JSON.stringify(j.params) }}</span>
				<span class="ms-auto text-fg-subtle">{{ relativeTime(j.created_at) }}</span>
			</button>
		</div>
	</div>
</template>
