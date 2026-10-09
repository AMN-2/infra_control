<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import {
	IcBadge,
	IcButton,
	IcCard,
	IcEmptyState,
	IcField,
	IcInput,
	IcPageHeader,
	IcProgress,
	IcSelect,
	IcSkeleton,
	IcStat,
	IcStatusBadge,
	IcSwitch,
	pushToast,
} from "@/design/components";
import type { Tone } from "@/design/status";
import ErrorState from "@/features/system/ErrorState.vue";
import {
	fieldsFrom,
	initialValues,
	splitList,
	toParams,
	validate,
	type ParamValues,
} from "@/features/jobs/schemaForm";
import { relativeTime } from "@/lib/time";
import { useBulkStore, type BulkOperation, type PreflightTarget } from "@/stores/bulk";
import { useInventoryStore } from "@/stores/inventory";
import { usePlaybooksStore, type TargetDoctype } from "@/stores/playbooks";
import { useSessionStore } from "@/stores/session";

/**
 * Bulk rollouts (ADR 0009): pick an operation, tick targets from the inventory (no typing),
 * run the preflight, drop what fails, set canary and batches, start. The engine still backs up
 * every site first, proves the canary, then advances batch by batch; this screen never runs
 * anything itself.
 */
const bulk = useBulkStore();
const inventory = useInventoryStore();
const playbooks = usePlaybooksStore();
const session = useSessionStore();
const now = ref(Date.now());
let clock: ReturnType<typeof setInterval> | undefined;

// ---- wizard state --------------------------------------------------------------------------
const creating = ref(false);
const playbookKey = ref("");
const search = ref("");
const statusFilter = ref("");
const groupFilter = ref("");
const picked = ref<Set<string>>(new Set());
const preflight = ref<Record<string, PreflightTarget> | null>(null);
const preflightFor = ref("");
const ping = ref(false);
const canary = ref("");
const batchSize = ref("5");
const failurePolicy = ref<"halt" | "continue">("halt");
const confirm = ref("");
const values = ref<ParamValues>({});
const listText = ref<Record<string, string>>({});
const touched = ref(false);

const ROLLOUT_DOCTYPES: readonly TargetDoctype[] = ["Site", "Bench", "Server"];
const chosen = computed(() => playbooks.catalogue.find((p) => p.key === playbookKey.value));
const doctype = computed<TargetDoctype | null>(() => chosen.value?.target_doctype ?? null);
const playbookOptions = computed(() =>
	ROLLOUT_DOCTYPES.flatMap((dt) =>
		playbooks.catalogue
			.filter((p) => p.target_doctype === dt && !p.creates)
			.sort((a, b) => a.title.localeCompare(b.title))
			.map((p) => ({ value: p.key, label: `${dt} · ${p.title} · ${p.risk} risk` }))
	)
);

interface Candidate {
	name: string;
	label: string;
	sub: string;
	status: string;
	group: string;
}
const candidates = computed<Candidate[]>(() => {
	switch (doctype.value) {
		case "Site":
			return inventory.sites.map((s) => ({
				name: s.name,
				label: s.domain,
				sub: `${s.bench} · ${s.server ?? "Frappe Cloud"}`,
				status: s.status,
				group: s.server ?? "frappe_cloud",
			}));
		case "Bench":
			return inventory.benches.map((b) => ({
				name: b.name,
				label: b.title,
				sub: `${b.server ?? "Frappe Cloud"} · ${b.apps.length} apps · ${b.site_count} sites`,
				status: b.apps.some((a) => a.update_state === "update_available")
					? "Update available"
					: "Current",
				group: b.server ?? "frappe_cloud",
			}));
		case "Server":
			return inventory.servers.map((s) => ({
				name: s.name,
				label: s.hostname,
				sub: `${s.public_ip} · ${s.region} · ${s.size}`,
				status: s.status,
				group: s.provider_account,
			}));
		default:
			return [];
	}
});
const statusOptions = computed(() => [
	{ value: "", label: "Any status" },
	...[...new Set(candidates.value.map((c) => c.status))]
		.sort()
		.map((s) => ({ value: s, label: s })),
]);
const groupOptions = computed(() => [
	{ value: "", label: doctype.value === "Server" ? "Any account" : "Any server" },
	...[...new Set(candidates.value.map((c) => c.group))].sort().map((g) => ({
		value: g,
		label: inventory.servers.find((s) => s.name === g)?.hostname ?? g,
	})),
]);
const filtered = computed(() => {
	const text = search.value.trim().toLowerCase();
	return candidates.value.filter(
		(c) =>
			(!statusFilter.value || c.status === statusFilter.value) &&
			(!groupFilter.value || c.group === groupFilter.value) &&
			(!text ||
				c.label.toLowerCase().includes(text) ||
				c.name.toLowerCase().includes(text) ||
				c.sub.toLowerCase().includes(text))
	);
});
const pickedList = computed(() => candidates.value.filter((c) => picked.value.has(c.name)));
const allFilteredPicked = computed(
	() => filtered.value.length > 0 && filtered.value.every((c) => picked.value.has(c.name))
);

