<script setup lang="ts">
import { onMounted, ref, useTemplateRef } from "vue";
import { Play, Plus, RefreshCw, Search, Server as ServerIcon } from "lucide-vue-next";
import ShowcaseSection from "../ShowcaseSection.vue";
import {
	IcBadge,
	IcBreadcrumbs,
	IcButton,
	IcCard,
	IcConfirmDialog,
	IcDialog,
	IcEmptyState,
	IcField,
	IcIconButton,
	IcInput,
	IcKbd,
	IcMenu,
	IcMetricChip,
	IcPageHeader,
	IcProgress,
	IcProviderBadge,
	IcSelect,
	IcSkeleton,
	IcSparkline,
	IcStat,
	IcStatusBadge,
	IcSwitch,
	IcTable,
	IcTabs,
	IcTerminal,
	IcTimeline,
	IcTooltip,
	pushToast,
	type Column,
	type TimelineStep,
} from "@/design/components";

// Sample data for the showcase only.
interface Row extends Record<string, unknown> {
	name: string;
	hostname: string;
	status: string;
	provider: "digitalocean" | "frappe_cloud";
	cpu: number;
}
const columns: Column<Row>[] = [
	{ key: "hostname", label: "Server", mono: true },
	{ key: "status", label: "Status" },
	{ key: "provider", label: "Provider" },
	{ key: "cpu", label: "CPU", align: "end" },
];
const rows: Row[] = [
	{
		name: "SRV-0001",
		hostname: "app-01.fra1",
		status: "Active",
		provider: "digitalocean",
		cpu: 23,
	},
	{
		name: "SRV-0002",
		hostname: "app-02.fra1",
		status: "Degraded",
		provider: "digitalocean",
		cpu: 91,
	},
	{
		name: "SRV-0003",
		hostname: "app-03.fra1",
		status: "Provisioning",
		provider: "digitalocean",
		cpu: 0,
	},
];
const tableLoading = ref(false);
const tab = ref("steps");
const steps: TimelineStep[] = [
	{
		idx: 0,
		title: "Acquire server lock",
		status: "Success",
		started_at: "2026-10-07T09:30:04Z",
		ended_at: "2026-10-07T09:30:04Z",
		output: "lock infra:lock:server:SRV-0001 acquired",
	},
	{
		idx: 1,
		title: "Backup database and files",
		status: "Success",
		started_at: "2026-10-07T09:30:05Z",
		ended_at: "2026-10-07T09:31:20Z",
		output: "Backup saved: 20261007_093010-database.sql.gz (96.3 MB)",
	},
	{
		idx: 2,
		title: "bench migrate",
		status: "Running",
		started_at: "2026-10-07T09:31:21Z",
		output: "Migrating demo.smartchoice-iq.com\nUpdating DocTypes for erpnext ...",
	},
	{ idx: 3, title: "Disable maintenance mode", status: "Queued" },
];
const dialog = ref(false);
const confirm = ref(false);
const confirmed = ref("");
const text = ref("");
const region = ref("fra1");
const enabled = ref(true);
const progress = ref(40);
const terminal = useTemplateRef<InstanceType<typeof IcTerminal>>("terminal");
let line = 0;
function streamLog(): void {
	for (let i = 0; i < 5; i++)
		terminal.value?.write(`[${++line}] TASK [bench : migrate] changed: [app-01.fra1]\n`);
}
onMounted(() => {
	streamLog();
});
</script>

