import type { Router } from "vue-router";
import { useSessionStore } from "@/stores/session";
import { pushToast } from "@/design/components";

const APP_TITLE = "Infra Control";

/**
 * Auth guard (B1.2): the Frappe page only renders for logged-in users, but a session can expire
 * while the tab is open. Without boot data we send the user through Frappe's login; routes with
 * `requiresRole` fall back to the overview with a toast. The server enforces every permission
 * again (403 permission_denied).
 */
export function installGuards(router: Router): void {
	router.beforeEach((to) => {
		const session = useSessionStore();
		if (!session.authenticated && !session.load()) {
			session.reauthenticate();
			return false;
		}
		const role = to.meta.requiresRole;
		if (role && !session.hasRole(role)) {
			pushToast({
				title: "Not permitted",
				description: `${to.meta.title} needs the ${role} role.`,
				tone: "degraded",
			});
			return { name: "overview" };
		}
		return true;
	});
	router.afterEach((to) => {
		document.title = `${to.meta.title} · ${APP_TITLE}`;
	});
}
