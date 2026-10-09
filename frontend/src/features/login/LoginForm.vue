<script setup lang="ts">
/** The sign-in form (ADR 0008): plain labels, visible focus, errors announced, one request at a time. */
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { IcButton, IcField, IcInput } from "@/design/components";
import type { LoginController } from "./useLoginTransition";

const props = defineProps<{
	controller: LoginController;
	/** Frappe's login page offers social login or LDAP; link to it. */
	alternatives?: boolean;
	/** `redirect-to` to carry over to Frappe's page. */
	redirectTo?: string | null;
}>();

const state = props.controller.state;
const email = ref("");
const password = ref("");
const otp = ref("");
const showPassword = ref(false);
const busy = computed(() => state.phase === "submitting");
const mfa = computed(() => state.phase === "mfa" || (busy.value && state.mfa !== null));
const fieldError = ref<string | null>(null);

const frappeLogin = computed(() => {
	const next = props.redirectTo ? `?redirect-to=${encodeURIComponent(props.redirectTo)}` : "";
	return `/login${next}`;
});

function focusField(id: string): void {
	void nextTick(() => {
		document.getElementById(id)?.focus();
	});
}

async function submit(): Promise<void> {
	if (busy.value) return;
	fieldError.value = null;
	if (mfa.value) {
		const code = otp.value.trim();
		if (!code) {
			fieldError.value = "Enter the verification code.";
			focusField("login-otp");
			return;
		}
		await props.controller.submitOtp(code);
		return;
	}
	const usr = email.value.trim();
	if (!usr || !password.value) {
		fieldError.value = !usr ? "Enter your email." : "Enter your password.";
		focusField(!usr ? "login-email" : "login-password");
		return;
	}
	await props.controller.submit({ usr, pwd: password.value });
}

function startOver(): void {
	props.controller.reset();
	otp.value = "";
	focusField("login-email");
}

watch(
	() => state.phase,
	(phase, previous) => {
		if (previous !== "submitting") return;
		// A failed attempt keeps the email and returns the user to the field that matters.
		if (phase === "idle" && state.error) focusField("login-password");
		if (phase === "mfa") focusField("login-otp");
	}
);

onMounted(() => {
	focusField("login-email");
});
</script>

<template>
	<form class="flex flex-col gap-4" novalidate data-testid="login-form" @submit.prevent="submit">
		<div>
			<h1 class="font-display text-xl font-semibold tracking-tight text-fg">
				{{ mfa ? "Verify it's you" : "Sign in" }}
			</h1>
			<p class="mt-1 text-sm text-fg-muted">
				{{
					mfa
						? (state.mfa?.prompt ?? "Enter the verification code.")
						: "Your infrastructure, in one place."
				}}
			</p>
		</div>

		<p
			v-if="state.error || fieldError"
			class="rounded border border-down/50 bg-down-soft px-3 py-2 text-sm text-fg"
			role="alert"
			aria-live="assertive"
			data-testid="login-error"
		>
			{{ fieldError ?? state.error }}
		</p>

		<template v-if="!mfa">
			<IcField label="Email" for-id="login-email" required>
				<IcInput
					id="login-email"
					v-model="email"
					type="text"
					autocomplete="username"
					placeholder="you@company.com"
					:disabled="busy"
					:invalid="fieldError === 'Enter your email.'"
				/>
			</IcField>
			<IcField label="Password" for-id="login-password" required>
				<div class="relative">
					<IcInput
						id="login-password"
						v-model="password"
						:type="showPassword ? 'text' : 'password'"
						autocomplete="current-password"
						:disabled="busy"
						:invalid="fieldError === 'Enter your password.'"
						class="pe-16"
					/>
					<button
						type="button"
						class="absolute inset-y-0 end-0 px-2.5 text-xs font-medium text-fg-muted hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-accent"
						:aria-pressed="showPassword"
						:aria-controls="'login-password'"
						data-testid="login-toggle-password"
						@click="showPassword = !showPassword"
					>
						{{ showPassword ? "Hide" : "Show" }}
					</button>
				</div>
			</IcField>
		</template>
		<template v-else>
			<IcField label="Verification code" for-id="login-otp" :hint="state.mfa?.method">
				<IcInput
					id="login-otp"
					v-model="otp"
					type="text"
					autocomplete="one-time-code"
					mono
					:disabled="busy"
					:invalid="fieldError !== null"
				/>
			</IcField>
		</template>

		<IcButton
			type="submit"
			variant="primary"
			class="mt-2 h-10"
			:loading="busy"
			:disabled="busy"
			data-testid="login-submit"
		>
			{{ busy ? (mfa ? "Verifying…" : "Signing in…") : mfa ? "Verify" : "Sign in" }}
		</IcButton>

		<div class="flex flex-wrap items-center justify-between gap-2 text-xs text-fg/60">
			<button
				v-if="mfa"
				type="button"
				class="underline-offset-2 hover:text-fg hover:underline"
				:disabled="busy"
				@click="startOver"
			>
				Start over
			</button>
			<a
				v-else
				:href="`${frappeLogin}#forgot`"
				class="underline-offset-2 hover:text-fg hover:underline"
			>
				Forgot password?
			</a>
			<a
				v-if="alternatives"
				:href="frappeLogin"
				class="underline-offset-2 hover:text-fg hover:underline"
				data-testid="login-alternatives"
			>
				Other sign-in methods
			</a>
		</div>
	</form>
</template>