<template>
	<ShowcaseSection
		id="components"
		title="Components"
		lead="The design system (B1.1): every screen composes these. Each takes its colours, durations and easings from the tokens above and nothing else; the design guard test proves it."
	>
		<div class="flex flex-col gap-8">
			<IcCard title="Buttons, badges, chips" :level="1">
				<div class="flex flex-wrap items-center gap-3" data-testid="buttons">
					<IcButton variant="primary"
						><template #icon><Play :size="14" /></template>Run playbook</IcButton
					>
					<IcButton>Secondary</IcButton>
					<IcButton variant="ghost">Ghost</IcButton>
					<IcButton variant="danger">Reboot</IcButton>
					<IcButton loading>Saving</IcButton>
					<IcButton disabled>Disabled</IcButton>
					<IcIconButton label="Refresh"><RefreshCw :size="16" /></IcIconButton>
					<IcKbd>Ctrl</IcKbd><IcKbd>K</IcKbd>
				</div>
				<div class="mt-4 flex flex-wrap items-center gap-2">
					<IcStatusBadge entity="server" status="Active" />
					<IcStatusBadge entity="server" status="Provisioning" />
					<IcStatusBadge entity="site" status="Maintenance" />
					<IcStatusBadge entity="job" status="Failed" />
					<IcStatusBadge entity="severity" status="critical" />
					<IcStatusBadge entity="severity" status="info" />
					<IcBadge mono>JOB-00042</IcBadge>
					<IcProviderBadge provider="digitalocean" />
					<IcProviderBadge provider="frappe_cloud" long />
					<IcMetricChip label="cpu" :value="23" />
					<IcMetricChip label="disk" :value="88" />
					<IcMetricChip label="ram" :value="null" />
					<IcTooltip text="Shown on hover and focus"
						><IcButton size="sm">Tooltip</IcButton></IcTooltip
					>
				</div>
			</IcCard>

			<div class="grid grid-cols-4 gap-3">
				<IcStat label="Servers" :value="18" note="17 active · 1 degraded" tone="healthy">
					<IcSparkline
						:points="[14, 14, 15, 15, 16, 16, 16, 17, 18, 18]"
						tone="healthy"
					/>
				</IcStat>
				<IcStat label="Running jobs" :value="3" note="1 bulk rollout" tone="running" />
				<IcCard :level="2" :padded="false"><IcSkeleton variant="block" /></IcCard>
				<IcCard :level="2" live title="Live card"
					><p class="text-xs text-fg-muted">Glows while a job runs on it.</p></IcCard
				>
			</div>

			<IcCard title="Table, tabs, progress">
				<template #actions>
					<IcSwitch v-model="tableLoading" label="Loading state" />
				</template>
				<IcTabs
					v-model="tab"
					label="Example tabs"
					:tabs="[
						{ id: 'steps', label: 'Steps', count: 4 },
						{ id: 'logs', label: 'Logs' },
						{ id: 'meta', label: 'Metadata' },
					]"
				/>
				<div class="mt-4 flex flex-col gap-4">
					<IcTable
						:columns="columns"
						:rows="rows"
						row-key="name"
						:loading="tableLoading"
						clickable
						selected="SRV-0002"
						data-testid="demo-table"
					>
						<template #cell-status="{ value }"
							><IcStatusBadge entity="server" :status="String(value)"
						/></template>
						<template #cell-provider="{ row }"
							><IcProviderBadge :provider="row.provider"
						/></template>
						<template #cell-cpu="{ row }"
							><IcMetricChip label="" :value="row.cpu"
						/></template>
					</IcTable>
					<IcProgress :value="progress" label="Job progress" />
					<div class="flex gap-2">
						<IcButton size="sm" @click="progress = Math.min(100, progress + 20)"
							>+20%</IcButton
						>
						<IcButton size="sm" variant="ghost" @click="progress = 0">Reset</IcButton>
					</div>
				</div>
			</IcCard>

			<div class="grid grid-cols-2 gap-6">
				<IcCard
					title="Job timeline"
					subtitle="The running step is expanded; finished steps collapse."
				>
					<IcTimeline :steps="steps" />
				</IcCard>
				<IcCard
					title="Terminal"
					subtitle="xterm.js, lazy-loaded; chunks flush at most every 50 ms."
				>
					<template #actions
						><IcButton size="sm" @click="streamLog">Stream 5 lines</IcButton></template
					>
					<IcTerminal ref="terminal" :rows="10" />
				</IcCard>
			</div>

			<IcCard title="Forms, dialogs, menus, toasts">
				<div class="grid grid-cols-3 gap-4">
					<IcField for-id="demo-domain" label="Domain" hint="Public hostname" required>
						<IcInput
							id="demo-domain"
							v-model="text"
							placeholder="erp.client.iq"
							mono
						/>
					</IcField>
					<IcField for-id="demo-region" label="Region" error="Region is not available">
						<IcSelect
							id="demo-region"
							v-model="region"
							:options="[
								{ value: 'fra1', label: 'Frankfurt 1' },
								{ value: 'ams3', label: 'Amsterdam 3' },
							]"
						/>
					</IcField>
					<IcField label="Enabled"
						><IcSwitch v-model="enabled" label="Enabled"
					/></IcField>
				</div>
				<div class="mt-4 flex flex-wrap items-center gap-3">
					<IcButton @click="dialog = true">Open dialog</IcButton>
					<IcButton variant="danger" data-testid="open-confirm" @click="confirm = true"
						>Typed confirmation</IcButton
					>
					<IcMenu
						label="Actions"
						:items="[
							{ id: 'backup', label: 'Backup site', kbd: 'B' },
							{ id: 'migrate', label: 'Migrate', description: 'Backs up first' },
							{ id: 'restore', label: 'Restore…', tone: 'down' },
							{ id: 'archive', label: 'Archive', disabled: true },
						]"
						@select="(id) => pushToast({ title: `Selected ${id}` })"
					>
						<template #trigger
							><IcButton
								><template #icon><Plus :size="14" /></template>Actions</IcButton
							></template
						>
					</IcMenu>
					<IcButton
						variant="ghost"
						data-testid="push-toast"
						@click="
							pushToast({
								title: 'Job JOB-00042 finished',
								description: 'Migrate site · demo.smartchoice-iq.com',
								tone: 'healthy',
							})
						"
						>Toast</IcButton
					>
					<span
						v-if="confirmed"
						class="font-mono text-xs text-fg-subtle"
						data-testid="confirmed"
						>confirmed: {{ confirmed }}</span
					>
				</div>
				<IcDialog
					v-model="dialog"
					title="Add custom domain"
					description="nginx, certbot and DNS are configured by the playbook."
				>
					<IcField for-id="dlg-domain" label="Domain"
						><IcInput id="dlg-domain" placeholder="shop.client.iq" mono autofocus
					/></IcField>
					<template #footer="{ close }">
						<IcButton variant="ghost" @click="close">Cancel</IcButton>
						<IcButton variant="primary" @click="close">Add domain</IcButton>
					</template>
				</IcDialog>
				<IcConfirmDialog
					v-model="confirm"
					title="Reboot SRV-0001"
					description="Every site on this server goes down for about a minute."
					expected="SRV-0001"
					confirm-label="Reboot"
					@confirm="
						(v) => {
							confirmed = v;
							confirm = false;
						}
					"
				/>
			</IcCard>

			<div class="grid grid-cols-2 gap-6">
				<IcCard :padded="false"
					><IcEmptyState
						title="No alerts"
						description="Rules evaluate every minute; this list fills itself."
						><template #icon><Search :size="28" /></template
						><template #action
							><IcButton size="sm">Create rule</IcButton></template
						></IcEmptyState
					></IcCard
				>
				<IcCard>
					<IcPageHeader
						title="app-01.fra1"
						subtitle="s-4vcpu-8gb · fra1"
						mono
						:crumbs="[{ label: 'Servers', to: '/servers' }, { label: 'app-01.fra1' }]"
					>
						<template #badges
							><IcStatusBadge entity="server" status="Active" /><IcProviderBadge
								provider="digitalocean"
						/></template>
						<template #actions
							><IcButton size="sm"
								><template #icon><ServerIcon :size="14" /></template
								>Snapshot</IcButton
							></template
						>
					</IcPageHeader>
					<IcBreadcrumbs
						:items="[
							{ label: 'Sites', to: '/sites' },
							{ label: 'demo.smartchoice-iq.com' },
						]"
					/>
				</IcCard>
			</div>
		</div>
	</ShowcaseSection>
</template>
