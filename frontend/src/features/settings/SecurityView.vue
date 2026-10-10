<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
	IcBadge,
	IcButton,
	IcCard,
	IcConfirmDialog,
	IcEmptyState,
	IcPageHeader,
	IcSkeleton,
	pushToast,
} from "@/design/components";
import ErrorState from "@/features/system/ErrorState.vue";
import { useSecurityStore, type SecurityCheck } from "@/stores/security";

/** Settings → Security (A4.1): the posture checks and the 2FA switch. */
const security = useSecurityStore();
const confirming = ref(false);
const tone = (s: SecurityCheck["status"]) =>
	s === "pass" ? "healthy" : s === "warn" ? "degraded" : "down";
const ordered = computed(() => {
	const rank = { fail: 0, warn: 1, pass: 2 } as const;
	return [...(security.posture?.checks ?? [])].sort((a, b) => rank[a.status] - rank[b.status]);
});
onMounted(() => void security.fetchPosture());

async function enable(): Promise<void> {
	const ok = await security.enable2fa();
	confirming.value = false;
	pushToast(
		ok
			? {
					title: "Two-factor authentication enabled",
					description:
						"Infra Admin and Infra Operator enrol an OTP app at their next login.",
					tone: "healthy",
				}
			: {
					title: "Could not enable 2FA",
					description: security.saveError ?? "",
					tone: "down",
				}
	);
}
</script>

<template>
	<div class="flex flex-col gap-6">
		<IcPageHeader
			title="Security"
			subtitle="The controls the plan requires before production, checked live. Nothing here shows a secret."
		>
			<template #actions>
				<div
					v-if="security.posture"
					class="flex items-center gap-2"
					data-testid="security-summary"
				>
					<IcBadge tone="healthy" dot>{{ security.posture.summary.pass }} pass</IcBadge>
					<IcBadge tone="degraded" dot>{{ security.posture.summary.warn }} warn</IcBadge>
					<IcBadge tone="down" dot>{{ security.posture.summary.fail }} fail</IcBadge>
					<IcButton size="sm" variant="ghost" @click="security.fetchPosture()"
						>Re-check</IcButton
					>
				</div>
			</template>
		</IcPageHeader>
		<IcCard v-if="security.error && !security.posture" :padded="false"
			><ErrorState :error="security.error" @retry="security.fetchPosture()"
		/></IcCard>
		<IcSkeleton v-else-if="!security.posture" variant="block" />
		<template v-else>
			<IcCard
				title="Two-factor authentication"
				subtitle="Frappe's OTP-app 2FA for the Infra roles only; other roles on this site are untouched."
			>
				<div class="flex flex-wrap items-center gap-3">
					<IcBadge
						:tone="security.posture.two_factor.enabled ? 'healthy' : 'down'"
						dot
						uppercase
						data-testid="tfa-state"
						>{{
							security.posture.two_factor.enabled ? "enabled" : "disabled"
						}}</IcBadge
					>
					<span class="text-xs text-fg-subtle">{{
						Object.entries(security.posture.two_factor.roles)
							.map(([r, on]) => `${r}: ${on ? "required" : "not required"}`)
							.join(" · ")
					}}</span>
					<IcButton
						v-if="!security.posture.two_factor.enabled"
						variant="primary"
						size="sm"
						class="ms-auto"
						data-testid="tfa-enable"
						@click="confirming = true"
						>Enable 2FA</IcButton
					>
				</div>
				<p class="mt-3 text-xs text-fg-subtle">
					Before enabling: make sure outgoing email works on this site (Frappe sends the
					OTP enrolment link by email) and that every Infra Admin can receive it, or an
					admin can lock themselves out.
				</p>
			</IcCard>
			<IcCard title="Checks" :padded="false">
				<IcEmptyState
					v-if="!ordered.length"
					title="No checks reported"
					description="The posture endpoint returned no checks for this site."
				/>
				<ul v-else class="divide-y divide-line" data-testid="security-checks">
					<li
						v-for="c in ordered"
						:key="c.id"
						class="flex flex-col gap-1 px-4 py-3 md:flex-row md:items-start md:gap-4"
						:data-testid="`check-${c.id}`"
						:data-status="c.status"
					>
						<IcBadge
							:tone="tone(c.status)"
							dot
							uppercase
							class="w-16 justify-center"
							>{{ c.status }}</IcBadge
						>
						<div class="flex min-w-0 flex-col gap-0.5">
							<span class="text-sm font-medium">{{ c.title }}</span>
							<span class="text-xs text-fg-muted">{{ c.detail }}</span>
							<span
								v-if="c.hint && c.status !== 'pass'"
								class="text-xs text-fg-subtle"
								>{{ c.hint }}</span
							>
						</div>
					</li>
				</ul>
			</IcCard>
			<IcConfirmDialog
				v-model="confirming"
				title="Enable two-factor authentication"
				description="Every Infra Admin and Infra Operator will have to enrol an OTP app at their next login. Confirm with ENABLE-2FA."
				expected="ENABLE-2FA"
				confirm-label="Enable"
				:busy="security.saving"
				@confirm="enable"
			/>
		</template>
	</div>
</template>