function toggle(name: string): void {
	const next = new Set(picked.value);
	if (next.has(name)) next.delete(name);
	else next.add(name);
	picked.value = next;
}
function pickFiltered(on: boolean): void {
	const next = new Set(picked.value);
	for (const c of filtered.value) {
		if (on) next.add(c.name);
		else next.delete(c.name);
	}
	picked.value = next;
}

function loadCandidates(): void {
	if (doctype.value === "Site") void inventory.fetchSites();
	else if (doctype.value === "Bench") void inventory.fetchBenches();
	else if (doctype.value === "Server") void inventory.fetchServers();
	if (!inventory.servers.length) void inventory.fetchServers();
}
watch(doctype, () => {
	picked.value = new Set();
	preflight.value = null;
	statusFilter.value = "";
	groupFilter.value = "";
	loadCandidates();
});

// ---- params form (plain fields only; pickers belong to single-target runs) --------------------
const fields = computed(() =>
	fieldsFrom(chosen.value?.params_schema ?? {}).filter((f) => !f.picker)
);
watch(chosen, () => {
	values.value = initialValues(fields.value);
	listText.value = {};
	touched.value = false;
	confirm.value = "";
});
const paramErrors = computed(() => validate(fields.value, values.value));
function stringValue(name: string): string {
	const v = values.value[name];
	return typeof v === "string" ? v : typeof v === "number" ? String(v) : "";
}

// ---- preflight ---------------------------------------------------------------------------------
const selectionKey = computed(
	() => `${playbookKey.value}|${ping.value}|${[...picked.value].sort().join(",")}`
);
const preflightFresh = computed(
	() => preflight.value !== null && preflightFor.value === selectionKey.value
);
const preflightRows = computed(() =>
	pickedList.value.map((c) => ({ ...c, result: preflight.value?.[c.name] ?? null }))
);
const failing = computed(() => preflightRows.value.filter((r) => r.result && !r.result.ok));
const summary = computed(() => {
	const rows = preflightRows.value.filter((r) => r.result);
	return {
		ok: rows.filter((r) => r.result?.ok).length,
		warn: rows.filter((r) => r.result?.ok && r.result.checks.some((c) => c.status === "warn"))
			.length,
		fail: rows.filter((r) => r.result && !r.result.ok).length,
	};
});
const checkTone: Record<string, Tone> = { pass: "healthy", warn: "degraded", fail: "down" };
function resultTone(r: PreflightTarget | null): Tone {
	if (!r) return "neutral";
	if (!r.ok) return "down";
	return r.checks.some((c) => c.status === "warn") ? "degraded" : "healthy";
}
function resultLabel(r: PreflightTarget | null): string {
	if (!r) return "not checked";
	if (!r.ok) return "blocked";
	return r.checks.some((c) => c.status === "warn") ? "ready, with warnings" : "ready";
}
function notable(r: PreflightTarget): string {
	return r.checks
		.filter((c) => c.status !== "pass")
		.map((c) => c.detail)
		.join(" · ");
}
async function runPreflight(): Promise<void> {
	if (!doctype.value || !picked.value.size) return;
	const dt = doctype.value;
	const res = await bulk.preflight({
		playbook: playbookKey.value,
		targets: [...picked.value].map((target_name) => ({ target_doctype: dt, target_name })),
		ping: ping.value,
	});
	if (!res) return;
	preflight.value = Object.fromEntries(res.items.map((i) => [i.target_name, i]));
	preflightFor.value = selectionKey.value;
	if (!picked.value.has(canary.value) || !preflight.value[canary.value]?.ok) {
		canary.value = res.items.find((i) => i.ok)?.target_name ?? "";
	}
}
function dropFailing(): void {
	const next = new Set(picked.value);
	for (const r of failing.value) next.delete(r.name);
	picked.value = next;
	preflightFor.value = selectionKey.value; // the remaining results are still valid
}
watch(picked, (set) => {
	if (!set.has(canary.value)) canary.value = [...set][0] ?? "";
});

