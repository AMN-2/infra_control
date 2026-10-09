<script setup lang="ts">
import { computed, onBeforeUnmount, ref, useTemplateRef, watch } from "vue";
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
import type { Bench } from "@/stores/inventory";
import { useJobsStore, type Job } from "@/stores/jobs";
import { useSessionStore } from "@/stores/session";

/**
 * Command runner (A3.9): one shell command as the bench user, run as a `server.exec` job so it
 * is audited, masked and streamed like everything else. The output lands in the terminal.
 * Destructive commands are refused by the backend guard before a job exists.
 */
const props = defineProps<{
	server: string;
	benches: readonly Bench[];
	runningJob?: string | null;
}>();
const jobs = useJobsStore();
const session = useSessionStore();

const command = ref("");
const cwd = ref("");
const timeout = ref("120");
const current = ref<string | null>(null);
const busy = ref(false);
const submitError = ref<string | null>(null);
const terminal = useTemplateRef<InstanceType<typeof IcTerminal>>("terminal");

const cwdOptions = computed(() =>
	props.benches
		.filter((b) => b.path)
		.map((b) => ({ value: b.path ?? "", label: `${b.title} · ${b.path}` }))
);
const history = computed<Job[]>(() =>
	jobs.items
		.filter((j) => j.playbook === "server.exec" && j.target_name === props.server)
		.slice(0, 10)
);
const detail = computed(() => (current.value ? jobs.details[current.value] : undefined));
const output = computed(() => {
	const steps = detail.value?.steps ?? [];
	const out = steps.find((s) => s.title === "Output");
	let text = out?.output
		? out.output.replace(/^ok: \[[^\]]+\] => \{\s*"msg": "/, "").replace(/"\s*\}\s*$/, "")
		: "";
	const exit = steps.find((s) => s.title === "Exit status");
	if (exit?.status === "Failed") text += `\n[${exit.output.trim() || "non-zero exit status"}]`;
	const failed = steps.find((s) => s.status === "Failed" && s.title !== "Exit status");
	if (!text && failed) text = `${failed.title}: ${failed.output}`;
	return text;
});
const canRun = computed(() => !busy.value && !props.runningJob && command.value.trim().length > 0);

function commandOf(p: unknown): string {
	return p && typeof p === "object" && "command" in p
		? String((p).command)
		: "";
}
async function run(): Promise<void> {
	if (!canRun.value) return;
	busy.value = true;
	submitError.value = null;
	const job = await jobs.runPlaybook({
		playbook: "server.exec",
		target_doctype: "Server",
		target_name: props.server,
		params: {
			command: command.value.trim(),
			...(cwd.value ? { cwd: cwd.value } : {}),
			timeout: Math.min(600, Math.max(1, Number(timeout.value) || 120)),
		},
	});
	busy.value = false;
	if (!job) {
		const e = jobs.error;
		submitError.value = e ? `${e.message} (${e.code})` : "The command could not be started.";
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
	cwdOptions,
	(opts) => {
		if (!cwd.value && opts[0]) cwd.value = opts[0].value;
	},
	{ immediate: true }
);
onBeforeUnmount(() => {
	if (poll !== undefined) clearInterval(poll);
});
</script>

<template>
	<div class="flex flex-col gap-4 p-5" data-testid="command-runner">
		<form class="flex flex-col gap-3" @submit.prevent="run">
			<IcField
				for-id="cmd-command"
				label="Command"
				required
				hint="Runs as the frappe user with bash. Destructive commands (rm -rf /, mkfs, reboot, drop-site…) are refused. Do not paste passwords: the command is recorded."
			>
				<textarea
					id="cmd-command"
					v-model="command"
					class="min-h-20 w-full rounded border border-line-strong bg-surface-2 p-2.5 font-mono text-sm text-fg"
					placeholder="bench version&#10;git -C apps/erpnext log --oneline -5"
					data-testid="cmd-command"
					@keydown.ctrl.enter.prevent="run"
				/>
			</IcField>
			<div class="grid gap-3 md:grid-cols-[1fr_8rem_auto] md:items-end">
				<IcField for-id="cmd-cwd" label="Working directory">
					<IcSelect
						v-if="cwdOptions.length"
						id="cmd-cwd"
						v-model="cwd"
						:options="cwdOptions"
					/>
					<IcInput
						v-else
						id="cmd-cwd"
						v-model="cwd"
						mono
						placeholder="/home/frappe/frappe-bench"
					/>
				</IcField>
				<IcField for-id="cmd-timeout" label="Timeout (s)">
					<IcInput id="cmd-timeout" v-model="timeout" type="number" mono />
				</IcField>
				<IcButton
					type="submit"
					variant="primary"
					:disabled="!canRun"
					:loading="busy"
					:title="runningJob ? `Wait for ${runningJob}` : 'Ctrl+Enter'"
					data-testid="cmd-run"
					>Run</IcButton
				>
			</div>
		</form>
		<p v-if="!session.canOperate" class="text-xs text-fg-subtle">
			Running commands needs the Infra Operator role.
		</p>
		<p v-if="submitError" class="text-xs text-down" role="alert" data-testid="cmd-error">
			{{ submitError }}
		</p>

		<div
			class="flex flex-wrap items-center gap-2 text-xs text-fg-subtle"
			data-testid="cmd-status"
		>
			<template v-if="detail">
				<IcStatusBadge entity="job" :status="detail.status" />
				<RouterLink
					:to="`/jobs/${encodeURIComponent(detail.name)}`"
					class="font-mono hover:text-fg hover:underline"
					>{{ detail.name }}</RouterLink
				>
				<IcBadge mono class="max-w-md truncate">{{ commandOf(detail.params) }}</IcBadge>
				<span v-if="detail.ended_at">{{ relativeTime(detail.ended_at) }}</span>
			</template>
			<span v-else>Each command is a job: audited, masked, one at a time per server.</span>
		</div>
		<IcTerminal ref="terminal" :rows="20" data-testid="cmd-terminal" />

		<div v-if="history.length" class="flex flex-col gap-1" data-testid="cmd-history">
			<span class="eyebrow">Recent commands</span>
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
				<span class="truncate font-mono text-fg-subtle">{{ commandOf(j.params) }}</span>
				<span class="ms-auto text-fg-subtle">{{ relativeTime(j.created_at) }}</span>
			</button>
		</div>
	</div>
</template>
