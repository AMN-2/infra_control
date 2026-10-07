<script setup lang="ts">
import { computed, onMounted, useTemplateRef, watch } from "vue";
import { useRouter } from "vue-router";
import { IcCard, IcEmptyState, IcPageHeader, IcSkeleton } from "@/design/components";
import { toneClass, toneLabel, type Tone } from "@/design/status";
import ErrorState from "@/features/system/ErrorState.vue";
import { shortTime } from "@/lib/time";
import { useInventoryStore } from "@/stores/inventory";
import TopologyGraph from "./TopologyGraph.vue";
import { layoutTopology, nodeRoute, type TopologyNode } from "./layout";

const inventory = useInventoryStore();
const router = useRouter();
const graph = useTemplateRef<InstanceType<typeof TopologyGraph>>("graph");

const layout = computed(() => (inventory.topology ? layoutTopology(inventory.topology) : null));
const counts = computed(() => {
	const nodes = inventory.topology?.nodes ?? [];
	const of = (t: TopologyNode["type"]): number => nodes.filter((n) => n.type === t).length;
	return {
		providers: of("provider"),
		servers: of("server"),
		benches: of("bench"),
		sites: of("site"),
	};
});
const subtitle = computed(() => {
	const t = inventory.topology;
	if (!t) return undefined;
	const c = counts.value;
	return `${c.servers} servers · ${c.benches} benches · ${c.sites} sites · generated ${shortTime(t.generated_at)}`;
});
const legend: readonly Tone[] = ["healthy", "degraded", "down", "running", "neutral"];

onMounted(() => {
	inventory.subscribe();
	if (!inventory.topology) void inventory.fetchTopology();
});

// Signature moment: every heartbeat sends a pulse down that server's edges.
watch(
	() => inventory.lastBeat,
	(beat) => {
		if (beat) graph.value?.pulse(beat.server);
	}
);

function open(node: TopologyNode): void {
	const r = nodeRoute(node);
	void router.push({ path: r.path, query: r.query });
}
</script>

<template>
	<div class="flex flex-col gap-4">
		<IcPageHeader title="Topology" :subtitle="subtitle" />

		<IcCard v-if="inventory.error && !inventory.topology" :padded="false">
			<ErrorState :error="inventory.error" @retry="inventory.fetchTopology()" />
		</IcCard>

		<div v-else-if="!layout" class="flex flex-col gap-3" data-testid="topology-loading">
			<IcSkeleton variant="block" />
			<IcSkeleton :lines="2" />
		</div>

		<IcCard v-else-if="layout.nodes.length === 0" :padded="false">
			<IcEmptyState
				title="No inventory yet"
				description="Add a Provider Account and run the inventory.sync playbook; servers, benches and sites appear here as they are discovered."
			/>
		</IcCard>

		<template v-else>
			<TopologyGraph
				ref="graph"
				:layout="layout"
				:heartbeats="inventory.heartbeats"
				@select="open"
			/>
			<div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-fg-subtle">
				<span v-for="t in legend" :key="t" class="flex items-center gap-1.5">
					<span class="size-1.5 rounded-full" :class="toneClass[t].bg" />
					{{ toneLabel[t] }}
				</span>
				<span class="flex items-center gap-1.5">
					<span class="ic-glow size-3 rounded-sm border border-running" />
					Running job
				</span>
				<span class="ms-auto">Scroll to zoom · drag to pan · click a node to open it</span>
			</div>
		</template>
	</div>
</template>
