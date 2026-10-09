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
	IcMetricChip,
	IcPageHeader,
	IcProviderBadge,
	IcSelect,
	IcSkeleton,
	IcStat,
	IcStatusBadge,
} from "@/design/components";
import ErrorState from "@/features/system/ErrorState.vue";
import { relativeTime } from "@/lib/time";
import { useInventoryStore, type Server } from "@/stores/inventory";
import { useSessionStore } from "@/stores/session";
import ProvisionDialog from "./ProvisionDialog.vue";

/**
 * Servers: status tiles that filter, search, and one table with the live load per server
 * (cpu / ram / disk from the last heartbeat), its benches and sites, and the heartbeat age.
 * Filters live in the URL so other screens can link here.
 */
const inventory = useInventoryStore();
const session = useSessionStore();
const route = useRoute();
const router = useRouter();
const provisioning = ref(false);
const search = ref("");
const now = ref(Date.now());
let clock: ReturnType<typeof setInterval> | undefined;

const STATUSES = ["Active", "Degraded", "Down", "Provisioning", "Archived"] as const;
const status = computed(() => (typeof route.query.status === "string" ? route.query.status : ""));
const account = computed(() =>
	typeof route.query.provider_account === "string" ? route.query.provider_account : ""
);

function load(): void {
	void inventory.fetchServers({
		...(status.value ? { status: status.value as Server["status"] } : {}),
		...(account.value ? { provider_account: account.value } : {}),
	});
}
function setFilter(key: "status" | "provider_account", v: string): void {
	void router.replace({ query: { ...route.query, [key]: v || undefined } });
}
onMounted(() => {
	inventory.subscribe();
	load();
	clock = setInterval(() => (now.value = Date.now()), 15_000);
});
onBeforeUnmount(() => {
	clearInterval(clock);
});
watch([status, account], load);

const counts = computed(() => {
	const c: Record<string, number> = {};
	for (const s of inventory.servers) c[s.status] = (c[s.status] ?? 0) + 1;
	return c;
});
const accounts = computed(() =>
	[...new Set(inventory.servers.map((s) => s.provider_account))].sort()
);
const rows = computed(() => {
	const q = search.value.trim().toLowerCase();
	const order: Record<Server["status"], number> = {
		Down: 0,
		Degraded: 1,
		Provisioning: 2,
		Active: 3,
		Archived: 4,
	};
	return inventory.servers
		.filter(
			(s) =>
				!q ||
				[s.hostname, s.name, s.public_ip ?? "", s.region, s.size, s.tags.join(" ")].some(
					(v) => v.toLowerCase().includes(q)
				)
		)
		.sort((a, b) => order[a.status] - order[b.status] || a.hostname.localeCompare(b.hostname))
		.map((s) => ({ ...s, hb: inventory.heartbeats[s.name] }));
});
function heartbeatTone(s: Server): "healthy" | "degraded" | "down" | "neutral" {
	if (!s.last_heartbeat) return "neutral";
	const age = (now.value - Date.parse(s.last_heartbeat)) / 1000;
	return age < 180 ? "healthy" : age < 900 ? "degraded" : "down";
}
const statTone = {
	Active: "healthy",
	Degraded: "degraded",
	Down: "down",
	Provisioning: "running",
	Archived: "neutral",
} as const;
</script>

