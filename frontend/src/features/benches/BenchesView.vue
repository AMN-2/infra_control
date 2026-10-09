<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import {
	IcBadge,
	IcButton,
	IcCard,
	IcEmptyState,
	IcField,
	IcInput,
	IcPageHeader,
	IcProviderBadge,
	IcSelect,
	IcSkeleton,
	IcStat,
	pushToast,
} from "@/design/components";
import ErrorState from "@/features/system/ErrorState.vue";
import { relativeTime } from "@/lib/time";
import { useInventoryStore, type Bench } from "@/stores/inventory";
import { useSessionStore } from "@/stores/session";
import { benchState, summarize, updateLabel, updateTone } from "./updates";

/**
 * Benches (ADR 0009): every bench with its apps and versions, and whether upstream has moved.
 * Tiles filter by update state; `server` comes from the URL. "Check all" asks upstream for
 * every bench in turn (one request per bench; GitHub rate limits apply).
 */
const inventory = useInventoryStore();
const session = useSessionStore();
const route = useRoute();
const router = useRouter();
const search = ref("");
const now = ref(Date.now());
const checking = ref<string | null>(null);
let clock: ReturnType<typeof setInterval> | undefined;

const q = (key: string): string => {
	const v = route.query[key];
	return typeof v === "string" ? v : "";
};
const state = computed(() => q("updates"));
const server = computed(() => q("server"));

function load(): void {
	void inventory.fetchBenches(server.value ? { server: server.value } : {});
	if (!inventory.servers.length) void inventory.fetchServers();
}
function setFilter(key: "updates" | "server", v: string): void {
	void router.replace({ query: { ...route.query, [key]: v || undefined } });
}
onMounted(() => {
	inventory.subscribe();
	load();
	clock = setInterval(() => (now.value = Date.now()), 30_000);
});
onBeforeUnmount(() => {
	clearInterval(clock);
});
watch(server, load);

const STATES = [
	{ id: "update_available", label: "Update available", tone: "degraded" },
	{ id: "up_to_date", label: "Up to date", tone: "healthy" },
	{ id: "unknown", label: "Not checked", tone: "neutral" },
] as const;
const counts = computed(() => {
	const c: Record<string, number> = { update_available: 0, up_to_date: 0, unknown: 0 };
	for (const b of inventory.benches) c[benchState(b)] = (c[benchState(b)] ?? 0) + 1;
	return c;
});
const rows = computed(() => {
	const text = search.value.trim().toLowerCase();
	const order = { update_available: 0, unknown: 1, up_to_date: 2 } as const;
	return inventory.benches
		.filter((b) => !state.value || benchState(b) === state.value)
		.filter(
			(b) =>
				!text ||
				b.title.toLowerCase().includes(text) ||
				b.name.toLowerCase().includes(text) ||
				(b.server ?? "").toLowerCase().includes(text) ||
				b.apps.some((a) => a.app.includes(text))
		)
		.map((b) => ({ bench: b, summary: summarize(b.apps) }))
		.sort(
			(a, b) =>
				order[a.summary.state] - order[b.summary.state] ||
				a.bench.title.localeCompare(b.bench.title)
		);
});
const serverOptions = computed(() => [
	{ value: "", label: "All servers" },
	...inventory.servers.map((s) => ({ value: s.name, label: s.hostname })),
]);
const hostOf = (b: Bench): string =>
	inventory.servers.find((s) => s.name === b.server)?.hostname ?? b.server ?? "Frappe Cloud";

async function checkAll(): Promise<void> {
	if (checking.value) return;
	let behind = 0;
	for (const b of inventory.benches) {
		checking.value = b.name;
		const d = await inventory.checkBenchUpdates(b.name);
		if (d) behind += summarize(d.apps).behind;
	}
	checking.value = null;
	pushToast({
		title: "Update check finished",
		description: behind
			? `${behind} app(s) have updates upstream.`
			: "Every checked app is current.",
		tone: behind ? "degraded" : "healthy",
	});
}
</script>

