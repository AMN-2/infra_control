<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { Pencil, Trash2 } from "lucide-vue-next";
import {
	IcBadge,
	IcButton,
	IcCard,
	IcConfirmDialog,
	IcEmptyState,
	IcField,
	IcIconButton,
	IcPageHeader,
	IcSelect,
	IcSkeleton,
	IcStatusBadge,
	IcSwitch,
	IcTabs,
	pushToast,
} from "@/design/components";
import ErrorState from "@/features/system/ErrorState.vue";
import { relativeTime } from "@/lib/time";
import { useAlertRulesStore } from "@/stores/alertRules";
import { useAlertsStore, type Alert } from "@/stores/alerts";
import { useSessionStore } from "@/stores/session";
import RuleDialog from "./RuleDialog.vue";
import { describeRule, type AlertRule } from "./ruleForm";

/**
 * Alerts (B3.2): firing first, acknowledge in place (the one optimistic action), and the rule
 * editor for Infra Admin. Realtime: a fired alert refetches the list, a resolved one is patched.
 */
const alerts = useAlertsStore();
const rules = useAlertRulesStore();
const session = useSessionStore();

const tab = ref<"alerts" | "rules">("alerts");
const status = ref("");
const severity = ref("");
const tabs = computed(() => [
	{ id: "alerts", label: "Alerts", count: alerts.firing.length },
	{ id: "rules", label: "Rules", count: rules.items.length },
]);
const query = computed(() => ({
	...(status.value ? { status: status.value as Alert["status"] } : {}),
	...(severity.value ? { severity: severity.value as Alert["severity"] } : {}),
}));
const statusOptions = [
	{ value: "", label: "All statuses" },
	{ value: "firing", label: "Firing" },
	{ value: "acknowledged", label: "Acknowledged" },
	{ value: "resolved", label: "Resolved" },
];
const severityOptions = [
	{ value: "", label: "All severities" },
	{ value: "critical", label: "Critical" },
	{ value: "warning", label: "Warning" },
	{ value: "info", label: "Info" },
];

function targetRoute(a: Alert): { name: string; params: { name: string } } | null {
	if (a.target.target_doctype === "Server")
		return { name: "server", params: { name: a.target.target_name } };
	if (a.target.target_doctype === "Site")
		return { name: "site", params: { name: a.target.target_name } };
	return null;
}
async function ack(a: Alert): Promise<void> {
	await alerts.acknowledge(a.name, session.user);
	if (alerts.error)
		pushToast({
			title: "Could not acknowledge",
			description: alerts.error.message,
			tone: "down",
		});
}

// Rules
const editorOpen = ref(false);
const editing = ref<AlertRule | null>(null);
const deleting = ref<AlertRule | null>(null);
function openCreate(): void {
	editing.value = null;
	editorOpen.value = true;
}
function openEdit(rule: AlertRule): void {
	editing.value = rule;
	editorOpen.value = true;
}
function onSaved(rule: AlertRule): void {
	pushToast({
		title: editing.value ? "Rule updated" : "Rule created",
		description: rule.title,
		tone: "healthy",
	});
}
async function toggle(rule: AlertRule, enabled: boolean): Promise<void> {
	await rules.setEnabled(rule.name, enabled);
	if (rules.saveError)
		pushToast({ title: "Could not update rule", description: rules.saveError, tone: "down" });
}
async function confirmDelete(): Promise<void> {
	const rule = deleting.value;
	if (!rule) return;
	const ok = await rules.remove(rule.name);
	if (ok) pushToast({ title: "Rule deleted", description: rule.title, tone: "neutral" });
	else
		pushToast({
			title: "Could not delete rule",
			description: rules.saveError ?? "",
			tone: "down",
		});
	deleting.value = null;
}

onMounted(() => {
	alerts.subscribe();
	void alerts.fetchList(query.value);
	void rules.fetchList();
});
watch(query, (q) => void alerts.fetchList(q));
</script>

