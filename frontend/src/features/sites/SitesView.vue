<script setup lang="ts">
import { computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
	IcCard,
	IcPageHeader,
	IcProviderBadge,
	IcSelect,
	IcStatusBadge,
	IcTable,
	type Column,
} from "@/design/components";
import ErrorState from "@/features/system/ErrorState.vue";
import { relativeTime } from "@/lib/time";
import { useInventoryStore, type Site } from "@/stores/inventory";

/** Sites list with the filters other screens link to (`status`, `bench`, `server`). */
const inventory = useInventoryStore();
const route = useRoute();
const router = useRouter();

const statusOptions = ["Pending", "Active", "Maintenance", "Suspended", "Broken", "Archived"].map(
	(s) => ({ value: s, label: s })
);
const q = (key: string): string => {
	const v = route.query[key];
	return typeof v === "string" ? v : "";
};
const status = computed(() => q("status"));
const bench = computed(() => q("bench"));
const server = computed(() => q("server"));

function load(): void {
	void inventory.fetchSites({
		...(status.value ? { status: status.value as Site["status"] } : {}),
		...(bench.value ? { bench: bench.value } : {}),
		...(server.value ? { server: server.value } : {}),
	});
}
onMounted(() => {
	inventory.subscribe();
	load();
});
watch([status, bench, server], load);

function setStatus(v: string): void {
	void router.replace({ query: { ...route.query, status: v || undefined } });
}

type Row = Site & { backup: string; ssl: string; db: string };
const rows = computed<Row[]>(() =>
	inventory.sites.map((s) => ({
		...s,
		backup: s.last_backup ? relativeTime(s.last_backup) : "never",
		ssl: s.ssl_expiry ? relativeTime(s.ssl_expiry) : "",
		db: s.db_size_mb === null ? "" : `${Math.round(s.db_size_mb)} MB`,
	}))
);
const columns: Column<Row>[] = [
	{ key: "domain", label: "Site", mono: true },
	{ key: "status", label: "Status" },
	{ key: "provider", label: "Provider" },
	{ key: "bench", label: "Bench", mono: true },
	{ key: "db", label: "DB", align: "end" },
	{ key: "backup", label: "Last backup", align: "end" },
	{ key: "ssl", label: "SSL expiry", align: "end" },
];
const filterLabel = computed(() =>
	[bench.value && `bench ${bench.value}`, server.value && `server ${server.value}`]
		.filter(Boolean)
		.join(" · ")
);
</script>

<template>
	<div class="flex flex-col gap-4">
		<IcPageHeader title="Sites" :subtitle="filterLabel || undefined" />
		<div class="flex flex-wrap items-center gap-3">
			<label class="text-xs text-fg-muted" for="sites-status">Status</label>
			<div class="w-44">
				<IcSelect
					id="sites-status"
					:model-value="status"
					:options="statusOptions"
					placeholder="All statuses"
					@update:model-value="setStatus"
				/>
			</div>
		</div>
		<IcCard v-if="inventory.error && !inventory.sites.length" :padded="false">
			<ErrorState :error="inventory.error" @retry="load" />
		</IcCard>
		<IcCard v-else :padded="false">
			<IcTable
				:columns="columns"
				:rows="rows"
				row-key="name"
				:loading="inventory.loading && !rows.length"
				clickable
				empty-title="No sites"
				:empty-description="
					status || bench || server
						? 'Nothing matches these filters.'
						: 'Create a site on a bench or run inventory.sync.'
				"
				@row-click="(r: Row) => router.push(`/sites/${encodeURIComponent(r.name)}`)"
			>
				<template #cell-status="{ row }">
					<IcStatusBadge entity="site" :status="row.status" />
				</template>
				<template #cell-provider="{ row }">
					<IcProviderBadge :provider="row.provider" />
				</template>
			</IcTable>
		</IcCard>
	</div>
</template>
