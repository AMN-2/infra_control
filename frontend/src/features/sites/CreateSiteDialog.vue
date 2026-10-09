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
import { useInventoryStore } from "@/stores/inventory";
import { useJobsStore } from "@/stores/jobs";

/**
 * New site: server → bench → domain → apps to install (from the bench's installed apps) →
 * Administrator password, then `jobs.run site.create` on the bench (the job creates the Site
 * document; the operator lands on the job). Apps not yet on the bench are added first with
 * "Add app to bench".
 */
const props = defineProps<{ bench?: string | null }>();
const open = defineModel<boolean>({ default: false });
const inventory = useInventoryStore();
const jobs = useJobsStore();
const router = useRouter();

const server = ref("");
const benchName = ref("");
const domain = ref("");
const password = ref("");
const selectedApps = ref<string[]>([]);
const touched = ref(false);
const busy = ref(false);
const submitError = ref<string | null>(null);
const revealed = ref(false);

const serverOptions = computed(() =>
	inventory.servers
		.filter((s) => s.status !== "Archived" && s.capabilities.includes("site"))
		.map((s) => ({ value: s.name, label: `${s.hostname} · ${s.name}` }))
);
const benchOptions = computed(() =>
	inventory.benches
		.filter((b) => !server.value || b.server === server.value)
		.map((b) => ({
			value: b.name,
			label: `${b.title} · ${b.frappe_version ?? ""} · ${b.site_count} sites`,
		}))
);
const chosenBench = computed(() => inventory.benches.find((b) => b.name === benchName.value));
const apps = computed(() => (chosenBench.value?.apps ?? []).filter((a) => a.app !== "frappe"));
const HOSTNAME =
	/^(?=.{1,253}$)[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$/;
const errors = computed(() => {
	const e: Record<string, string> = {};
	if (!benchName.value) e.bench = "Choose a bench";
	if (!HOSTNAME.test(domain.value.trim().toLowerCase())) e.domain = "Not a valid domain";
	if (password.value.length < 12) e.password = "At least 12 characters";
	return e;
});
const valid = computed(() => Object.keys(errors.value).length === 0);

function toggleApp(app: string, on: boolean): void {
	const set = new Set(selectedApps.value);
	if (on) set.add(app);
	else set.delete(app);
	selectedApps.value = apps.value.map((a) => a.app).filter((a) => set.has(a));
}
function generatePassword(): void {
	const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
	const bytes = new Uint8Array(20);
	crypto.getRandomValues(bytes);
	password.value = Array.from(bytes, (b) => alphabet[b % alphabet.length]).join("");
	revealed.value = true;
}

watch(open, async (v) => {
	if (!v) return;
	touched.value = false;
	submitError.value = null;
	revealed.value = false;
	if (!inventory.servers.length) await inventory.fetchServers();
	if (!inventory.benches.length) await inventory.fetchBenches();
	if (props.bench) {
		benchName.value = props.bench;
		server.value = inventory.benches.find((b) => b.name === props.bench)?.server ?? "";
	} else if (!server.value && serverOptions.value[0]) {
		server.value = serverOptions.value[0].value;
	}
});
watch(server, () => {
	if (chosenBench.value?.server !== server.value)
		benchName.value = benchOptions.value[0]?.value ?? "";
});
watch(benchName, () => {
	selectedApps.value = apps.value.map((a) => a.app);
});

async function submit(): Promise<void> {
	touched.value = true;
	if (!valid.value || busy.value) return;
	busy.value = true;
	submitError.value = null;
	const job = await jobs.runPlaybook({
		playbook: "site.create",
		target_doctype: "Bench",
		target_name: benchName.value,
		params: {
			domain: domain.value.trim().toLowerCase(),
			apps: selectedApps.value,
			admin_password: password.value,
		},
	});
	busy.value = false;
	if (!job) {
		const e = jobs.error;
		submitError.value = e ? `${e.message} (${e.code})` : "The job could not be created.";
		return;
	}
	pushToast({
		title: "Creating site",
		description: `${job.name} · ${domain.value}`,
		tone: "running",
	});
	open.value = false;
	password.value = "";
	void router.push(`/jobs/${encodeURIComponent(job.name)}`);
}
</script>

<template>
	<IcDialog
		v-model="open"
		title="New site"
		description="bench new-site on the chosen bench, then the selected apps, scheduler on, nginx reloaded. The Site appears when the job succeeds."
		size="lg"
	>
		<form class="flex flex-col gap-5" data-testid="create-site" @submit.prevent="submit">
			<div class="grid gap-4 sm:grid-cols-2">
				<IcField for-id="site-server" label="Server" required>
					<IcSelect
						id="site-server"
						v-model="server"
						:options="serverOptions"
						placeholder="Choose server"
						data-testid="site-server"
					/>
				</IcField>
				<IcField
					for-id="site-bench"
					label="Bench"
					required
					:error="touched ? errors.bench : undefined"
				>
					<IcSelect
						id="site-bench"
						v-model="benchName"
						:options="benchOptions"
						placeholder="Choose bench"
						data-testid="site-bench"
					/>
				</IcField>
				<IcField
					for-id="site-domain"
					label="Domain"
					required
					hint="e.g. erp.client-d.iq"
					:error="touched ? errors.domain : undefined"
				>
					<IcInput
						id="site-domain"
						v-model="domain"
						mono
						placeholder="erp.client-d.iq"
						:invalid="touched && !!errors.domain"
						data-testid="site-domain"
					/>
				</IcField>
				<IcField
					for-id="site-password"
					label="Administrator password"
					required
					hint="At least 12 characters. Sent write-only; never shown again."
					:error="touched ? errors.password : undefined"
				>
					<div class="flex gap-2">
						<IcInput
							id="site-password"
							v-model="password"
							:type="revealed ? 'text' : 'password'"
							mono
							autocomplete="new-password"
							:invalid="touched && !!errors.password"
							data-testid="site-password"
						/>
						<IcButton size="sm" @click="generatePassword">Generate</IcButton>
					</div>
				</IcField>
			</div>

			<div class="flex flex-col gap-2">
				<div class="flex items-center gap-2">
					<span class="eyebrow">Apps to install</span>
					<span class="text-xs text-fg-subtle"
						>frappe is always installed; the rest come from the bench</span
					>
				</div>
				<IcSkeleton v-if="inventory.loading && !inventory.benches.length" :lines="2" />
				<p
					v-else-if="bench && !apps.length"
					class="text-xs text-fg-subtle"
					data-testid="site-no-apps"
				>
					Only frappe is on this bench. Add apps with
					<span class="font-mono">Add app to bench</span> on the server first.
				</p>
				<div
					v-else
					class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3"
					data-testid="site-apps"
				>
					<label
						v-for="a in apps"
						:key="a.app"
						class="flex cursor-pointer items-center gap-2 rounded border border-line p-2.5 text-sm hover:bg-surface-2"
						:class="{ 'border-accent bg-surface-2': selectedApps.includes(a.app) }"
					>
						<input
							type="checkbox"
							class="accent-accent"
							:checked="selectedApps.includes(a.app)"
							:data-testid="`site-app-${a.app}`"
							@change="
								(e) => toggleApp(a.app, (e.target as HTMLInputElement).checked)
							"
						/>
						<span class="font-mono">{{ a.app }}</span>
						<IcBadge v-if="a.branch" mono class="ms-auto">{{ a.branch }}</IcBadge>
					</label>
				</div>
			</div>

			<p v-if="submitError" class="text-xs text-down" role="alert" data-testid="site-error">
				{{ submitError }}
			</p>
		</form>
		<template #footer="{ close }">
			<IcButton variant="ghost" @click="close">Cancel</IcButton>
			<IcButton
				variant="primary"
				:disabled="busy || (touched && !valid)"
				:loading="busy"
				data-testid="site-submit"
				@click="submit"
				>Create site</IcButton
			>
		</template>
	</IcDialog>
</template>
