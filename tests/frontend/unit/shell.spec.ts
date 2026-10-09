import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { needsReauthentication } from "@/api/client";
import { clearToasts, toasts } from "@/design/components";
import { installGuards } from "@/router/guards";
import { routes } from "@/router";
import { navigationMatches, toPaletteItem, usePalette } from "@/app/usePalette";
import { useSessionStore } from "@/stores/session";

function makeRouter() {
	const router = createRouter({ history: createMemoryHistory("/infra/"), routes });
	installGuards(router);
	return router;
}

beforeEach(() => {
	setActivePinia(createPinia());
	clearToasts();
	delete window.infra_boot;
});

describe("auth guard", () => {
	it("sends an unauthenticated session to Frappe's login", async () => {
		const session = useSessionStore();
		const reauth = vi.spyOn(session, "reauthenticate").mockImplementation(() => undefined);
		vi.stubEnv("DEV", false);
		const router = makeRouter();
		await router.push("/servers").catch(() => undefined);
		expect(reauth).toHaveBeenCalled();
		vi.unstubAllEnvs();
	});

	it("keeps viewers out of admin-only routes and sets the document title", async () => {
		window.infra_boot = { session_user: "v@x", roles: ["Infra Viewer"], site_name: "s" };
		const router = makeRouter();
		await router.push("/_design");
		expect(router.currentRoute.value.name).toBe("overview");
		expect(toasts.items[0]?.title).toBe("Not permitted");
		expect(document.title).toBe("Overview · Infra Control");
		await router.push("/jobs/JOB-1");
		expect(router.currentRoute.value.name).toBe("job");
	});

	it("lets admins into the showcase", async () => {
		window.infra_boot = {
			session_user: "a@x",
			roles: ["Infra Admin", "Infra Operator", "Infra Viewer"],
			site_name: "s",
		};
		const router = makeRouter();
		await router.push("/_design");
		expect(router.currentRoute.value.name).toBe("design");
	});
});

describe("re-authentication rule", () => {
	it("matches the contract", () => {
		expect(needsReauthentication(401, {})).toBe(true);
		expect(needsReauthentication(403, { exc_type: "PermissionError" })).toBe(true);
		expect(needsReauthentication(403, { error: { code: "permission_denied" } })).toBe(false);
		expect(needsReauthentication(404, null)).toBe(false);
	});
});

describe("command palette", () => {
	it("filters navigation instantly and maps search results to routes", () => {
		expect(navigationMatches("").map((i) => i.title)).toEqual([
			"Overview",
			"Topology",
			"Servers",
			"Benches",
			"Sites",
			"Tenants",
			"Jobs",
			"Bulk rollouts",
			"Alerts",
		]);
		expect(navigationMatches("ser").map((i) => i.to)).toEqual(["/servers"]);
		expect(
			toPaletteItem({
				type: "site",
				id: "demo.iq",
				title: "demo.iq",
				subtitle: null,
				status: "Active",
				provider: "digitalocean",
			}).to
		).toBe("/sites/demo.iq");
		expect(
			toPaletteItem({
				type: "job",
				id: "JOB-1",
				title: "x",
				subtitle: null,
				status: "Running",
				provider: null,
			}).group
		).toBe("Jobs");
	});

	it("opens on Ctrl+K, moves with arrows and navigates on choose", async () => {
		window.infra_boot = { session_user: "a@x", roles: ["Infra Viewer"], site_name: "s" };
		const router = makeRouter();
		await router.push("/overview");
		const p = usePalette(router, 0);
		p.onKeydown(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }));
		expect(p.open.value).toBe(true);
		p.move(1);
		p.move(1);
		expect(p.items.value[p.active.value]?.title).toBe("Servers");
		await p.choose();
		expect(p.open.value).toBe(false);
		expect(router.currentRoute.value.path).toBe("/servers");
		p.onKeydown(new KeyboardEvent("keydown", { key: "k", metaKey: true }));
		p.onKeydown(new KeyboardEvent("keydown", { key: "Escape" }));
		expect(p.open.value).toBe(false);
	});
});
