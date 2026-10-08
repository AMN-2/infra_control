<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
	IcBadge,
	IcButton,
	IcDialog,
	IcField,
	IcInput,
	IcSelect,
	IcSkeleton,
	pushToast,
} from "@/design/components";
import ErrorState from "@/features/system/ErrorState.vue";
import { useJobsStore } from "@/stores/jobs";
import { useProvidersStore, type ProvisionSize } from "@/stores/providers";

/**
 * New server (ADR 0006): account → region → plan (live catalogue with specs and price) →
 * hostname, role, tags → `jobs.run server.provision`. The operator is taken to the job.
 */
const open = defineModel<boolean>({ default: false });
const providers = useProvidersStore();
const jobs = useJobsStore();
const router = useRouter();

const account = ref("");
const region = ref("");
const size = ref("");
const family = ref<ProvisionSize["family"]>("basic");
const hostname = ref("");
const role = ref("all");
const tagsText = ref("");
const touched = ref(false);
const busy = ref(false);
const submitError = ref<string | null>(null);

const accountOptions = computed(() =>
	providers.accounts
		.filter((a) => a.enabled && a.provider === "digitalocean")
		.map((a) => ({ value: a.name, label: `${a.label}${a.is_staging ? " · staging" : ""}` }))
);
const catalogue = computed(() =>
	account.value ? providers.catalogues[account.value] : undefined
);
const regionOptions = computed(() =>
	(catalogue.value?.regions ?? []).map((r) => ({
		value: r.slug,
		label: `${r.name} (${r.slug})`,
	}))
);
const FAMILIES: readonly ProvisionSize["family"][] = [
	"basic",
	"general",
	"cpu",
	"memory",
	"storage",
	"other",
];
const families = computed(() => {
	const seen = new Set((catalogue.value?.sizes ?? []).map((s) => s.family));
	return FAMILIES.filter((f) => seen.has(f));
});
const regionSizes = computed(() => {
	const r = catalogue.value?.regions.find((x) => x.slug === region.value);
	return new Set(r?.sizes ?? []);
});
const plans = computed<ProvisionSize[]>(() =>
	(catalogue.value?.sizes ?? []).filter(
		(s) =>
			s.family === family.value && (!regionSizes.value.size || regionSizes.value.has(s.slug))
	)
);
const HOSTNAME = /^[a-z0-9.-]{3,63}$/;
const errors = computed(() => {
	const e: Record<string, string> = {};
	if (!account.value) e.account = "Choose an account";
	if (!region.value) e.region = "Choose a region";
	if (!size.value) e.size = "Choose a plan";
	else if (regionSizes.value.size && !regionSizes.value.has(size.value))
		e.size = "This plan is not offered in the chosen region";
	if (!HOSTNAME.test(hostname.value))
		e.hostname = "3–63 lowercase letters, digits, dots or dashes";
	return e;
});
/** The button stays enabled so a click surfaces the validation messages (errors gate submit()). */
const valid = computed(() => Object.keys(errors.value).length === 0);
const canSubmit = computed(() => !busy.value && (!touched.value || valid.value));
const chosen = computed(() => catalogue.value?.sizes.find((s) => s.slug === size.value));

function gb(mb: number): string {
	return mb >= 1024 ? `${Math.round(mb / 1024)} GB` : `${mb} MB`;
}
function money(v: number): string {
	return `$${v.toFixed(v >= 10 ? 0 : 2)}`;
}

watch(open, (v) => {
	if (!v) return;
	touched.value = false;
	submitError.value = null;
	if (!providers.loaded) void providers.fetchAccounts();
});
watch(
	() => [providers.loaded, account.value],
	async () => {
		if (!account.value && accountOptions.value[0])
			account.value = accountOptions.value[0].value;
		if (!account.value) return;
		const cat = await providers.fetchCatalogue(account.value);
		if (!cat) return;
		if (!region.value) region.value = cat.defaults.region;
		if (!size.value) size.value = cat.defaults.size;
		const def = cat.sizes.find((s) => s.slug === size.value);
		if (def) family.value = def.family;
	},
	{ immediate: true }
);

async function submit(): Promise<void> {
	touched.value = true;
	if (!valid.value || busy.value) return;
	busy.value = true;
	submitError.value = null;
	const tags = tagsText.value
		.split(/[,\s]+/)
		.map((t) => t.trim())
		.filter(Boolean);
	const job = await jobs.runPlaybook({
		playbook: "server.provision",
		target_doctype: "Provider Account",
		target_name: account.value,
		params: {
			hostname: hostname.value,
			region: region.value,
			size: size.value,
			role: role.value,
			tags,
		},
	});
	busy.value = false;
	if (!job) {
		const e = jobs.error;
		submitError.value = e ? `${e.message} (${e.code})` : "The job could not be created.";
		return;
	}
	pushToast({
		title: "Provisioning started",
		description: `${job.name} · ${hostname.value}`,
		tone: "running",
	});
	open.value = false;
	void router.push(`/jobs/${encodeURIComponent(job.name)}`);
}
</script>

