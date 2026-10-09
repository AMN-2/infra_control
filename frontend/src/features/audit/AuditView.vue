<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import {
	IcBadge,
	IcButton,
	IcCard,
	IcEmptyState,
	IcField,
	IcInput,
	IcPageHeader,
	IcSelect,
	IcSkeleton,
} from "@/design/components";
import ErrorState from "@/features/system/ErrorState.vue";
import { relativeTime } from "@/lib/time";
import { useSecurityStore } from "@/stores/security";

/** The immutable audit log, newest first, with the filters the API offers. */
const security = useSecurityStore();
const user = ref("");
const action = ref("");
const targetDoctype = ref("");
const targetName = ref("");
const query = computed(() => ({
	...(user.value.trim() ? { user: user.value.trim() } : {}),
	...(action.value.trim() ? { action: action.value.trim() } : {}),
	...(targetDoctype.value
		? {
				target_doctype: targetDoctype.value as
					"Server" | "Site" | "Bench" | "Provider Account",
			}
		: {}),
	...(targetName.value.trim() ? { target_name: targetName.value.trim() } : {}),
}));
let timer: ReturnType<typeof setTimeout> | undefined;
watch(query, () => {
	if (timer !== undefined) clearTimeout(timer);
	timer = setTimeout(() => void security.fetchAudit(query.value), 250);
});
onMounted(() => void security.fetchAudit());
function targetLink(t: { target_doctype: string; target_name: string }): string | null {
	if (t.target_doctype === "Server") return `/servers/${encodeURIComponent(t.target_name)}`;
	if (t.target_doctype === "Site") return `/sites/${encodeURIComponent(t.target_name)}`;
	return null;
}
</script>

<template>
	<div class="flex flex-col gap-4">
		<IcPageHeader
			title="Audit log"
			subtitle="Every action, who did it, on what, and the job it produced. Rows are never edited or deleted."
		/>
		<div class="flex flex-wrap items-end gap-3">
			<IcField for-id="audit-user" label="User"
				><IcInput
					id="audit-user"
					v-model="user"
					mono
					placeholder="user@…"
					data-testid="audit-user"
			/></IcField>
			<IcField for-id="audit-action" label="Action"
				><IcInput
					id="audit-action"
					v-model="action"
					mono
					placeholder="jobs.run"
					data-testid="audit-action"
			/></IcField>
			<IcField for-id="audit-dt" label="Target type">
				<IcSelect
					id="audit-dt"
					v-model="targetDoctype"
					:options="[
						{ value: '', label: 'Any' },
						{ value: 'Server', label: 'Server' },
						{ value: 'Site', label: 'Site' },
						{ value: 'Bench', label: 'Bench' },
						{ value: 'Provider Account', label: 'Provider Account' },
					]"
				/>
			</IcField>
			<IcField for-id="audit-target" label="Target"
				><IcInput id="audit-target" v-model="targetName" mono
			/></IcField>
		</div>
		<IcCard v-if="security.error && !security.audit.length" :padded="false"
			><ErrorState :error="security.error" @retry="security.fetchAudit(query)"
		/></IcCard>
		<div v-else-if="security.loading && !security.audit.length">
			<IcSkeleton variant="block" />
		</div>
		<IcEmptyState
			v-else-if="!security.audit.length"
			title="No audit rows"
			description="Nothing matches these filters."
		/>
		<IcCard v-else :padded="false">
			<ul class="divide-y divide-line" data-testid="audit-list">
				<li
					v-for="e in security.audit"
					:key="e.name"
					class="flex flex-col gap-1 px-4 py-3 md:flex-row md:items-center md:gap-4"
				>
					<span class="w-28 shrink-0 font-mono text-xs text-fg-subtle" :title="e.ts">{{
						relativeTime(e.ts)
					}}</span>
					<IcBadge
						:tone="
							e.result === 'success'
								? 'healthy'
								: e.result === 'denied'
									? 'degraded'
									: 'down'
						"
						dot
						uppercase
						class="w-20 justify-center"
						>{{ e.result }}</IcBadge
					>
					<span class="font-mono text-sm">{{ e.action }}</span>
					<span class="text-xs text-fg-muted">by {{ e.user }}</span>
					<template v-if="e.target">
						<RouterLink
							v-if="targetLink(e.target)"
							:to="targetLink(e.target)!"
							class="font-mono text-xs hover:underline"
							>{{ e.target.target_doctype }} {{ e.target.target_name }}</RouterLink
						>
						<span v-else class="font-mono text-xs text-fg-subtle"
							>{{ e.target.target_doctype }} {{ e.target.target_name }}</span
						>
					</template>
					<RouterLink
						v-if="e.job"
						:to="`/jobs/${encodeURIComponent(e.job)}`"
						class="ms-auto font-mono text-xs text-fg-muted hover:underline"
						>{{ e.job }}</RouterLink
					>
				</li>
			</ul>
			<div v-if="security.auditCursor" class="p-3">
				<IcButton
					size="sm"
					@click="security.fetchAudit(query, security.auditCursor ?? undefined)"
					>Load older</IcButton
				>
			</div>
		</IcCard>
	</div>
</template>
