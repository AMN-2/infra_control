<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
	IcBadge,
	IcBreadcrumbs,
	IcButton,
	IcCard,
	IcConfirmDialog,
	IcField,
	IcInput,
	IcPageHeader,
	IcSelect,
	IcSkeleton,
	IcStatusBadge,
	IcTable,
	pushToast,
	type Column,
} from "@/design/components";
import ErrorState from "@/features/system/ErrorState.vue";
import { useInventoryStore } from "@/stores/inventory";
import { useSessionStore } from "@/stores/session";
import { useTenantsStore, type TenantDetail } from "@/stores/tenants";

/** One tenant: editable facts, its sites (attach/detach), suspend or activate them all. */
const route = useRoute();
const router = useRouter();
const tenants = useTenantsStore();
const inventory = useInventoryStore();
const session = useSessionStore();
const name = computed(() => String(route.params.name ?? ""));
const tenant = computed(() => tenants.details[name.value]);
const form = ref({ title: "", plan: "", contact_email: "", contact_phone: "", notes: "" });
const dirty = ref(false);
const siteToAttach = ref("");
const confirming = ref<"suspend" | "activate" | null>(null);

type SiteRow = TenantDetail["sites"][number] & { actions: null };
const siteColumns: Column<SiteRow>[] = [
	{ key: "domain", label: "Site", mono: true },
	{ key: "status", label: "Status" },
	{ key: "server", label: "Server", mono: true },
	{ key: "bench", label: "Bench", mono: true },
	{ key: "actions", label: "", align: "end" },
];
const siteRows = computed<SiteRow[]>(() =>
	(tenant.value?.sites ?? []).map((s) => ({ ...s, actions: null }))
);
const attachOptions = computed(() => {
	const mine = new Set((tenant.value?.sites ?? []).map((s) => s.name));
	return inventory.sites
		.filter((s) => !mine.has(s.name) && s.status !== "Archived")
		.map((s) => ({ value: s.name, label: s.domain }));
});

function load(): void {
	void tenants.fetchDetail(name.value);
	if (!inventory.sites.length) void inventory.fetchSites();
}
watch(
	tenant,
	(t) => {
		if (!t) return;
		form.value = {
			title: t.title,
			plan: t.plan ?? "",
			contact_email: t.contact_email ?? "",
			contact_phone: t.contact_phone ?? "",
			notes: t.notes ?? "",
		};
		dirty.value = false;
	},
	{ immediate: true }
);
watch(form, () => (dirty.value = true), { deep: true });
watch(name, load);
onMounted(load);

async function save(): Promise<void> {
	const t = await tenants.update({ tenant: name.value, ...form.value });
	if (t) {
		dirty.value = false;
		pushToast({ title: "Tenant saved", description: t.title, tone: "healthy" });
	} else
		pushToast({ title: "Could not save", description: tenants.saveError ?? "", tone: "down" });
}
async function attach(): Promise<void> {
	if (!siteToAttach.value) return;
	const t = await tenants.assign(name.value, siteToAttach.value);
	if (t) siteToAttach.value = "";
	else
		pushToast({
			title: "Could not attach site",
			description: tenants.saveError ?? "",
			tone: "down",
		});
}
async function detach(site: string): Promise<void> {
	const t = await tenants.assign(name.value, site, true);
	if (!t)
		pushToast({
			title: "Could not detach site",
			description: tenants.saveError ?? "",
			tone: "down",
		});
}
async function confirmSuspend(): Promise<void> {
	const suspended = confirming.value === "suspend";
	const result = await tenants.suspend(name.value, suspended);
	confirming.value = null;
	if (!result) {
		pushToast({
			title: "Could not queue the jobs",
			description: tenants.saveError ?? "",
			tone: "down",
		});
		return;
	}
	pushToast({
		title: suspended ? "Suspending sites" : "Activating sites",
		description: `${result.jobs.length} job(s) queued${result.errors.length ? `, ${result.errors.length} site(s) skipped` : ""}`,
		tone: result.errors.length ? "degraded" : "running",
	});
	if (result.jobs[0]) void router.push(`/jobs/${encodeURIComponent(result.jobs[0])}`);
}
</script>