<template>
	<div class="flex flex-col gap-6">
		<IcPageHeader
			title="Alerts"
			subtitle="What is firing now, who acknowledged it, and the rules behind it."
		>
			<template #actions>
				<IcButton
					v-if="session.isAdmin && tab === 'rules'"
					variant="primary"
					data-testid="rule-new"
					@click="openCreate"
					>New metric rule</IcButton
				>
			</template>
		</IcPageHeader>
		<IcTabs v-model="tab" :tabs="tabs" label="Alerts sections" />

		<!-- Alerts -->
		<section
			v-if="tab === 'alerts'"
			id="panel-alerts"
			role="tabpanel"
			aria-labelledby="tab-alerts"
			class="flex flex-col gap-4"
		>
			<div class="flex flex-wrap items-end gap-3">
				<IcField for-id="alerts-status" label="Status">
					<IcSelect
						id="alerts-status"
						v-model="status"
						:options="statusOptions"
						data-testid="alerts-status"
					/>
				</IcField>
				<IcField for-id="alerts-severity" label="Severity">
					<IcSelect
						id="alerts-severity"
						v-model="severity"
						:options="severityOptions"
						data-testid="alerts-severity"
					/>
				</IcField>
				<span class="ms-auto text-xs text-fg-subtle" data-testid="alerts-firing-count"
					>{{ alerts.firing.length }} firing</span
				>
			</div>
			<IcCard v-if="alerts.error && !alerts.items.length" :padded="false">
				<ErrorState :error="alerts.error" @retry="alerts.fetchList(query)" />
			</IcCard>
			<div v-else-if="alerts.loading && !alerts.items.length" class="flex flex-col gap-2">
				<IcSkeleton v-for="i in 4" :key="i" variant="block" />
			</div>
			<IcEmptyState
				v-else-if="!alerts.items.length"
				title="No alerts"
				description="Nothing matches these filters. Firing alerts appear here within a minute."
			/>
			<IcCard v-else :padded="false">
				<ul class="divide-y divide-line" data-testid="alerts-list">
					<li
						v-for="a in alerts.items"
						:key="a.name"
						class="flex flex-col gap-2 border-s-2 px-4 py-3 md:flex-row md:items-center md:gap-4"
						:class="{
							'border-down': a.severity === 'critical',
							'border-degraded': a.severity === 'warning',
							'border-running': a.severity === 'info',
							'opacity-70': a.status === 'resolved',
						}"
						:data-status="a.status"
						:data-testid="`alert-${a.name}`"
					>
						<div class="flex min-w-0 flex-1 flex-col gap-1">
							<div class="flex flex-wrap items-center gap-2">
								<IcStatusBadge entity="severity" :status="a.severity" />
								<IcStatusBadge entity="alert" :status="a.status" />
								<span class="truncate text-sm font-medium">{{ a.message }}</span>
							</div>
							<div
								class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-fg-subtle"
							>
								<RouterLink
									v-if="targetRoute(a)"
									:to="targetRoute(a)!"
									class="font-mono text-fg-muted hover:text-fg hover:underline"
									>{{ a.target.target_name }}</RouterLink
								>
								<span v-else class="font-mono">{{ a.target.target_name }}</span>
								<span>{{ a.rule_title }}</span>
								<span :title="a.fired_at"
									>fired {{ relativeTime(a.fired_at) }}</span
								>
								<span v-if="a.acknowledged_by"
									>acknowledged by {{ a.acknowledged_by }}</span
								>
								<span v-if="a.resolved_at" :title="a.resolved_at"
									>resolved {{ relativeTime(a.resolved_at) }}</span
								>
							</div>
						</div>
						<IcButton
							v-if="a.status === 'firing' && session.canOperate"
							size="sm"
							:data-testid="`ack-${a.name}`"
							@click="ack(a)"
							>Acknowledge</IcButton
						>
					</li>
				</ul>
				<div v-if="alerts.nextCursor" class="p-3">
					<IcButton
						size="sm"
						:loading="alerts.loading"
						@click="alerts.fetchList(query, alerts.nextCursor ?? undefined)"
						>Load more</IcButton
					>
				</div>
			</IcCard>
		</section>

		<!-- Rules -->
		<section
			v-else
			id="panel-rules"
			role="tabpanel"
			aria-labelledby="tab-rules"
			class="flex flex-col gap-4"
		>
			<IcCard v-if="rules.error && !rules.items.length" :padded="false">
				<ErrorState :error="rules.error" @retry="rules.fetchList()" />
			</IcCard>
			<div v-else-if="rules.loading && !rules.items.length" class="flex flex-col gap-2">
				<IcSkeleton v-for="i in 4" :key="i" variant="block" />
			</div>
			<IcEmptyState
				v-else-if="!rules.items.length"
				title="No rules"
				description="Built-in rules are created on install."
			/>
			<IcCard v-else :padded="false">
				<ul class="divide-y divide-line" data-testid="rules-list">
					<li
						v-for="r in rules.items"
						:key="r.name"
						class="flex flex-col gap-2 px-4 py-3 md:flex-row md:items-center md:gap-4"
						:class="{ 'opacity-60': !r.enabled }"
						:data-testid="`rule-${r.name}`"
					>
						<div class="flex min-w-0 flex-1 flex-col gap-1">
							<div class="flex flex-wrap items-center gap-2">
								<span class="text-sm font-medium">{{ r.title }}</span>
								<IcStatusBadge entity="severity" :status="r.severity" />
								<IcBadge mono>{{ r.kind }}</IcBadge>
								<IcBadge v-if="r.builtin">built-in</IcBadge>
							</div>
							<div
								class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-fg-subtle"
							>
								<span class="font-mono text-fg-muted">{{ r.name }}</span>
								<span>{{ r.target_doctype }}</span>
								<span>{{ describeRule(r) }}</span>
								<span>via {{ r.channels.join(", ") || "no channel" }}</span>
							</div>
						</div>
						<div class="flex items-center gap-2">
							<IcSwitch
								:model-value="r.enabled"
								:label="`${r.title} enabled`"
								:disabled="!session.isAdmin"
								:data-testid="`rule-toggle-${r.name}`"
								@update:model-value="(on) => toggle(r, on)"
							/>
							<IcIconButton
								v-if="session.isAdmin"
								label="Edit rule"
								size="sm"
								:data-testid="`rule-edit-${r.name}`"
								@click="openEdit(r)"
							>
								<Pencil :size="14" />
							</IcIconButton>
							<IcIconButton
								v-if="session.isAdmin && !r.builtin"
								label="Delete rule"
								size="sm"
								:data-testid="`rule-delete-${r.name}`"
								@click="deleting = r"
							>
								<Trash2 :size="14" />
							</IcIconButton>
						</div>
					</li>
				</ul>
				<div v-if="rules.nextCursor" class="p-3">
					<IcButton
						size="sm"
						:loading="rules.loading"
						@click="rules.fetchList(rules.nextCursor ?? undefined)"
						>Load more</IcButton
					>
				</div>
			</IcCard>
		</section>

		<RuleDialog v-model="editorOpen" :rule="editing" @saved="onSaved" />
		<IcConfirmDialog
			:model-value="deleting !== null"
			title="Delete rule"
			description="Its historical alerts are kept. Built-in rules cannot be deleted."
			:expected="deleting?.name ?? ''"
			confirm-label="Delete"
			:busy="rules.saving"
			@update:model-value="
				(v) => {
					if (!v) deleting = null;
				}
			"
			@confirm="confirmDelete"
		/>
	</div>
</template>
