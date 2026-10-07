import { createApp } from "vue";
import { createPinia } from "pinia";
import "@fontsource-variable/space-grotesk";
import "@fontsource-variable/jetbrains-mono";
import App from "./App.vue";
import { router } from "./router";
import { installMotionEnvironment } from "./design/motion";
import { authHooks } from "./api/client";
import { connectRealtime } from "./realtime";
import { realtimeOrigin } from "./api/boot";
import { useSessionStore } from "./stores/session";
import { useOverviewStore } from "./stores/overview";
import { useInventoryStore } from "./stores/inventory";
import { useJobsStore } from "./stores/jobs";
import { useAlertsStore } from "./stores/alerts";
import "./main.css";

installMotionEnvironment();
const pinia = createPinia();
const app = createApp(App).use(pinia).use(router);

const session = useSessionStore();
if (session.load()) {
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
app.mount("#app");