<template>
	<IcDialog
		v-model="open"
		title="New server"
		description="Create a droplet from a plan, then cloud-init and the base, mariadb, redis, nginx and bench roles."
		size="lg"
	>
		<form class="flex flex-col gap-5" data-testid="provision-dialog" @submit.prevent="submit">
			<div class="grid gap-4 sm:grid-cols-2">
				<IcField
					for-id="prov-account"
					label="Provider account"
					required
					:error="touched ? errors.account : undefined"
				>
					<IcSelect
						id="prov-account"
						v-model="account"
						:options="accountOptions"
						placeholder="Choose account"
						data-testid="prov-account"
					/>
				</IcField>
				<IcField
					for-id="prov-region"
					label="Region"
					required
					:error="touched ? errors.region : undefined"
				>
					<IcSelect
						id="prov-region"
						v-model="region"
						:options="regionOptions"
						placeholder="Choose region"
						data-testid="prov-region"
					/>
				</IcField>
			</div>

			<ErrorState
				v-if="providers.error && !catalogue"
				:error="providers.error"
				title="Could not load the catalogue"
				@retry="account && providers.fetchCatalogue(account)"
			/>
			<IcSkeleton v-else-if="!catalogue" variant="block" />
			<div v-else class="flex flex-col gap-3">
				<div class="flex flex-wrap items-center gap-2">
					<span class="eyebrow">Plan</span>
					<div class="ms-auto flex gap-1" role="tablist" aria-label="Plan family">
						<IcButton
							v-for="f in families"
							:key="f"
							size="sm"
							:variant="family === f ? 'primary' : 'ghost'"
							:data-testid="`prov-family-${f}`"
							@click="family = f"
							>{{ f }}</IcButton
						>
					</div>
				</div>
				<div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3" data-testid="prov-plans">
					<button
						v-for="p in plans"
						:key="p.slug"
						type="button"
						class="flex flex-col gap-1 rounded border p-3 text-start hover:bg-surface-2"
						:class="
							size === p.slug ? 'border-accent bg-surface-2 ic-glow' : 'border-line'
						"
						:aria-pressed="size === p.slug"
						:data-testid="`prov-plan-${p.slug}`"
						@click="size = p.slug"
					>
						<span class="flex items-center justify-between gap-2">
							<span class="font-mono text-xs">{{ p.slug }}</span>
							<span class="text-sm font-medium"
								>{{ money(p.price_monthly)
								}}<span class="text-2xs text-fg-subtle">/mo</span></span
							>
						</span>
						<span class="text-xs text-fg-muted"
							>{{ p.vcpus }} vCPU · {{ gb(p.memory_mb) }} RAM · {{ p.disk_gb }} GB
							SSD · {{ p.transfer_tb }} TB</span
						>
					</button>
				</div>
				<p v-if="!plans.length" class="text-xs text-fg-subtle">
					No plans of this family in {{ region || "the chosen region" }}.
				</p>
				<p v-if="touched && errors.size" class="text-xs text-down" role="alert">
					{{ errors.size }}
				</p>
			</div>

			<div class="grid gap-4 sm:grid-cols-2">
				<IcField
					for-id="prov-hostname"
					label="Hostname"
					required
					hint="e.g. app-03.fra1"
					:error="touched ? errors.hostname : undefined"
				>
					<IcInput
						id="prov-hostname"
						v-model="hostname"
						mono
						placeholder="app-03.fra1"
						:invalid="touched && !!errors.hostname"
						data-testid="prov-hostname"
					/>
				</IcField>
				<IcField
					for-id="prov-role"
					label="Role"
					required
					hint="all = app + db on one server"
				>
					<IcSelect
						id="prov-role"
						v-model="role"
						:options="
							['all', 'app', 'db', 'proxy'].map((r) => ({ value: r, label: r }))
						"
					/>
				</IcField>
				<IcField
					class="sm:col-span-2"
					for-id="prov-tags"
					label="Tags"
					hint="Comma separated; the role and staging tags are added automatically."
				>
					<IcInput id="prov-tags" v-model="tagsText" mono placeholder="client-a, erp" />
				</IcField>
			</div>

			<div
				v-if="chosen"
				class="flex flex-wrap items-center gap-2 text-xs text-fg-muted"
				data-testid="prov-summary"
			>
				<IcBadge mono>{{ chosen.slug }}</IcBadge>
				<span>{{ region }}</span>
				<span>{{ catalogue?.defaults.image }}</span>
				<span class="ms-auto">{{ money(chosen.price_monthly) }}/month</span>
			</div>
			<p v-if="submitError" class="text-xs text-down" role="alert" data-testid="prov-error">
				{{ submitError }}
			</p>
		</form>
		<template #footer="{ close }">
			<IcButton variant="ghost" @click="close">Cancel</IcButton>
			<IcButton
				variant="primary"
				:disabled="!canSubmit"
				:loading="busy"
				data-testid="prov-submit"
				@click="submit"
				>Create server</IcButton
			>
		</template>
	</IcDialog>
</template>
