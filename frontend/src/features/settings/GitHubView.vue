<script setup lang="ts">
import { onMounted, ref } from "vue";
import { Trash2 } from "lucide-vue-next";
import {
	IcBadge,
	IcButton,
	IcCard,
	IcConfirmDialog,
	IcEmptyState,
	IcField,
	IcIconButton,
	IcInput,
	IcPageHeader,
	IcSkeleton,
	pushToast,
} from "@/design/components";
import ErrorState from "@/features/system/ErrorState.vue";
import { relativeTime } from "@/lib/time";
import { useGitStore, type GitConnection } from "@/stores/git";

/**
 * Settings → GitHub (ADR 0005): paste a personal access token, it is verified against GitHub
 * and stored encrypted; the screen shows who the token belongs to and never the token.
 */
const git = useGitStore();
const label = ref("");
const token = ref("");
const touched = ref(false);
const removing = ref<GitConnection | null>(null);

async function submit(): Promise<void> {
	touched.value = true;
	if (!label.value.trim() || !token.value.trim()) return;
	const c = await git.connect(label.value.trim().toUpperCase(), token.value.trim());
	if (c) {
		pushToast({
			title: "GitHub connected",
			description: `${c.label} as ${c.login}`,
			tone: "healthy",
		});
		label.value = "";
		token.value = "";
		touched.value = false;
	}
}
async function confirmRemove(): Promise<void> {
	const c = removing.value;
	if (!c) return;
	const ok = await git.disconnect(c.name);
	pushToast(
		ok
			? { title: "Connection removed", description: c.label, tone: "neutral" }
			: { title: "Could not remove", description: git.saveError ?? "", tone: "down" }
	);
	removing.value = null;
}
onMounted(() => void git.fetchConnections());
</script>

<template>
	<div class="flex flex-col gap-6">
		<IcPageHeader
			title="GitHub"
			subtitle="Connect an account or organisation to browse repositories and pin versions when adding or updating apps."
		/>
		<div class="grid gap-5 lg:grid-cols-[22rem_1fr]">
			<IcCard
				title="Connect"
				subtitle="A fine-grained or classic personal access token with repository read access."
			>
				<form
					class="flex flex-col gap-4"
					data-testid="git-connect"
					@submit.prevent="submit"
				>
					<IcField
						for-id="git-label"
						label="Label"
						required
						hint="Stable id, e.g. GH-SMARTCHOICE. Reusing a label replaces its token."
						:error="touched && !label.trim() ? 'Required' : undefined"
					>
						<IcInput
							id="git-label"
							v-model="label"
							mono
							placeholder="GH-SMARTCHOICE"
							data-testid="git-label"
						/>
					</IcField>
					<IcField
						for-id="git-token"
						label="Access token"
						required
						hint="Verified against GitHub before it is stored. Never shown again."
						:error="touched && !token.trim() ? 'Required' : undefined"
					>
						<IcInput
							id="git-token"
							v-model="token"
							type="password"
							autocomplete="new-password"
							placeholder="github_pat_… or ghp_…"
							data-testid="git-token"
						/>
					</IcField>
					<p
						v-if="git.saveError"
						class="text-xs text-down"
						role="alert"
						data-testid="git-error"
					>
						{{ git.saveError }}
					</p>
					<IcButton
						type="submit"
						variant="primary"
						:loading="git.saving"
						data-testid="git-submit"
						>Verify and connect</IcButton
					>
				</form>
			</IcCard>
			<IcCard title="Connections" :padded="false">
				<ErrorState
					v-if="git.error && !git.connections.length"
					:error="git.error"
					@retry="git.fetchConnections()"
				/>
				<div v-else-if="git.loading && !git.loaded" class="p-4">
					<IcSkeleton :lines="3" />
				</div>
				<IcEmptyState
					v-else-if="!git.connections.length"
					title="No connections yet"
					description="Add a token to browse your repositories from the app pickers."
				/>
				<ul v-else class="divide-y divide-line" data-testid="git-connections">
					<li
						v-for="c in git.connections"
						:key="c.name"
						class="flex items-center gap-4 px-4 py-3"
						:data-testid="`git-${c.name}`"
					>
						<div class="flex min-w-0 flex-1 flex-col gap-1">
							<div class="flex flex-wrap items-center gap-2">
								<span class="font-mono text-sm">{{ c.label }}</span>
								<IcBadge :tone="c.enabled ? 'healthy' : 'neutral'" dot>{{
									c.enabled ? "enabled" : "disabled"
								}}</IcBadge>
								<IcBadge v-if="c.account_type" mono>{{ c.account_type }}</IcBadge>
							</div>
							<div class="flex flex-wrap gap-x-3 gap-y-1 text-xs text-fg-subtle">
								<span v-if="c.login">@{{ c.login }}</span>
								<span v-if="c.scopes.length"
									>scopes {{ c.scopes.join(", ") }}</span
								>
								<span v-if="c.verified_at" :title="c.verified_at"
									>verified {{ relativeTime(c.verified_at) }}</span
								>
							</div>
						</div>
						<IcIconButton
							label="Remove connection"
							size="sm"
							:data-testid="`git-remove-${c.name}`"
							@click="removing = c"
						>
							<Trash2 :size="14" />
						</IcIconButton>
					</li>
				</ul>
			</IcCard>
		</div>
		<IcConfirmDialog
			:model-value="removing !== null"
			title="Remove connection"
			description="Apps already cloned keep working; only browsing and new private clones stop."
			:expected="removing?.name ?? ''"
			confirm-label="Remove"
			:busy="git.saving"
			@update:model-value="
				(v) => {
					if (!v) removing = null;
				}
			"
			@confirm="confirmRemove"
		/>
	</div>
</template>
