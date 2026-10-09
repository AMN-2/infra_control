<script setup lang="ts">
import { computed, onMounted, ref, useTemplateRef, watch } from "vue";
import { IcBadge, IcButton, IcSkeleton, IcTerminal } from "@/design/components";
import { relativeTime } from "@/lib/time";
import { useConsoleStore } from "@/stores/console";

/** What happened in each console session (ADR 0007): list and replay of the transcript. */
const props = defineProps<{ server: string; refreshKey?: number }>();
const consoleStore = useConsoleStore();
const selected = ref<string | null>(null);
const terminal = useTemplateRef<InstanceType<typeof IcTerminal>>("terminal");
const items = computed(() => consoleStore.sessions[props.server] ?? []);
const transcript = computed(() =>
	selected.value ? consoleStore.transcripts[selected.value] : undefined
);

async function show(session: string): Promise<void> {
	selected.value = session;
	const t = await consoleStore.fetchTranscript(session);
	terminal.value?.clear?.();
	if (t?.transcript) terminal.value?.write(t.transcript);
}
function load(): void {
	void consoleStore.fetchSessions(props.server);
}
onMounted(load);
watch(() => props.refreshKey, load);
</script>

<template>
	<div class="flex flex-col gap-3" data-testid="console-sessions">
		<div class="flex items-center gap-2">
			<span class="eyebrow">Sessions</span>
			<IcButton size="sm" variant="ghost" class="ms-auto" @click="load">Refresh</IcButton>
		</div>
		<IcSkeleton v-if="consoleStore.loading && !items.length" :lines="2" />
		<p v-else-if="!items.length" class="text-xs text-fg-subtle">
			No console sessions on this server yet.
		</p>
		<ul
			v-else
			class="divide-y divide-line rounded border border-line"
			data-testid="console-session-list"
		>
			<li v-for="s in items" :key="s.session">
				<button
					type="button"
					class="flex w-full flex-wrap items-center gap-3 px-3 py-2 text-start text-xs hover:bg-surface-2"
					:class="{ 'bg-surface-2': s.session === selected }"
					:data-testid="`session-${s.session}`"
					@click="show(s.session)"
				>
					<span class="font-mono text-fg-muted">{{ s.session }}</span>
					<IcBadge
						:tone="s.status === 'open' ? 'running' : 'neutral'"
						dot
						:live="s.status === 'open'"
						>{{ s.status }}</IcBadge
					>
					<span>{{ s.by }}</span>
					<span v-if="s.started_at" class="text-fg-subtle">{{
						relativeTime(s.started_at)
					}}</span>
					<span v-if="s.reason" class="text-fg-subtle">· {{ s.reason }}</span>
					<span class="ms-auto text-fg-subtle"
						>{{ (s.bytes / 1024).toFixed(1) }} KB</span
					>
				</button>
			</li>
		</ul>
		<div v-if="selected" class="flex flex-col gap-1">
			<span class="text-xs text-fg-subtle" data-testid="console-transcript-label"
				>Transcript {{ selected
				}}<span v-if="transcript?.truncated"> (last 200 KB)</span></span
			>
			<IcTerminal ref="terminal" :rows="18" data-testid="console-transcript" />
		</div>
	</div>
</template>