<template>
	<div class="flex flex-col gap-6">
		<IcPageHeader
			title="Benches"
			subtitle="Every bench, its apps and versions, and what upstream has that the bench does not."
		>
			<template #actions>
				<IcButton
					v-if="session.canOperate"
					variant="primary"
					:loading="!!checking"
					:disabled="!inventory.benches.length"
					data-testid="benches-check-all"
					@click="checkAll"
				>
					{{ checking ? `Checking ${checking}…` : "Check all for updates" }}
				</IcButton>
			</template>
		</IcPageHeader>

		<div class="grid grid-cols-2 gap-3 md:grid-cols-4" data-testid="bench-tiles">
			<button type="button" class="text-start" @click="setFilter('updates', '')">
				<IcStat
					label="Benches"
					:value="inventory.benches.length"
					tone="neutral"
					:animate="false"
				/>
			</button>
			<button
				v-for="s in STATES"
				:key="s.id"
				type="button"
				class="text-start"
				:aria-pressed="state === s.id"
				:data-testid="`bench-tile-${s.id}`"
				@click="setFilter('updates', state === s.id ? '' : s.id)"
			>
				<IcStat
					:label="s.label"
					:value="counts[s.id] ?? 0"
					:tone="(counts[s.id] ?? 0) > 0 ? s.tone : 'neutral'"
					:animate="false"
					:class="{ 'ring-1 ring-accent': state === s.id }"
				/>
			</button>
		</div>

		<div class="flex flex-wrap items-end gap-3">
			<IcField label="Search" for-id="bench-search" class="min-w-64 flex-1">
				<IcInput
					id="bench-search"
					v-model="search"
					type="search"
					placeholder="Bench, server or app"
				/>
			</IcField>
			<IcField label="Server" for-id="bench-server" class="w-56">
				<IcSelect
					id="bench-server"
					:model-value="server"
					:options="serverOptions"
					@update:model-value="(v: string) => setFilter('server', v)"
				/>
			</IcField>
		</div>

		<IcCard v-if="inventory.error && !inventory.benches.length" :padded="false">
			<ErrorState :error="inventory.error" @retry="load" />
		</IcCard>
		<IcSkeleton v-else-if="inventory.loading && !inventory.benches.length" :lines="6" />
		<IcEmptyState
			v-else-if="!rows.length"
			title="No benches"
			description="Benches appear after inventory discovery or server.provision."
		/>
		<div v-else class="overflow-x-auto rounded border border-line bg-surface-1">
			<table class="w-full border-collapse text-sm" data-testid="benches-table">
				<thead>
					<tr class="border-b border-line">
						<th class="eyebrow px-4 py-2.5 text-start font-medium">Bench</th>
						<th class="eyebrow px-4 py-2.5 text-start font-medium">Server</th>
						<th class="eyebrow px-4 py-2.5 text-start font-medium">Apps</th>
						<th class="eyebrow px-4 py-2.5 text-start font-medium">Updates</th>
						<th class="eyebrow px-4 py-2.5 text-end font-medium">Sites</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="{ bench: b, summary } in rows"
						:key="b.name"
						class="cursor-pointer border-b border-line last:border-0 hover:bg-surface-2"
						role="row"
						data-testid="bench-row"
						@click="router.push(`/benches/${encodeURIComponent(b.name)}`)"
					>
						<td class="px-4 py-3 align-top">
							<RouterLink
								:to="`/benches/${encodeURIComponent(b.name)}`"
								class="font-medium"
								@click.stop
								>{{ b.title }}</RouterLink
							>
							<span class="block truncate font-mono text-2xs text-fg-subtle">{{
								b.path ?? b.name
							}}</span>
							<span class="mt-1 block text-2xs text-fg-subtle"
								>Frappe {{ b.frappe_version ?? "?" }}</span
							>
						</td>
						<td class="px-4 py-3 align-top">
							<RouterLink
								v-if="b.server"
								:to="`/servers/${encodeURIComponent(b.server)}`"
								class="font-mono text-xs"
								@click.stop
								>{{ hostOf(b) }}</RouterLink
							>
							<IcProviderBadge v-else :provider="b.provider" />
						</td>
						<td class="px-4 py-3 align-top">
							<div class="flex max-w-md flex-wrap gap-1">
								<IcBadge
									v-for="a in b.apps"
									:key="a.app"
									mono
									:tone="updateTone[a.update_state]"
									:dot="a.update_state === 'update_available'"
								>
									{{ a.app
									}}<span class="text-fg-subtle"
										>@{{ a.version ?? a.branch ?? "?" }}</span
									>
								</IcBadge>
								<span v-if="!b.apps.length" class="text-xs text-fg-subtle"
									>not discovered yet</span
								>
							</div>
						</td>
						<td class="px-4 py-3 align-top">
							<IcBadge :tone="updateTone[summary.state]" dot>
								{{
									summary.state === "update_available"
										? `${summary.behind} app(s) behind`
										: updateLabel[summary.state]
								}}
							</IcBadge>
							<span
								v-if="summary.lastChecked"
								class="mt-1 block text-2xs text-fg-subtle"
								>checked {{ relativeTime(summary.lastChecked, now) }}</span
							>
						</td>
						<td class="px-4 py-3 text-end align-top">
							<RouterLink
								:to="{ path: '/sites', query: { bench: b.name } }"
								class="font-mono text-xs"
								@click.stop
								>{{ b.site_count }}</RouterLink
							>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>
