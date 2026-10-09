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
	IcSwitch,
	pushToast,
} from "@/design/components";
import { useInventoryStore, type GitRefList, type InstalledApp } from "@/stores/inventory";
import { useJobsStore } from "@/stores/jobs";

/**
 * Move one app to another branch or tag (ADR 0009). Lists the upstream refs, then queues
 * `bench.update` for that app with `branch` set; the playbook checks the ref out, pulls
 * (branches only), installs requirements, backs up and migrates every site, builds, restarts.
 */
const props = defineProps<{ bench: string; app: InstalledApp }>();
const open = defineModel<boolean>({ default: false });
const inventory = useInventoryStore();
const jobs = useJobsStore();
const router = useRouter();

const refs = ref<GitRefList | null>(null);
const loadError = ref<string | null>(null);
const query = ref("");
const kind = ref<"tag" | "branch">("tag");
const chosen = ref("");
const migrate = ref(true);
const build = ref(true);
const busy = ref(false);

async function load(): Promise<void> {
	refs.value = null;
	loadError.value = null;
	chosen.value = "";
	const r = await inventory.fetchBenchRefs(props.bench, props.app.app);
	if (!r) {
		loadError.value = inventory.error?.message ?? "Could not list the upstream versions.";
		return;
	}
	refs.value = r;
	kind.value = r.items.some((i) => i.kind === "tag") ? "tag" : "branch";
	if (props.app.latest_tag && r.items.some((i) => i.name === props.app.latest_tag)) {
		chosen.value = props.app.latest_tag;
	}
}
watch(
	() => [open.value, props.app.app],
	([isOpen]) => {
		if (isOpen) void load();
	},
	{ immediate: true }
);

const options = computed(() => {
	const text = query.value.trim().toLowerCase();
	return (refs.value?.items ?? [])
		.filter((i) => i.kind === kind.value && (!text || i.name.toLowerCase().includes(text)))
		.map((i) => ({
			value: i.name,
			label: i.name === props.app.branch ? `${i.name} (current)` : i.name,
		}));
});
const current = computed(() => props.app.branch ?? "");

async function submit(): Promise<void> {
	if (!chosen.value || busy.value) return;
	busy.value = true;
	const job = await jobs.runPlaybook({
		playbook: "bench.update",
		target_doctype: "Bench",
		target_name: props.bench,
		params: {
			apps: [props.app.app],
			branch: chosen.value,
			migrate: migrate.value,
			build: build.value,
		},
	});
	busy.value = false;
	if (!job) {
		const e = jobs.error;
		pushToast({
			title: "Version switch not queued",
			description: e ? `${e.message} (${e.code})` : "The job could not be created.",
			tone: "down",
		});
		return;
	}
	pushToast({
		title: `${props.app.app} → ${chosen.value}`,
		description: `${job.name} on ${props.bench}`,
		tone: "running",
	});
	open.value = false;
	void router.push(`/jobs/${encodeURIComponent(job.name)}`);
}
</script>

<template>
	<IcDialog
		v-model="open"
		:title="`Switch ${app.app} version`"
		description="Check out a tag or branch upstream, pull, install requirements, back up and migrate every site, build and restart."
		size="md"
	>
		<form class="flex flex-col gap-4" data-testid="switch-version" @submit.prevent="submit">
			<div class="flex flex-wrap items-center gap-2 text-xs text-fg-muted">
				<span>Now</span>
				<IcBadge mono>{{ current || "detached" }}</IcBadge>
				<IcBadge v-if="app.version" mono tone="neutral">v{{ app.version }}</IcBadge>
				<IcBadge v-if="app.latest_tag" mono tone="healthy" class="ms-auto"
					>latest {{ app.latest_tag }}</IcBadge
				>
			</div>
			<p v-if="loadError" class="text-sm text-down" role="alert">{{ loadError }}</p>
			<template v-else>
				<div class="flex gap-2" role="radiogroup" aria-label="Reference kind">
					<IcButton
						v-for="k in ['tag', 'branch'] as const"
						:key="k"
						size="sm"
						:variant="kind === k ? 'primary' : 'secondary'"
						:aria-pressed="kind === k"
						@click="kind = k"
						>{{ k === "tag" ? "Tags" : "Branches" }}</IcButton
					>
					<span class="ms-auto self-center text-xs text-fg-subtle">{{
						refs ? `${options.length} shown` : "loading…"
					}}</span>
				</div>
				<IcField label="Filter" for-id="switch-filter">
					<IcInput
						id="switch-filter"
						v-model="query"
						type="search"
						mono
						placeholder="v15."
					/>
				</IcField>
				<IcField label="Version" for-id="switch-ref" required>
					<IcSelect
						id="switch-ref"
						v-model="chosen"
						:options="options"
						placeholder="Choose a reference"
					/>
				</IcField>
				<div class="flex flex-wrap gap-6 text-sm">
					<span class="flex items-center gap-2"
						><IcSwitch v-model="migrate" label="Back up and migrate sites" />Back up
						and migrate sites</span
					>
					<span class="flex items-center gap-2"
						><IcSwitch v-model="build" label="Build assets" />Build assets</span
					>
				</div>
			</template>
			<div class="flex justify-end gap-2">
				<IcButton @click="open = false">Cancel</IcButton>
				<IcButton
					type="submit"
					variant="primary"
					:disabled="!chosen || chosen === current"
					:loading="busy"
					data-testid="switch-submit"
				>
					Queue switch
				</IcButton>
			</div>
		</form>
	</IcDialog>
</template>
