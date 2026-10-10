<script setup lang="ts">
import { IcProviderBadge } from "@/design/components";
import { liveStates, toneClass, toneFor, type Tone } from "@/design/status";
import { NODE_H, NODE_W, type TopologyNode } from "./layout";

/**
 * One node card. Its own component so a heartbeat (new `metrics` for one server) patches that
 * card only; the other cards keep identical props and Vue skips them (B4.1, 200-node topology).
 */
defineProps<{ node: TopologyNode; x: number; y: number; metrics: string | null }>();
const emit = defineEmits<{ select: [node: TopologyNode, viaKeyboard: boolean] }>();

const kindLabel: Record<TopologyNode["type"], string> = {
	provider: "Provider",
	server: "Server",
	bench: "Bench",
	site: "Site",
};
function nodeTone(n: TopologyNode): Tone {
	if (n.type === "server" || n.type === "site") return toneFor(n.type, n.status ?? "");
	return "neutral";
}
function isLive(n: TopologyNode): boolean {
	return n.has_running_job || liveStates.has(n.status ?? "");
}
</script>

<template>
	<!-- Outer box holds the position; the card holds the look (ic-glow sets position: relative). -->
	<div
		class="absolute"
		:style="{
			insetInlineStart: `${x}px`,
			insetBlockStart: `${y}px`,
			inlineSize: `${NODE_W}px`,
			blockSize: `${NODE_H}px`,
		}"
	>
		<div
			role="button"
			tabindex="0"
			class="flex size-full cursor-pointer flex-col justify-center gap-0.5 rounded border bg-surface-2 px-3 outline-none hover:bg-surface-3 focus-visible:ring-2 focus-visible:ring-accent"
			:class="node.has_running_job ? 'ic-glow border-running' : 'border-line-strong'"
			:data-testid="`topology-node-${node.id}`"
			:data-type="node.type"
			:aria-label="`${kindLabel[node.type]} ${node.label}`"
			@click="emit('select', node, false)"
			@keydown.enter.prevent="emit('select', node, true)"
		>
			<span class="flex items-center gap-1.5 text-xs">
				<span
					class="size-1.5 shrink-0 rounded-full"
					:class="[toneClass[nodeTone(node)].bg, isLive(node) ? 'ic-pulse ic-live' : '']"
				/>
				<span
					class="min-w-0 flex-1 truncate"
					:class="
						node.type === 'server' || node.type === 'site'
							? 'font-mono'
							: 'font-medium'
					"
					>{{ node.label }}</span
				>
				<IcProviderBadge
					v-if="node.type === 'server' || node.type === 'site'"
					:provider="node.provider"
				/>
			</span>
			<span class="flex items-center gap-2 text-2xs text-fg-subtle">
				<span>{{ kindLabel[node.type] }}</span>
				<span v-if="node.status" :class="toneClass[nodeTone(node)].text">{{
					node.status
				}}</span>
				<span v-if="metrics" class="ms-auto truncate font-mono">{{ metrics }}</span>
			</span>
		</div>
	</div>
</template>