<template>
	<div class="flex flex-col gap-5">
		<IcPageHeader
			title="Servers"
			subtitle="Every managed server with its live load, what runs on it, and when it last reported."
		>
			<template #actions>
				<IcButton
					v-if="session.canOperate"
					variant="primary"
					data-testid="server-new"
					@click="provisioning = true"
					>New server</IcButton
				>
			</template>
		</IcPageHeader>
		<ProvisionDialog v-model="provisioning" />

		<div class="grid grid-cols-2 gap-3 md:grid-cols-5" data-testid="servers-stats">
			<button
				v-for="s in STATUSES"
				:key="s"
				type="button"
				class="rounded border text-start transition-colors"
				:class="
					status === s ? 'border-accent bg-surface-2' : 'border-line hover:bg-surface-2'
				"
				:aria-pressed="status === s"
				:data-testid="`servers-stat-${s}`"
				@click="setFilter('status', status === s ? '' : s)"
			>
				<IcStat :label="s" :value="counts[s] ?? 0" :tone="statTone[s]" :animate="false" />
			</button>
		</div>

		<div class="flex flex-wrap items-end gap-3">
			<IcField for-id="servers-search" label="Search" class="min-w-64 flex-1">
				<IcInput
					id="servers-search"
					v-model="search"
					type="search"
					mono
					placeholder="hostname, id, IP, region, size, tag…"
					data-testid="servers-search"
				/>
			</IcField>
			<IcField for-id="servers-account" label="Provider account">
				<IcSelect
					id="servers-account"
					:model-value="account"
					:options="accounts.map((a) => ({ value: a, label: a }))"
					placeholder="All accounts"
					@update:model-value="(v: string) => setFilter('provider_account', v)"
				/>
			</IcField>
			<IcButton
				v-if="status || account || search"
				size="sm"
				variant="ghost"
				@click="
					search = '';
					router.replace({ query: {} });
				"
				>Clear</IcButton
			>
		</div>

		<IcCard v-if="inventory.error && !inventory.servers.length" :padded="false"
			><ErrorState :error="inventory.error" @retry="load"
		/></IcCard>
		<div
			v-else-if="inventory.loading && !inventory.servers.length"
			class="flex flex-col gap-2"
		>
			<IcSkeleton v-for="i in 3" :key="i" variant="block" />
		</div>
		<IcEmptyState
			v-else-if="!rows.length"
			title="No servers"
			:description="
				status || account || search
					? 'Nothing matches these filters.'
					: 'Provision a server or run inventory.sync on a provider account.'
			"
		/>
		<IcCard v-else :padded="false">
			<div class="overflow-x-auto">
				<table class="w-full border-collapse text-sm" data-testid="servers-table">
					<thead>
						<tr class="border-b border-line">
							<th scope="col" class="eyebrow px-4 py-2.5 text-start font-medium">
								Server
							</th>
							<th scope="col" class="eyebrow px-4 py-2.5 text-start font-medium">
								Status
							</th>
							<th scope="col" class="eyebrow px-4 py-2.5 text-start font-medium">
								Where
							</th>
							<th scope="col" class="eyebrow px-4 py-2.5 text-start font-medium">
								Load
							</th>
							<th scope="col" class="eyebrow px-4 py-2.5 text-end font-medium">
								Runs
							</th>
							<th scope="col" class="eyebrow px-4 py-2.5 text-end font-medium">
								Heartbeat
							</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="s in rows"
							:key="s.name"
							class="cursor-pointer border-b border-line hover:bg-surface-2"
							:class="{ 'opacity-60': s.status === 'Archived' }"
							role="row"
							tabindex="0"
							:aria-label="`${s.hostname} ${s.name}`"
							data-testid="server-row"
							@click="router.push(`/servers/${encodeURIComponent(s.name)}`)"
							@keydown.enter="router.push(`/servers/${encodeURIComponent(s.name)}`)"
						>
							<td class="px-4 py-3">
								<div class="flex flex-col gap-0.5">
									<span class="font-medium">{{ s.hostname }}</span>
									<span class="font-mono text-xs text-fg-subtle"
										>{{ s.name
										}}<span v-if="s.public_ip">
											· {{ s.public_ip }}</span
										></span
									>
									<span v-if="s.tags.length" class="flex flex-wrap gap-1"
										><IcBadge v-for="t in s.tags.slice(0, 4)" :key="t" mono>{{
											t
										}}</IcBadge></span
									>
								</div>
							</td>
							<td class="px-4 py-3">
								<IcStatusBadge entity="server" :status="s.status" /><span
									class="mt-1 block text-2xs text-fg-subtle uppercase"
									>{{ s.role }}</span
								>
							</td>
							<td class="px-4 py-3">
								<div class="flex flex-col gap-1">
									<IcProviderBadge :provider="s.provider" /><span
										class="font-mono text-xs text-fg-muted"
										>{{ s.region }} · {{ s.size }}</span
									><span class="text-2xs text-fg-subtle">{{
										s.provider_account
									}}</span>
								</div>
							</td>
							<td class="px-4 py-3">
								<div v-if="s.hb" class="flex flex-wrap gap-1.5">
									<IcMetricChip label="cpu" :value="s.hb.cpu" /><IcMetricChip
										label="ram"
										:value="s.hb.ram"
									/><IcMetricChip label="disk" :value="s.hb.disk" />
								</div>
								<span v-else class="text-xs text-fg-subtle">{{
									s.status === "Archived" ? "—" : "no reading yet"
								}}</span>
							</td>
							<td class="px-4 py-3 text-end text-xs">
								<RouterLink
									:to="{ path: '/sites', query: { server: s.name } }"
									class="hover:underline"
									@click.stop
									>{{ s.site_count }} site{{
										s.site_count === 1 ? "" : "s"
									}}</RouterLink
								><span class="block text-fg-subtle"
									>{{ s.bench_count }} bench{{
										s.bench_count === 1 ? "" : "es"
									}}</span
								>
							</td>
							<td class="px-4 py-3 text-end">
								<IcBadge
									:tone="heartbeatTone(s)"
									dot
									:live="heartbeatTone(s) === 'healthy'"
									>{{
										s.last_heartbeat
											? relativeTime(s.last_heartbeat, now)
											: "never"
									}}</IcBadge
								>
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</IcCard>
	</div>
</template>
