import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { DEV_BOOT, readBoot, type InfraBoot } from "@/api/boot";

export const ROLE_ADMIN = "Infra Admin";
export const ROLE_OPERATOR = "Infra Operator";
export const ROLE_VIEWER = "Infra Viewer";

/** Who is logged in and what they may do. The server enforces everything again. */
export const useSessionStore = defineStore("session", () => {
	const boot = ref<InfraBoot | null>(null);

	function load(): boolean {
		boot.value = readBoot() ?? (import.meta.env.DEV ? DEV_BOOT : null);
		return boot.value !== null;
	}

	const user = computed(() => boot.value?.session_user ?? "");
	const site = computed(() => boot.value?.site_name ?? "");
	const roles = computed(() => boot.value?.roles ?? []);
	const authenticated = computed(() => boot.value !== null);
	const hasRole = (role: string): boolean => roles.value.includes(role);
	const canOperate = computed(() => hasRole(ROLE_OPERATOR));
	const isAdmin = computed(() => hasRole(ROLE_ADMIN));

	/** Expired session (401, or 403 without an envelope): go through Frappe's login page. */
	function reauthenticate(): void {
		const next = encodeURIComponent(window.location.pathname + window.location.search);
		window.location.assign(`/login?redirect-to=${next}`);
	}

	return {
		boot,
		load,
		user,
		site,
		roles,
		authenticated,
		hasRole,
		canOperate,
		isAdmin,
		reauthenticate,
	};
});
