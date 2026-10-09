import { authHooks } from "@/api/client";
import { realtimeOrigin } from "@/api/boot";
import { connectRealtime } from "@/realtime";
import { useSessionStore } from "@/stores/session";
import { useOverviewStore } from "@/stores/overview";
import { useInventoryStore } from "@/stores/inventory";
import { useJobsStore } from "@/stores/jobs";
import { useAlertsStore } from "@/stores/alerts";

let started = false;

/**
 * Everything that needs a session: re-authentication on 401, the realtime socket and the live
 * store subscriptions. Runs once, either at page load (main.ts) or right after the in-app login
 * confirmed the session (features/login, ADR 0008).
 */
export function startAuthenticatedServices(): void {
	if (started) return;
	started = true;
	const session = useSessionStore();
	authHooks.onReauthenticate = () => {
		session.reauthenticate();
	};
	connectRealtime({
		site: session.site,
		path: session.boot?.socketio_path,
		origin: realtimeOrigin(session.boot),
	});
	useOverviewStore().subscribe();
	useInventoryStore().subscribe();
	useJobsStore().subscribe();
	useAlertsStore().subscribe();
}

/** Tests only. */
export function _resetBootstrapForTests(): void {
	started = false;
}
