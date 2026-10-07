<script setup lang="ts">
import { computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
	IcCard,
	IcMetricChip,
	IcPageHeader,
	IcProviderBadge,
	IcSelect,
	IcStatusBadge,
	IcTable,
	type Column,
} from "@/design/components";
import ErrorState from "@/features/system/ErrorState.vue";
import { relativeTime } from "@/lib/time";
import { useInventoryStore, type Server } from "@/stores/inventory";

/** Servers list with the filters the other screens link to (`status`, `provider_account`). */
const inventory = useInventoryStore();
const route = useRoute();
const router = useRouter();

const statusOptions = ["Provisioning", "Active", "Degraded", "Down", "Archived"].map((s) => ({
	value: s,
	label: s,
}));
const status = computed(() => {
	const s = route.query.status;
	return typeof s === "string" ? s : "";
});
const account = computed(() => {
	const a = route.query.provider_account;
	return typeof a === "string" ? a : "";
});

function load(): void {
	void inventory.fetchServers({
		...(status.value ? { status: status.value as Server["status"] } : {}),
		...(account.value ? { provider_account: account.value } : {}),
	});
}
onMounted(() => {
	inventory.subscribe();
	load();
});
watch([status, account], load);

function setStatus(v: string): void {
	void router.replace({ query: { ...route.query, status: v || undefined } });
}

type Row = Server & { heartbeat: string; cpu: number | null; disk: number | null };
const rows = computed<Row[]>(() =>
	inventory.servers.map((s) => {
		const hb = inventory.heartbeats[s.name];
		return {
			...s,
			heartbeat: s.last_heartbeat ? relativeTime(s.last_heartbeat) : "never",
			cpu: hb?.cpu ?? null,
			disk: hb?.disk ?? null,
		};
	})
);
const columns: Column<Row>[] = [
	{ key: "hostname", label: "Server", mono: true },
	{ key: "status", label: "Status" },
	{ key: "provider", label: "Provider" },
	{ key: "region", label: "Region", mono: true },
	{ key: "size", label: "Size", mono: true },
	{ key: "cpu", label: "CPU", align: "end" },
	{ key: "disk", label: "Disk", align: "end" },
	{ key: "site_count", label: "Sites", align: "end" },
	{ key: "heartbeat", label: "Heartbeat", align: "end" },
];
</script>

<template>
	<div class="flex flex-col gap-4">
		<IcPageHeader
			title="Servers"
			:subtitle="account ? `Provider account ${account}` : undefined"
		/>
		<div class="flex flex-wrap items-center gap-3">
			<label class="text-xs text-fg-muted" for="servers-status">Status</label>
			<div class="w-44">
				<IcSelect
					id="servers-status"
					:model-value="status"
					:options="statusOptions"
					placeholder="All statuses"
					@update:model-value="setStatus"
				/>
			</div>
		</div>
		<IcCard v-if="inventory.error && !inventory.servers.length" :padded="false">
			<ErrorState :error="inventory.error" @retry="load" />
		</IcCard>
		<IcCard v-else :padded="false">
			<IcTable
				:columns="columns"
				:rows="rows"
				row-key="name"
				:loading="inventory.loading && !rows.length"
				clickable
				empty-title="No servers"
				:empty-description="
					status || account
						? 'Nothing matches these filters.'
						: 'Provision a server or run inventory.sync on a provider account.'
				"
				@row-click="(r: Row) => router.push(`/servers/${encodeURIComponent(r.name)}`)"
			>
				<template #cell-status="{ row }">
					<IcStatusBadge entity="server" :status="row.status" />
				</template>
				<template #cell-provider="{ row }">
					<IcProviderBadge :provider="row.provider" />
				</template>
				<template #cell-cpu="{ row }">
					<IcMetricChip label="cpu" :value="row.cpu" />
				</template>
				<template #cell-disk="{ row }">
					<IcMetricChip label="disk" :value="row.disk" />
				</template>
			</IcTable>
		</IcCard>
	</div>
</template>
