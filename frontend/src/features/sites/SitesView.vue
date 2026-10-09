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
	IcStatusBadge,
} from "@/design/components";
import ErrorState from "@/features/system/ErrorState.vue";
import { relativeTime } from "@/lib/time";
import { useInventoryStore, type Site } from "@/stores/inventory";
import { useSessionStore } from "@/stores/session";
import CreateSiteDialog from "./CreateSiteDialog.vue";

/**
 * Sites: status tiles that filter, search, and one table where the things that need
 * attention stand out: a stale or missing backup, a certificate about to expire, a site in
 * maintenance or broken. `status`, `bench` and `server` come from the URL.
 */
const inventory = useInventoryStore();
const session = useSessionStore();
const route = useRoute();
const router = useRouter();
const creating = ref(false);
const search = ref("");
const now = ref(Date.now());
let clock: ReturnType<typeof setInterval> | undefined;

const STATUSES = ["Active", "Maintenance", "Suspended", "Broken", "Pending", "Archived"] as const;
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
function setFilter(key: "status" | "bench" | "server", v: string): void {
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
watch([status, bench, server], load);

const counts = computed(() => {
	const c: Record<string, number> = {};
	for (const s of inventory.sites) c[s.status] = (c[s.status] ?? 0) + 1;
	return c;
});
const DAY = 86_400_000;
const rows = computed(() => {
	const text = search.value.trim().toLowerCase();
	const order: Record<Site["status"], number> = {
		Broken: 0,
		Maintenance: 1,
		Pending: 2,
		Suspended: 3,
		Active: 4,
		Archived: 5,
	};
	return inventory.sites
		.filter(
			(s) =>
				!text ||
				[
					s.domain,
					s.name,
					s.bench,
					s.server ?? "",
					s.plan ?? "",
					...s.custom_domains,
				].some((v) => v.toLowerCase().includes(text))
		)
		.sort((a, b) => order[a.status] - order[b.status] || a.domain.localeCompare(b.domain))
		.map((s) => {
			const backupAge = s.last_backup ? (now.value - Date.parse(s.last_backup)) / DAY : null;
			const sslDays = s.ssl_expiry
				? Math.round((Date.parse(s.ssl_expiry) - now.value) / DAY)
				: null;
			return { ...s, backupAge, sslDays };
		});
});
function backupTone(
	age: number | null,
	status: Site["status"]
): "healthy" | "degraded" | "down" | "neutral" {
	if (status === "Archived") return "neutral";
	if (age === null) return "down";
	return age <= 1.5 ? "healthy" : age <= 7 ? "degraded" : "down";
}
function sslTone(days: number | null): "healthy" | "degraded" | "down" | "neutral" {
	if (days === null) return "neutral";
	return days > 14 ? "healthy" : days > 0 ? "degraded" : "down";
}
const statTone = {
	Active: "healthy",
	Maintenance: "degraded",
	Suspended: "neutral",
	Broken: "down",
	Pending: "running",
	Archived: "neutral",
} as const;
</script>

<template>
	<div class="flex flex-col gap-5">
		<IcPageHeader
			title="Sites"
			subtitle="Every client site, with the two things that must never slip: a fresh backup and a valid certificate."
		>
			<template #actions>
				<IcButton
					v-if="session.canOperate"
					variant="primary"
					data-testid="site-new"
					@click="creating = true"
					>New site</IcButton
				>
			</template>
		</IcPageHeader>
		<CreateSiteDialog v-model="creating" />

		<div class="grid grid-cols-2 gap-3 md:grid-cols-6" data-testid="sites-stats">
			<button
				v-for="s in STATUSES"
				:key="s"
				type="button"
				class="rounded border text-start transition-colors"
				:class="
					status === s ? 'border-accent bg-surface-2' : 'border-line hover:bg-surface-2'
				"
				:aria-pressed="status === s"
				:data-testid="`sites-stat-${s}`"
				@click="setFilter('status', status === s ? '' : s)"
			>
				<IcStat :label="s" :value="counts[s] ?? 0" :tone="statTone[s]" :animate="false" />
			</button>
		</div>

		<div class="flex flex-wrap items-end gap-3">
			<IcField for-id="sites-search" label="Search" class="min-w-64 flex-1">
				<IcInput
					id="sites-search"
					v-model="search"
					type="search"
					mono
					placeholder="domain, bench, server, plan…"
					data-testid="sites-search"
				/>
			</IcField>
			<IcField for-id="sites-status" label="Status">
				<IcSelect
					id="sites-status"
					:model-value="status"
					:options="STATUSES.map((s) => ({ value: s, label: s }))"
					placeholder="All statuses"
					@update:model-value="(v: string) => setFilter('status', v)"
				/>
			</IcField>
			<IcBadge v-if="bench" mono>bench {{ bench }}</IcBadge>
			<IcBadge v-if="server" mono>server {{ server }}</IcBadge>
			<IcButton
				v-if="status || bench || server || search"
				size="sm"
				variant="ghost"
				@click="
					search = '';
					router.replace({ query: {} });
				"
				>Clear</IcButton
			>
		</div>

		<IcCard v-if="inventory.error && !inventory.sites.length" :padded="false"
			><ErrorState :error="inventory.error" @retry="load"
		/></IcCard>
		<div v-else-if="inventory.loading && !inventory.sites.length" class="flex flex-col gap-2">
			<IcSkeleton v-for="i in 3" :key="i" variant="block" />
		</div>
		<IcEmptyState
			v-else-if="!rows.length"
			title="No sites"
			:description="
				status || bench || server || search
					? 'Nothing matches these filters.'
					: 'Create a site on a bench or run inventory.sync.'
			"
		/>
		<IcCard v-else :padded="false">
			<div class="overflow-x-auto">
				<table class="w-full border-collapse text-sm" data-testid="sites-table">
					<thead>
						<tr class="border-b border-line">
							<th scope="col" class="eyebrow px-4 py-2.5 text-start font-medium">
								Site
							</th>
							<th scope="col" class="eyebrow px-4 py-2.5 text-start font-medium">
								Status
							</th>
							<th scope="col" class="eyebrow px-4 py-2.5 text-start font-medium">
								Runs on
							</th>
							<th scope="col" class="eyebrow px-4 py-2.5 text-end font-medium">
								Database
							</th>
							<th scope="col" class="eyebrow px-4 py-2.5 text-end font-medium">
								Last backup
							</th>
							<th scope="col" class="eyebrow px-4 py-2.5 text-end font-medium">
								Certificate
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
							:aria-label="s.domain"
							data-testid="site-row"
							@click="router.push(`/sites/${encodeURIComponent(s.name)}`)"
							@keydown.enter="router.push(`/sites/${encodeURIComponent(s.name)}`)"
						>
							<td class="px-4 py-3">
								<div class="flex flex-col gap-0.5">
									<span class="font-mono font-medium">{{ s.domain }}</span>
									<span class="text-xs text-fg-subtle"
										><span v-if="s.plan">{{ s.plan }}</span
										><span v-if="s.plan && s.custom_domains.length"> · </span
										><span v-if="s.custom_domains.length"
											>{{ s.custom_domains.length }} custom domain{{
												s.custom_domains.length === 1 ? "" : "s"
											}}</span
										></span
									>
								</div>
							</td>
							<td class="px-4 py-3">
								<IcStatusBadge entity="site" :status="s.status" />
							</td>
							<td class="px-4 py-3">
								<div class="flex flex-col gap-1">
									<span class="flex items-center gap-2"
										><IcProviderBadge :provider="s.provider" /><RouterLink
											v-if="s.server"
											:to="`/servers/${encodeURIComponent(s.server)}`"
											class="font-mono text-xs hover:underline"
											@click.stop
											>{{ s.server }}</RouterLink
										></span
									>
									<RouterLink
										:to="{ path: '/sites', query: { bench: s.bench } }"
										class="font-mono text-xs text-fg-subtle hover:underline"
										@click.stop
										>{{ s.bench }}</RouterLink
									>
								</div>
							</td>
							<td class="px-4 py-3 text-end font-mono text-xs">
								{{
									s.db_size_mb === null
										? "—"
										: s.db_size_mb >= 1024
											? `${(s.db_size_mb / 1024).toFixed(1)} GB`
											: `${Math.round(s.db_size_mb)} MB`
								}}
							</td>
							<td class="px-4 py-3 text-end">
								<IcBadge :tone="backupTone(s.backupAge, s.status)" dot>{{
									s.last_backup ? relativeTime(s.last_backup, now) : "never"
								}}</IcBadge>
							</td>
							<td class="px-4 py-3 text-end">
								<IcBadge
									:tone="sslTone(s.sslDays)"
									dot
									:title="s.ssl_expiry ?? ''"
									>{{
										s.sslDays === null
											? "—"
											: s.sslDays > 0
												? `${s.sslDays} d left`
												: "expired"
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
