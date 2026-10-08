<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { Play } from "lucide-vue-next";
import { IcBadge, IcButton, IcSkeleton } from "@/design/components";
import type { components } from "@/api/schema";
import { usePlaybooksStore, type Playbook, type TargetDoctype } from "@/stores/playbooks";
import { useSessionStore } from "@/stores/session";
import RunPlaybookDialog from "./RunPlaybookDialog.vue";

type Capability = components["schemas"]["Capability"];

/**
 * Capability-driven actions for a server, bench or site (plan §10.2: controls for unsupported
 * capabilities are not rendered). The list comes from `playbooks.list` for the target; a
 * playbook whose `required_capability` the target lacks is dropped, and so are creation
 * playbooks (those live on the parent's "create" flow). Viewers see nothing; a target whose
 * server is locked by a running job shows the lock instead of enabled buttons.
 */
const props = defineProps<{
	targetDoctype: TargetDoctype;
	targetName: string;
	targetLabel?: string;
	capabilities: readonly Capability[];
	runningJob?: string | null;
	/** Inline in a table cell: no heading, no "no actions" text. */
	compact?: boolean;
}>();

const playbooks = usePlaybooksStore();
const session = useSessionStore();
const selected = ref<Playbook | null>(null);
const open = ref(false);

const key = computed(() => `${props.targetDoctype}:${props.targetName}`);
const available = computed(() =>
	(playbooks.forTarget[key.value] ?? []).filter(
		(p) =>
			p.target_doctype === props.targetDoctype &&
			p.creates === null &&
			(p.required_capability === null || props.capabilities.includes(p.required_capability))
	)
);
const loaded = computed(() => key.value in playbooks.forTarget);

function load(): void {
	void playbooks.fetchFor(props.targetDoctype, props.targetName);
}
onMounted(load);
watch(key, load);

function pick(p: Playbook): void {
	selected.value = p;
	open.value = true;
}
const riskVariant = { low: "secondary", medium: "secondary", high: "danger" } as const;
</script>

<template>
	<div
		v-if="session.canOperate"
		class="flex flex-col gap-3"
		:class="{ 'items-end': compact }"
		:data-testid="compact ? 'target-actions-inline' : 'target-actions'"
	>
		<div v-if="!compact" class="flex items-center gap-2">
			<span class="eyebrow">Actions</span>
			<RouterLink
				v-if="runningJob"
				:to="`/jobs/${encodeURIComponent(runningJob)}`"
				class="ms-auto"
				data-testid="lock-notice"
			>
				<IcBadge tone="running" dot live mono>locked by {{ runningJob }}</IcBadge>
			</RouterLink>
		</div>
		<IcSkeleton v-if="!loaded && playbooks.loading" :lines="2" />
		<p v-else-if="!available.length && !compact" class="text-xs text-fg-subtle">
			No actions are available for this {{ targetDoctype.toLowerCase() }}.
		</p>
		<div v-else class="flex flex-wrap gap-2">
			<IcButton
				v-for="p in available"
				:key="p.key"
				size="sm"
				:variant="riskVariant[p.risk]"
				:disabled="!!runningJob"
				:title="runningJob ? `Wait for ${runningJob} to finish` : p.description"
				:data-testid="`action-${p.key}`"
				@click="pick(p)"
			>
				<Play class="size-3.5" aria-hidden="true" />
				{{ p.title }}
			</IcButton>
		</div>
		<RunPlaybookDialog
			v-if="selected"
			v-model="open"
			:playbook="selected"
			:target-doctype="targetDoctype"
			:target-name="targetName"
			:target-label="targetLabel"
		/>
	</div>
</template>
