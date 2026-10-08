<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { IcInput, IcSelect, IcSkeleton } from "@/design/components";
import { useGitStore, type GitRepo } from "@/stores/git";

/**
 * The three `x-picker` fields of a playbook form (ADR 0005): connection → repository search →
 * branch/tag. Values land in the ordinary params (`connection`, `repo` as clone URL, `branch`)
 * so the backend sees plain strings; typing a URL by hand still works without a connection.
 */
const props = defineProps<{
	connection: string;
	repo: string;
	branch: string;
	/** Which pickers the schema asked for. */
	wants: { connection: boolean; repo: boolean; branch: boolean };
	invalidRepo?: boolean;
}>();
const emit = defineEmits<{
	"update:connection": [value: string];
	"update:repo": [value: string];
	"update:branch": [value: string];
}>();

const git = useGitStore();
const query = ref("");
const results = ref<GitRepo[]>([]);
const searching = ref(false);
const searchError = ref<string | null>(null);
const chosen = ref<GitRepo | null>(null);
const refsLoading = ref(false);
const refsError = ref<string | null>(null);

const connectionOptions = computed(() =>
	git.connections
		.filter((c) => c.enabled)
		.map((c) => ({ value: c.name, label: `${c.label}${c.login ? " · @" + c.login : ""}` }))
);
const refKey = computed(() =>
	props.connection && chosen.value ? `${props.connection}:${chosen.value.full_name}` : ""
);
const refOptions = computed(() => {
	const entry = refKey.value ? git.refs[refKey.value] : undefined;
	if (!entry) return [];
	return entry.items.map((r) => ({ value: r.name, label: `${r.name}  (${r.kind} ${r.sha})` }));
});

let timer: ReturnType<typeof setTimeout> | undefined;
function scheduleSearch(text: string): void {
	query.value = text;
	if (timer !== undefined) clearTimeout(timer);
	timer = setTimeout(() => void search(), 250);
}
async function search(): Promise<void> {
	if (!props.connection) return;
	searching.value = true;
	searchError.value = null;
	try {
		results.value = (await git.searchRepos(props.connection, query.value)).items;
	} catch (e) {
		searchError.value = e instanceof Error ? e.message : String(e);
		results.value = [];
	} finally {
		searching.value = false;
	}
}
async function pick(r: GitRepo): Promise<void> {
	chosen.value = r;
	emit("update:repo", r.clone_url);
	results.value = [];
	query.value = r.full_name;
	refsLoading.value = true;
	refsError.value = null;
	try {
		const entry = await git.fetchRefs(props.connection, r.full_name);
		if (entry && !props.branch) emit("update:branch", r.default_branch);
	} catch (e) {
		refsError.value = e instanceof Error ? e.message : String(e);
	} finally {
		refsLoading.value = false;
	}
}
watch(
	() => props.connection,
	() => {
		chosen.value = null;
		results.value = [];
		query.value = "";
	}
);
onMounted(() => {
	if (!git.loaded) void git.fetchConnections();
});
</script>

<template>
	<div class="flex flex-col gap-4" data-testid="git-pickers">
		<div v-if="wants.connection" class="flex flex-col gap-1.5">
			<label for="param-connection" class="text-xs font-medium text-fg-muted"
				>GitHub connection</label
			>
			<IcSelect
				id="param-connection"
				:model-value="connection"
				:options="connectionOptions"
				placeholder="Public URL (no connection)"
				data-testid="picker-connection"
				@update:model-value="(v: string) => emit('update:connection', v)"
			/>
			<p v-if="git.loaded && !connectionOptions.length" class="text-xs text-fg-subtle">
				No GitHub connection yet.
				<RouterLink to="/settings/github" class="underline hover:text-fg"
					>Add one</RouterLink
				>
				to browse repositories; a public https URL works without it.
			</p>
		</div>
		<div v-if="wants.repo" class="flex flex-col gap-1.5">
			<label for="param-repo" class="text-xs font-medium text-fg-muted">
				Repository <span class="text-down" aria-hidden="true">*</span>
			</label>
			<IcInput
				v-if="connection"
				id="param-repo"
				:model-value="query"
				mono
				placeholder="Search owner/name…"
				:invalid="invalidRepo"
				data-testid="picker-repo-search"
				@update:model-value="scheduleSearch"
			/>
			<IcInput
				v-else
				id="param-repo"
				:model-value="repo"
				mono
				placeholder="https://github.com/org/app.git"
				:invalid="invalidRepo"
				data-testid="picker-repo-url"
				@update:model-value="(v: string) => emit('update:repo', v)"
			/>
			<IcSkeleton v-if="searching" :lines="2" />
			<ul
				v-else-if="results.length"
				class="max-h-56 overflow-auto rounded border border-line bg-surface-2"
				data-testid="picker-repo-results"
			>
				<li v-for="r in results" :key="r.full_name">
					<button
						type="button"
						class="flex w-full flex-col gap-0.5 px-3 py-2 text-start hover:bg-surface-3"
						:data-testid="`pick-${r.full_name}`"
						@click="pick(r)"
					>
						<span class="font-mono text-sm"
							>{{ r.full_name
							}}<span v-if="r.private" class="ms-2 text-2xs text-fg-subtle uppercase"
								>private</span
							></span
						>
						<span v-if="r.description" class="truncate text-xs text-fg-subtle">{{
							r.description
						}}</span>
					</button>
				</li>
			</ul>
			<p v-if="searchError" class="text-xs text-down" role="alert">{{ searchError }}</p>
			<p v-else-if="chosen" class="text-xs text-fg-subtle">{{ repo }}</p>
		</div>
		<div v-if="wants.branch" class="flex flex-col gap-1.5">
			<label for="param-branch" class="text-xs font-medium text-fg-muted"
				>Branch or tag</label
			>
			<IcSkeleton v-if="refsLoading" :lines="1" />
			<IcSelect
				v-else-if="refOptions.length"
				id="param-branch"
				:model-value="branch"
				:options="refOptions"
				placeholder="Default branch"
				data-testid="picker-ref"
				@update:model-value="(v: string) => emit('update:branch', v)"
			/>
			<IcInput
				v-else
				id="param-branch"
				:model-value="branch"
				mono
				placeholder="version-15 or v1.2.0 (empty = default)"
				data-testid="picker-ref-text"
				@update:model-value="(v: string) => emit('update:branch', v)"
			/>
			<p v-if="refsError" class="text-xs text-down" role="alert">{{ refsError }}</p>
		</div>
	</div>
</template>