<template>
	<div class="flex flex-col gap-4">
		<IcBreadcrumbs
			:items="[{ label: 'Tenants', to: '/tenants' }, { label: tenant?.title ?? name }]"
		/>
		<IcCard v-if="tenants.error && !tenant" :padded="false"
			><ErrorState :error="tenants.error" @retry="load"
		/></IcCard>
		<IcSkeleton v-else-if="!tenant" variant="block" />
		<template v-else>
			<IcPageHeader :title="tenant.title" :subtitle="tenant.label">
				<template #actions>
					<div class="flex items-center gap-2" data-testid="tenant-badges">
						<IcBadge
							:tone="tenant.status === 'active' ? 'healthy' : 'neutral'"
							dot
							uppercase
							>{{ tenant.status }}</IcBadge
						>
						<IcBadge v-if="tenant.plan" mono>{{ tenant.plan }}</IcBadge>
						<template v-if="session.canOperate && tenant.sites.length">
							<IcButton
								v-if="tenant.status === 'active'"
								variant="danger"
								size="sm"
								data-testid="tenant-suspend"
								@click="confirming = 'suspend'"
								>Suspend all sites</IcButton
							>
							<IcButton
								v-else
								variant="primary"
								size="sm"
								data-testid="tenant-activate"
								@click="confirming = 'activate'"
								>Activate all sites</IcButton
							>
						</template>
					</div>
				</template>
			</IcPageHeader>

			<div class="grid gap-5 lg:grid-cols-[22rem_1fr]">
				<IcCard title="Client">
					<form
						class="flex flex-col gap-3"
						data-testid="tenant-form"
						@submit.prevent="save"
					>
						<IcField for-id="t-title" label="Name" required
							><IcInput
								id="t-title"
								v-model="form.title"
								:disabled="!session.canOperate"
								data-testid="tenant-form-title"
						/></IcField>
						<IcField for-id="t-plan" label="Plan"
							><IcInput
								id="t-plan"
								v-model="form.plan"
								:disabled="!session.canOperate"
						/></IcField>
						<IcField for-id="t-email" label="Contact email"
							><IcInput
								id="t-email"
								v-model="form.contact_email"
								type="email"
								:disabled="!session.canOperate"
						/></IcField>
						<IcField for-id="t-phone" label="Contact phone"
							><IcInput
								id="t-phone"
								v-model="form.contact_phone"
								mono
								:disabled="!session.canOperate"
						/></IcField>
						<IcField for-id="t-notes" label="Notes">
							<textarea
								id="t-notes"
								v-model="form.notes"
								class="min-h-20 w-full rounded border border-line-strong bg-surface-2 p-2.5 text-sm text-fg"
								:disabled="!session.canOperate"
							/>
						</IcField>
						<div class="flex items-center gap-3">
							<IcButton
								v-if="session.canOperate"
								type="submit"
								variant="primary"
								:disabled="!dirty"
								:loading="tenants.saving"
								data-testid="tenant-save"
								>Save</IcButton
							>
							<span
								v-if="tenants.saveError"
								class="text-xs text-down"
								role="alert"
								>{{ tenants.saveError }}</span
							>
						</div>
					</form>
				</IcCard>

				<IcCard
					title="Sites"
					:subtitle="`${tenant.site_count} site(s); each site belongs to one tenant`"
					:padded="false"
				>
					<div
						v-if="session.canOperate"
						class="flex items-end gap-2 border-b border-line p-4"
					>
						<IcField class="flex-1" for-id="t-attach" label="Attach a site">
							<IcSelect
								id="t-attach"
								v-model="siteToAttach"
								:options="attachOptions"
								placeholder="Choose a site without a tenant"
								data-testid="tenant-attach"
							/>
						</IcField>
						<IcButton
							:disabled="!siteToAttach"
							:loading="tenants.saving"
							data-testid="tenant-attach-submit"
							@click="attach"
							>Attach</IcButton
						>
					</div>
					<IcTable
						:columns="siteColumns"
						:rows="siteRows"
						row-key="name"
						clickable
						empty-title="No sites yet"
						empty-description="Attach the client's sites above."
						data-testid="tenant-sites"
						@row-click="
							(s: SiteRow) => router.push(`/sites/${encodeURIComponent(s.name)}`)
						"
					>
						<template #cell-status="{ row }"
							><IcStatusBadge entity="site" :status="row.status"
						/></template>
						<template #cell-actions="{ row }">
							<div @click.stop>
								<IcButton
									v-if="session.canOperate"
									size="sm"
									variant="ghost"
									:data-testid="`tenant-detach-${row.name}`"
									@click="detach(row.name)"
									>Detach</IcButton
								>
							</div>
						</template>
					</IcTable>
				</IcCard>
			</div>

			<IcConfirmDialog
				:model-value="confirming !== null"
				:title="confirming === 'suspend' ? 'Suspend every site' : 'Activate every site'"
				:description="`One site.suspend job per site (${tenant.site_count}). Sites locked by a running job are skipped and listed.`"
				:expected="tenant.label"
				:confirm-label="confirming === 'suspend' ? 'Suspend' : 'Activate'"
				:busy="tenants.saving"
				@update:model-value="
					(v) => {
						if (!v) confirming = null;
					}
				"
				@confirm="confirmSuspend"
			/>
		</template>
	</div>
</template>