// ---- submit -----------------------------------------------------------------------------------
const canaryOptions = computed(() =>
	pickedList.value.map((c) => ({ value: c.name, label: c.label }))
);
const expected = computed(() => `${playbookKey.value}:${picked.value.size}`);
const batches = computed(() =>
	Math.max(0, Math.ceil((picked.value.size - 1) / Math.max(1, Number(batchSize.value) || 1)))
);
const canSubmit = computed(
	() =>
		!!chosen.value &&
		picked.value.size > 0 &&
		picked.value.has(canary.value) &&
		preflightFresh.value &&
		summary.value.fail === 0 &&
		Object.keys(paramErrors.value).length === 0 &&
		(chosen.value.risk !== "high" || confirm.value === expected.value)
);
async function submit(): Promise<void> {
	touched.value = true;
	if (!canSubmit.value || !doctype.value) return;
	const dt = doctype.value;
	const name = await bulk.create({
		playbook: playbookKey.value,
		targets: [...picked.value].map((target_name) => ({ target_doctype: dt, target_name })),
		canary_target: { target_doctype: dt, target_name: canary.value },
		batch_size: Number(batchSize.value) || 5,
		failure_policy: failurePolicy.value,
		params: toParams(fields.value, values.value),
		...(confirm.value ? { confirm: confirm.value } : {}),
	});
	if (name) {
		pushToast({
			title: "Rollout started",
			description: `${name} · canary ${canary.value}`,
			tone: "running",
		});
		creating.value = false;
		picked.value = new Set();
		preflight.value = null;
		playbookKey.value = "";
	}
}

// ---- operations list and detail ------------------------------------------------------------
const detail = computed(() => (bulk.selected ? bulk.details[bulk.selected] : undefined));
const STATUSES = [
	"Running",
	"Queued",
	"Paused",
	"Halted",
	"Success",
	"Failed",
	"Cancelled",
] as const;
const statusTone: Record<string, Tone> = {
	Running: "running",
	Queued: "running",
	Paused: "degraded",
	Halted: "degraded",
	Success: "healthy",
	Failed: "down",
	Cancelled: "neutral",
};
const listFilter = ref("");
const counts = computed(() => {
	const c: Record<string, number> = {};
	for (const i of bulk.items) c[i.status] = (c[i.status] ?? 0) + 1;
	return c;
});
const operations = computed(() =>
	bulk.items.filter((i) => !listFilter.value || i.status === listFilter.value)
);
const progressOf = (i: BulkOperation): number => (i.total ? (i.done / i.total) * 100 : 0);
const batchesOf = computed(() => {
	if (!detail.value) return [];
	const by = new Map<number, typeof detail.value.targets>();
	for (const t of detail.value.targets) by.set(t.batch, [...(by.get(t.batch) ?? []), t]);
	return [...by.entries()].sort((a, b) => a[0] - b[0]);
});
const phaseLabel: Record<string, string> = {
	backup: "Backing up",
	canary: "Canary",
	batches: "Batches",
	done: "Done",
};

onMounted(() => {
	bulk.subscribe();
	void bulk.fetchList();
	void playbooks.fetchAll();
	clock = setInterval(() => (now.value = Date.now()), 30_000);
});
onBeforeUnmount(() => {
	clearInterval(clock);
});
watch(
	() => bulk.selected,
	(name) => {
		if (name && !bulk.details[name]) void bulk.fetchDetail(name);
	}
);
</script>

