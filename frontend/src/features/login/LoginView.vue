<script setup lang="ts">
/** `/infra/login` (ADR 0008): the form over the scene; App.vue renders the scene itself. */
import { computed, onBeforeUnmount, onMounted } from "vue";
import { useRoute } from "vue-router";
import { safeDestination } from "@/api/auth";
import { transitions } from "@/design/motion";
import { useSessionStore } from "@/stores/session";
import LoginForm from "./LoginForm.vue";
import { LOGO } from "./media";
import { useLoginController } from "./useLoginTransition";

const route = useRoute();
const session = useSessionStore();
const controller = useLoginController();

const redirectTo = computed(() => {
	const raw = route.query["redirect-to"];
	return typeof raw === "string" ? raw : null;
});
controller.reset();
controller.setDestination(safeDestination(redirectTo.value));

const showForm = computed(
	() => controller.state.phase !== "transitioning" && controller.state.phase !== "done"
);
const siteName = computed(() => session.guestBoot?.site_name ?? "");

onMounted(() => {
	document.title = "Sign in · Infra Control";
});
onBeforeUnmount(() => {
	controller.reset();
});
</script>

<template>
	<main
		class="relative z-40 flex min-h-dvh flex-col justify-end px-4 pb-10 pt-16 sm:flex-row sm:items-center sm:justify-end sm:px-12 sm:py-12 lg:px-24"
		data-testid="login-page"
	>
		<Transition :name="transitions.fade">
			<section v-if="showForm" class="w-full max-w-sm">
				<header class="mb-8 flex items-center gap-3">
					<img
						:src="LOGO"
						alt="Smart Choice"
						class="h-9 w-9 rounded-md bg-surface-3 p-0.5"
					/>
					<div class="min-w-0">
						<p class="font-display text-md font-semibold tracking-tight text-fg">
							Infra Control
						</p>
						<p v-if="siteName" class="truncate text-xs text-fg-subtle">
							{{ siteName }}
						</p>
					</div>
				</header>
				<LoginForm
					:controller="controller"
					:alternatives="session.guestBoot?.login_alternatives"
					:redirect-to="redirectTo"
				/>
			</section>
		</Transition>
	</main>
</template>
