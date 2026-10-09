<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { IcBadge, IcCard, IcSkeleton } from "@/design/components";
import type { Tone } from "@/design/status";
import { useInventoryStore } from "@/stores/inventory";
import { useSecurityStore } from "@/stores/security";
import { useSessionStore } from "@/stores/session";

/**
 * What needs a human now, derived from the inventory (and the security posture for admins):
 * servers down or degraded, sites broken or in maintenance, backups older than 36 hours or
 * missing, certificates expiring within 14 days, failed security checks.
 */
const inventory = useInventoryStore();
const security = useSecurityStore();
const session = useSessionStore();
const now = ref(Date.now());
const DAY = 86_400_000;

interface Item {
	id: string;
	tone: Tone;
	title: string;
	detail: string;
	to: string | { path: string; query: Record<string, string> };
}

const items = computed<Item[]>(() => {
	const out: Item[] = [];
	for (const s of inventory.servers) {
		if (s.status === "Down")
			out.push({
				id: `srv-${s.name}`,
				tone: "down",
				title: `${s.hostname} is down`,
				detail: s.last_heartbeat
					? `no heartbeat since ${new Date(s.last_heartbeat).toLocaleTimeString()}`
					: "never reported",
				to: `/servers/${encodeURIComponent(s.name)}`,
			});
		else if (s.status === "Degraded")
			out.push({
				id: `srv-${s.name}`,
				tone: "degraded",
				title: `${s.hostname} is degraded`,
				detail: "a resource is at or above 90 %",
				to: `/servers/${encodeURIComponent(s.name)}`,
			});
	}
	for (const s of inventory.sites) {
		if (s.status === "Archived") continue;
		if (s.status === "Broken")
			out.push({
				id: `site-${s.name}-b`,
				tone: "down",
				title: `${s.domain} is broken`,
				detail: "open the site and its last jobs",
				to: `/sites/${encodeURIComponent(s.name)}`,
			});
		else if (s.status === "Maintenance")
			out.push({
				id: `site-${s.name}-m`,
				tone: "degraded",
				title: `${s.domain} is in maintenance`,
				detail: "lift it when the work is done",
				to: `/sites/${encodeURIComponent(s.name)}`,
			});
		const age = s.last_backup ? (now.value - Date.parse(s.last_backup)) / DAY : null;
		if (age === null)
			out.push({
				id: `site-${s.name}-nb`,
				tone: "down",
				title: `${s.domain} was never backed up`,
				detail: "set a schedule or run site.backup",
				to: `/sites/${encodeURIComponent(s.name)}`,
			});
		else if (age > 1.5)
			out.push({
				id: `site-${s.name}-ob`,
				tone: age > 7 ? "down" : "degraded",
				title: `${s.domain}: last backup ${Math.round(age)} day(s) ago`,
				detail: "schedule it from the Backups tab",
				to: `/sites/${encodeURIComponent(s.name)}`,
			});
		if (s.ssl_expiry) {
			const days = Math.round((Date.parse(s.ssl_expiry) - now.value) / DAY);
			if (days <= 14)
				out.push({
					id: `site-${s.name}-ssl`,
					tone: days <= 0 ? "down" : "degraded",
					title:
						days <= 0
							? `${s.domain}: certificate expired`
							: `${s.domain}: certificate expires in ${days} day(s)`,
					detail: "renew before clients notice",
					to: `/sites/${encodeURIComponent(s.name)}`,
				});
		}
	}
	if (session.isAdmin && security.posture) {
		const fails = security.posture.checks.filter((c) => c.status === "fail");
		if (fails.length)
			out.push({
				id: "security",
				tone: "down",
				title: `${fails.length} security check(s) failing`,
				detail: fails
					.map((f) => f.title)
					.slice(0, 3)
					.join(", "),
				to: "/settings/security",
			});
	}
	const rank: Record<Tone, number> = {
		down: 0,
		degraded: 1,
		running: 2,
		healthy: 3,
		neutral: 4,
	};
	return out.sort((a, b) => rank[a.tone] - rank[b.tone]);
});
const loading = computed(
	() => inventory.loading && !inventory.servers.length && !inventory.sites.length
);

onMounted(() => {
	if (!inventory.servers.length) void inventory.fetchServers();
	if (!inventory.sites.length) void inventory.fetchSites();
	if (session.isAdmin && !security.posture) void security.fetchPosture();
});
</script>

<template>
	<IcCard
		title="Needs attention"
		:subtitle="
			items.length
				? `${items.length} item(s), worst first`
				: 'Nothing needs a human right now'
		"
		:padded="false"
		data-testid="attention"
	>
		<IcSkeleton v-if="loading" :lines="3" class="p-4" />
		<p v-else-if="!items.length" class="px-4 py-6 text-center text-sm text-fg-subtle">
			All servers report, every site has a recent backup and a valid certificate.
		</p>
		<ul v-else class="divide-y divide-line">
			<li v-for="it in items.slice(0, 12)" :key="it.id">
				<RouterLink
					:to="it.to"
					class="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-2"
					:data-testid="`attention-${it.id}`"
				>
					<IcBadge :tone="it.tone" dot uppercase class="w-20 justify-center">{{
						it.tone === "down" ? "urgent" : "soon"
					}}</IcBadge>
					<span class="flex min-w-0 flex-col"
						><span class="truncate text-sm">{{ it.title }}</span
						><span class="truncate text-xs text-fg-subtle">{{ it.detail }}</span></span
					>
				</RouterLink>
			</li>
			<li v-if="items.length > 12" class="px-4 py-2 text-xs text-fg-subtle">
				and {{ items.length - 12 }} more
			</li>
		</ul>
	</IcCard>
</template>