<template>
	<div class="flex flex-col gap-6">
		<IcPageHeader
			title="Bulk rollouts"
			subtitle="Pick the targets, check them, prove the canary, then advance in controlled batches."
		>
			<template #actions>
				<IcButton
					v-if="session.canOperate"
					variant="primary"
					data-testid="bulk-new"
					@click="creating = !creating"
					>{{ creating ? "Close" : "New rollout" }}</IcButton
				>
			</template>
		</IcPageHeader>

		<div class="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8" data-testid="bulk-tiles">
			<button type="button" class="text-start" @click="listFilter = ''">
				<IcStat label="All" :value="bulk.items.length" tone="neutral" :animate="false" />
			</button>
			<button
				v-for="s in STATUSES"
				:key="s"
				type="button"
				class="text-start"
				:aria-pressed="listFilter === s"
				:data-testid="`bulk-tile-${s}`"
				@click="listFilter = listFilter === s ? '' : s"
			>
				<IcStat
					:label="s"
					:value="counts[s] ?? 0"
					:tone="(counts[s] ?? 0) > 0 ? statusTone[s] : 'neutral'"
					:animate="false"
					:class="{ 'ring-1 ring-accent': listFilter === s }"
				/>
			</button>
		</div>

		<!-- ---------------- wizard ---------------- -->
		<IcCard
			v-if="creating"
			title="New rollout"
			subtitle="Four steps. Nothing runs until you press Start."
			data-testid="bulk-create"
		>
			<form class="flex flex-col gap-6" @submit.prevent="submit">
				<section class="grid gap-4 md:grid-cols-[14rem_1fr]">
					<h3 class="text-sm font-medium">
						<span class="eyebrow block">Step 1</span>Operation
					</h3>
					<IcField
						label="Playbook"
						for-id="bulk-playbook"
						required
						:hint="chosen?.description"
					>
						<IcSelect
							id="bulk-playbook"
							v-model="playbookKey"
							:options="playbookOptions"
							placeholder="Choose the operation"
						/>
					</IcField>
				</section>

				<section
					v-if="doctype"
					class="grid gap-4 md:grid-cols-[14rem_1fr]"
					data-testid="bulk-targets-step"
				>
					<h3 class="text-sm font-medium">
						<span class="eyebrow block">Step 2</span>Targets
						<span class="mt-1 block text-xs font-normal text-fg-subtle"
							>{{ picked.size }} of {{ candidates.length }}
							{{ doctype.toLowerCase() }}s selected</span
						>
					</h3>
					<div class="flex flex-col gap-3">
						<div class="flex flex-wrap items-end gap-3">
							<IcField label="Search" for-id="bulk-search" class="min-w-56 flex-1"
								><IcInput
									id="bulk-search"
									v-model="search"
									type="search"
									:placeholder="`Filter ${doctype.toLowerCase()}s`"
							/></IcField>
							<IcField label="Status" for-id="bulk-status" class="w-44"
								><IcSelect
									id="bulk-status"
									v-model="statusFilter"
									:options="statusOptions"
							/></IcField>
							<IcField
								:label="doctype === 'Server' ? 'Account' : 'Server'"
								for-id="bulk-group"
								class="w-48"
								><IcSelect
									id="bulk-group"
									v-model="groupFilter"
									:options="groupOptions"
							/></IcField>
							<div class="flex gap-2 pb-0.5">
								<IcButton
									size="sm"
									:disabled="!filtered.length"
									data-testid="bulk-pick-all"
									@click="pickFiltered(!allFilteredPicked)"
									>{{
										allFilteredPicked
											? "Clear shown"
											: `Select shown (${filtered.length})`
									}}</IcButton
								>
								<IcButton
									size="sm"
									variant="ghost"
									:disabled="!picked.size"
									@click="picked = new Set()"
									>Clear all</IcButton
								>
							</div>
						</div>
						<IcSkeleton v-if="inventory.loading && !candidates.length" :lines="4" />
						<div
							v-else
							class="max-h-80 overflow-auto rounded border border-line bg-surface-1"
						>
							<table
								class="w-full border-collapse text-sm"
								data-testid="bulk-candidates"
							>
								<tbody>
									<tr
										v-for="c in filtered"
										:key="c.name"
										class="border-b border-line last:border-0 hover:bg-surface-2"
										:class="{ 'bg-surface-2': picked.has(c.name) }"
									>
										<td class="w-8 px-3 py-2">
											<input
												:id="`pick-${c.name}`"
												type="checkbox"
												class="size-4 accent-accent"
												:checked="picked.has(c.name)"
												:aria-label="`Select ${c.label}`"
												data-testid="bulk-candidate"
												@change="toggle(c.name)"
											/>
										</td>
										<td class="px-2 py-2">
											<label
												:for="`pick-${c.name}`"
												class="cursor-pointer font-mono text-xs"
												>{{ c.label }}</label
											><span class="block text-2xs text-fg-subtle">{{
												c.sub
											}}</span>
										</td>
										<td class="px-3 py-2 text-end">
											<IcBadge
												:tone="
													c.status === 'Active' || c.status === 'Current'
														? 'healthy'
														: c.status === 'Update available'
															? 'degraded'
															: 'neutral'
												"
												dot
												>{{ c.status }}</IcBadge
											>
										</td>
									</tr>
									<tr v-if="!filtered.length">
										<td
											colspan="3"
											class="px-4 py-6 text-center text-xs text-fg-subtle"
										>
											Nothing matches.
										</td>
									</tr>
								</tbody>
							</table>
						</div>
					</div>
				</section>

				<section
					v-if="doctype && picked.size"
					class="grid gap-4 md:grid-cols-[14rem_1fr]"
					data-testid="bulk-preflight-step"
				>
					<h3 class="text-sm font-medium">
						<span class="eyebrow block">Step 3</span>Checks
						<span class="mt-1 block text-xs font-normal text-fg-subtle"
							>Exists, capability, status, lock, backup age{{
								doctype !== "Bench" ? ", optional ping" : ""
							}}.</span
						>
					</h3>
					<div class="flex flex-col gap-3">
						<div class="flex flex-wrap items-center gap-3">
							<IcButton
								variant="primary"
								:loading="bulk.loading"
								data-testid="bulk-run-checks"
								@click="runPreflight"
								>{{ preflightFresh ? "Re-run checks" : "Run checks" }}</IcButton
							>
							<IcSwitch
								v-if="doctype !== 'Bench'"
								v-model="ping"
								label="Ping each target"
							/>
							<template v-if="preflightFresh">
								<IcBadge tone="healthy" dot>{{ summary.ok }} ready</IcBadge>
								<IcBadge v-if="summary.warn" tone="degraded" dot
									>{{ summary.warn }} with warnings</IcBadge
								>
								<IcBadge v-if="summary.fail" tone="down" dot
									>{{ summary.fail }} blocked</IcBadge
								>
								<IcButton
									v-if="failing.length"
									size="sm"
									variant="danger"
									data-testid="bulk-drop-failing"
									@click="dropFailing"
									>Drop {{ failing.length }} blocked</IcButton
								>
							</template>
							<span v-else-if="preflight" class="text-xs text-degraded"
								>Selection changed: run the checks again.</span
							>
						</div>
						<div
							v-if="preflight"
							class="max-h-72 overflow-auto rounded border border-line bg-surface-1"
						>
							<table
								class="w-full border-collapse text-sm"
								data-testid="bulk-preflight"
							>
								<tbody>
									<tr
										v-for="r in preflightRows"
										:key="r.name"
										class="border-b border-line last:border-0"
										:data-testid="`preflight-${r.name}`"
									>
										<td class="px-3 py-2 font-mono text-xs">{{ r.label }}</td>
										<td class="px-3 py-2">
											<IcBadge :tone="resultTone(r.result)" dot>{{
												resultLabel(r.result)
											}}</IcBadge>
										</td>
										<td class="px-3 py-2 text-xs text-fg-subtle">
											<span v-if="r.result">{{
												notable(r.result) || "all checks pass"
											}}</span>
											<span v-if="r.result" class="mt-1 flex flex-wrap gap-1"
												><IcBadge
													v-for="c in r.result.checks"
													:key="c.id"
													:tone="checkTone[c.status] ?? 'neutral'"
													:title="c.detail"
													>{{ c.id }}</IcBadge
												></span
											>
										</td>
									</tr>
								</tbody>
							</table>
						</div>
					</div>
				</section>

				<section
					v-if="doctype && picked.size"
					class="grid gap-4 md:grid-cols-[14rem_1fr]"
					data-testid="bulk-plan-step"
				>
					<h3 class="text-sm font-medium">
						<span class="eyebrow block">Step 4</span>Plan
						<span class="mt-1 block text-xs font-normal text-fg-subtle"
							>Canary first, then {{ batches }} batch{{
								batches === 1 ? "" : "es"
							}}
							of {{ batchSize || 5 }}.</span
						>
					</h3>
					<div class="grid gap-4 md:grid-cols-3">
						<IcField
							label="Canary"
							for-id="bulk-canary"
							required
							hint="Proven alone before any batch runs."
							><IcSelect
								id="bulk-canary"
								v-model="canary"
								:options="canaryOptions"
								placeholder="Pick targets first"
						/></IcField>
						<IcField label="Batch size" for-id="bulk-batch" required
							><IcInput id="bulk-batch" v-model="batchSize" type="number"
						/></IcField>
						<IcField label="On failure" for-id="bulk-policy" required
							><IcSelect
								id="bulk-policy"
								v-model="failurePolicy"
								:options="[
									{ value: 'halt', label: 'Halt the rollout' },
									{ value: 'continue', label: 'Continue with the next target' },
								]"
						/></IcField>
						<IcField
							v-for="f in fields"
							:key="f.name"
							:label="f.label"
							:for-id="`bulk-param-${f.name}`"
							:required="f.required"
							:hint="f.description"
							:error="touched ? paramErrors[f.name] : undefined"
						>
							<IcSwitch
								v-if="f.kind === 'boolean'"
								:model-value="values[f.name] === true"
								:label="f.label"
								@update:model-value="(v: boolean) => (values[f.name] = v)"
							/>
							<IcSelect
								v-else-if="f.kind === 'enum'"
								:id="`bulk-param-${f.name}`"
								:model-value="stringValue(f.name)"
								:options="(f.options ?? []).map((o) => ({ value: o, label: o }))"
								placeholder="Choose…"
								@update:model-value="(v: string) => (values[f.name] = v)"
							/>
							<IcInput
								v-else-if="f.kind === 'strings'"
								:id="`bulk-param-${f.name}`"
								:model-value="listText[f.name] ?? ''"
								mono
								placeholder="comma separated"
								@update:model-value="
									(v: string) => {
										listText[f.name] = v;
										values[f.name] = splitList(v);
									}
								"
							/>
							<IcInput
								v-else
								:id="`bulk-param-${f.name}`"
								:model-value="stringValue(f.name)"
								:type="
									f.kind === 'number' || f.kind === 'integer' ? 'number' : 'text'
								"
								mono
								@update:model-value="
									(v: string) =>
										(values[f.name] =
											f.kind === 'number' || f.kind === 'integer'
												? v === ''
													? null
													: Number(v)
												: v)
								"
							/>
						</IcField>
						<IcField
							v-if="chosen?.risk === 'high'"
							class="md:col-span-3"
							label="Typed confirmation"
							:hint="`High risk: type ${expected}`"
							required
							><IcInput
								id="bulk-confirm"
								v-model="confirm"
								mono
								data-testid="bulk-confirm"
						/></IcField>
					</div>
				</section>

				<div class="flex flex-wrap items-center gap-3 border-t border-line pt-4">
					<IcButton
						type="submit"
						variant="primary"
						:disabled="!canSubmit"
						:loading="bulk.loading"
						data-testid="bulk-start"
						>Start rollout</IcButton
					>
					<span class="text-xs text-fg-subtle">
						<template v-if="!playbookKey">Choose an operation.</template>
						<template v-else-if="!picked.size">Select at least one target.</template>
						<template v-else-if="!preflightFresh"
							>Run the checks on the current selection.</template
						>
						<template v-else-if="summary.fail"
							>{{ summary.fail }} target(s) are blocked: drop them or fix them
							first.</template
						>
						<template v-else-if="chosen?.risk === 'high' && confirm !== expected"
							>Type the confirmation to start.</template
						>
						<template v-else
							>{{ picked.size }} target(s): backup, canary {{ canary }}, then
							{{ batches }} batch{{ batches === 1 ? "" : "es" }}.</template
						>
					</span>
				</div>
			</form>
		</IcCard>

		<!-- ---------------- operations ---------------- -->
		<IcCard v-if="bulk.error && !bulk.items.length" :padded="false"
			><ErrorState :error="bulk.error" @retry="bulk.fetchList()"
		/></IcCard>
		<div v-else-if="bulk.loading && !bulk.items.length" class="grid gap-4 lg:grid-cols-3">
			<IcSkeleton v-for="i in 3" :key="i" variant="block" />
		</div>
		<IcEmptyState
			v-else-if="!bulk.items.length"
			title="No rollouts yet"
			description="Create a rollout to run one playbook safely across many targets."
		/>
		<div v-else class="grid gap-5 xl:grid-cols-[24rem_1fr]">
			<IcCard
				title="Operations"
				:subtitle="
					listFilter
						? `${operations.length} ${listFilter.toLowerCase()}`
						: `${bulk.items.length} total`
				"
				:padded="false"
			>
				<button
					v-for="item in operations"
					:key="item.name"
					type="button"
					class="flex w-full flex-col gap-2 border-b border-line p-4 text-start last:border-0 hover:bg-surface-2"
					:class="{ 'bg-surface-2': bulk.selected === item.name }"
					data-testid="bulk-row"
					@click="bulk.fetchDetail(item.name)"
				>
					<span class="flex items-center justify-between gap-2"
						><span class="font-mono text-xs">{{ item.name }}</span
						><IcStatusBadge entity="bulk" :status="item.status"
					/></span>
					<span class="text-sm font-medium">{{ item.playbook_title }}</span>
					<IcProgress :value="progressOf(item)" :label="item.name + ' progress'" />
					<span class="text-2xs text-fg-subtle"
						>{{ item.done }}/{{ item.total }} done<span v-if="item.failed">
							· {{ item.failed }} failed</span
						>
						· {{ phaseLabel[item.phase] ?? item.phase }} ·
						{{ relativeTime(item.created_at, now) }}</span
					>
				</button>
				<p v-if="!operations.length" class="px-4 py-6 text-center text-xs text-fg-subtle">
					No {{ listFilter.toLowerCase() }} rollouts.
				</p>
				<div v-if="bulk.nextCursor" class="p-3">
					<IcButton size="sm" @click="bulk.fetchList(bulk.nextCursor ?? undefined)"
						>Load more</IcButton
					>
				</div>
			</IcCard>
			<IcCard
				v-if="detail"
				:title="detail.playbook_title"
				:subtitle="`${detail.name} · by ${detail.triggered_by} · ${relativeTime(detail.created_at, now)}`"
				data-testid="bulk-detail"
			>
				<div class="mb-5 flex flex-wrap items-center gap-2">
					<IcStatusBadge entity="bulk" :status="detail.status" />
					<IcBadge>{{ phaseLabel[detail.phase] ?? detail.phase }}</IcBadge>
					<IcBadge mono
						>batch {{ detail.current_batch }}/{{ detail.batches_total }}</IcBadge
					>
					<IcBadge mono>canary {{ detail.canary_target.target_name }}</IcBadge>
					<IcBadge>{{
						detail.failure_policy === "halt"
							? "halt on failure"
							: "continue on failure"
					}}</IcBadge>
					<div v-if="session.canOperate" class="ms-auto flex gap-2">
						<IcButton
							v-if="['Queued', 'Running'].includes(detail.status)"
							size="sm"
							@click="bulk.action('pause', detail.name)"
							>Pause</IcButton
						>
						<IcButton
							v-if="['Paused', 'Halted'].includes(detail.status)"
							size="sm"
							variant="primary"
							@click="bulk.action('resume', detail.name)"
							>Resume</IcButton
						>
						<IcButton
							v-if="
								['Queued', 'Running', 'Paused', 'Halted'].includes(detail.status)
							"
							size="sm"
							variant="danger"
							@click="bulk.action('cancel', detail.name)"
							>Cancel</IcButton
						>
					</div>
				</div>
				<IcProgress
					:value="progressOf(detail)"
					:label="detail.name + ' progress'"
					class="mb-5"
				/>
				<div class="flex flex-col gap-4" data-testid="bulk-targets">
					<div v-for="[batch, targets] in batchesOf" :key="batch">
						<p class="eyebrow mb-2">
							{{ batch === 0 ? "Canary" : `Batch ${batch}` }} · {{ targets.length }}
						</p>
						<div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
							<div
								v-for="target in targets"
								:key="target.target_name"
								class="rounded border border-line bg-surface-2 p-3"
							>
								<span class="flex items-center justify-between gap-2"
									><span class="truncate font-mono text-xs">{{
										target.target_name
									}}</span
									><IcStatusBadge entity="bulkTarget" :status="target.status"
								/></span>
								<RouterLink
									v-if="target.job"
									:to="`/jobs/${encodeURIComponent(target.job)}`"
									class="mt-2 block font-mono text-2xs text-fg-subtle hover:text-fg"
									>{{ target.job }}</RouterLink
								>
							</div>
						</div>
					</div>
				</div>
			</IcCard>
		</div>
	</div>
</template>
