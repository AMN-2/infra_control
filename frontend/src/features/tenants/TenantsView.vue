<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
	IcBadge,
	IcButton,
	IcCard,
	IcDialog,
	IcEmptyState,
	IcField,
	IcInput,
	IcPageHeader,
	IcSelect,
	IcSkeleton,
	IcTable,
	pushToast,
	type Column,
} from "@/design/components";
import ErrorState from "@/features/system/ErrorState.vue";
import { relativeTime } from "@/lib/time";
import { useSessionStore } from "@/stores/session";
import { useTenantsStore, type Tenant } from "@/stores/tenants";

/** Tenants list: the clients behind the sites, with search, status filter and creation. */
const tenants = useTenantsStore();
const session = useSessionStore();
const router = useRouter();
const status = ref("");
const query = ref("");
const creating = ref(false);
const form = ref({ label: "", title: "", plan: "", contact_email: "", contact_phone: "" });
const touched = ref(false);

type Row = Tenant & { when: string };
const columns: Column<Row>[] = [
	{ key: "label", label: "Id", mono: true },
	{ key: "title", label: "Name" },
	{ key: "status", label: "Status" },
	{ key: "plan", label: "Plan" },
	{ key: "site_count", label: "Sites", align: "end" },
	{ key: "contact_email", label: "Contact" },
	{ key: "when", label: "Updated" },
];
function rows(): Row[] {
	return tenants.items.map((t) => ({
		...t,
		when: t.modified_at ? relativeTime(t.modified_at) : "",
	}));
}
function load(): void {
	void tenants.fetchList({
		...(status.value ? { status: status.value as Tenant["status"] } : {}),
		...(query.value.trim() ? { query: query.value.trim() } : {}),
	});
}
let timer: ReturnType<typeof setTimeout> | undefined;
watch(query, () => {
	if (timer !== undefined) clearTimeout(timer);
	timer = setTimeout(load, 250);
});
watch(status, load);
onMounted(load);

async function submit(): Promise<void> {
	touched.value = true;
	if (!form.value.label.trim()) return;
	const t = await tenants.create({
		label: form.value.label.trim().toUpperCase(),
		title: form.value.title.trim() || undefined,
		plan: form.value.plan.trim() || undefined,
		contact_email: form.value.contact_email.trim() || undefined,
		contact_phone: form.value.contact_phone.trim() || undefined,
	});
	if (t) {
		pushToast({ title: "Tenant created", description: t.title, tone: "healthy" });
		creating.value = false;
		form.value = { label: "", title: "", plan: "", contact_email: "", contact_phone: "" };
		touched.value = false;
		void router.push(`/tenants/${encodeURIComponent(t.name)}`);
	}
}
</script>

<template>
	<div class="flex flex-col gap-4">
		<IcPageHeader
			title="Tenants"
			subtitle="The clients behind the sites: plan, contact, and one place to suspend or activate everything they run."
		>
			<template #actions>
				<IcButton
					v-if="session.canOperate"
					variant="primary"
					data-testid="tenant-new"
					@click="creating = true"
					>New tenant</IcButton
				>
			</template>
		</IcPageHeader>
		<div class="flex flex-wrap items-end gap-3">
			<IcField for-id="tenants-query" label="Search"
				><IcInput
					id="tenants-query"
					v-model="query"
					type="search"
					placeholder="Name…"
					data-testid="tenants-query"
			/></IcField>
			<IcField for-id="tenants-status" label="Status">
				<IcSelect
					id="tenants-status"
					v-model="status"
					:options="[
						{ value: '', label: 'All' },
						{ value: 'active', label: 'Active' },
						{ value: 'suspended', label: 'Suspended' },
					]"
				/>
			</IcField>
		</div>
		<IcCard v-if="tenants.error && !tenants.items.length" :padded="false"
			><ErrorState :error="tenants.error" @retry="load"
		/></IcCard>
		<div v-else-if="tenants.loading && !tenants.items.length">
			<IcSkeleton variant="block" />
		</div>
		<IcEmptyState
			v-else-if="!tenants.items.length"
			title="No tenants yet"
			description="Create one and attach its sites."
		/>
		<IcCard v-else :padded="false">
			<IcTable
				:columns="columns"
				:rows="rows()"
				row-key="name"
				clickable
				data-testid="tenants-table"
				@row-click="(t: Row) => router.push(`/tenants/${encodeURIComponent(t.name)}`)"
			>
				<template #cell-status="{ row }">
					<IcBadge
						:tone="row.status === 'active' ? 'healthy' : 'neutral'"
						dot
						uppercase
						>{{ row.status }}</IcBadge
					>
				</template>
			</IcTable>
			<div v-if="tenants.nextCursor" class="p-3">
				<IcButton size="sm" @click="tenants.fetchList({}, tenants.nextCursor ?? undefined)"
					>Load more</IcButton
				>
			</div>
		</IcCard>

		<IcDialog
			v-model="creating"
			title="New tenant"
			description="A stable id and the client's details. Sites are attached from the tenant's page."
			size="md"
		>
			<form
				class="grid gap-4 sm:grid-cols-2"
				data-testid="tenant-create"
				@submit.prevent="submit"
			>
				<IcField
					for-id="tenant-label"
					label="Id"
					required
					hint="e.g. CLIENT-D; upper-cased"
					:error="touched && !form.label.trim() ? 'Required' : undefined"
				>
					<IcInput
						id="tenant-label"
						v-model="form.label"
						mono
						data-testid="tenant-label"
					/>
				</IcField>
				<IcField for-id="tenant-title" label="Name"
					><IcInput id="tenant-title" v-model="form.title" data-testid="tenant-title"
				/></IcField>
				<IcField for-id="tenant-plan" label="Plan"
					><IcInput id="tenant-plan" v-model="form.plan" placeholder="Business"
				/></IcField>
				<IcField for-id="tenant-email" label="Contact email"
					><IcInput id="tenant-email" v-model="form.contact_email" type="email"
				/></IcField>
				<IcField for-id="tenant-phone" label="Contact phone"
					><IcInput id="tenant-phone" v-model="form.contact_phone" mono
				/></IcField>
				<p v-if="tenants.saveError" class="text-xs text-down sm:col-span-2" role="alert">
					{{ tenants.saveError }}
				</p>
			</form>
			<template #footer="{ close }">
				<IcButton variant="ghost" @click="close">Cancel</IcButton>
				<IcButton
					variant="primary"
					:loading="tenants.saving"
					data-testid="tenant-submit"
					@click="submit"
					>Create</IcButton
				>
			</template>
		</IcDialog>
	</div>
</template>
