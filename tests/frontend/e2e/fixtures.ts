import { test as base, type Page } from "@playwright/test";

export { expect } from "@playwright/test";

/**
 * The built SPA expects the Frappe page's boot data (window.infra_boot). `vite preview` serves
 * no such page, so every e2e test injects an admin session before the app boots.
 */
/** For tests that create their own context: `await injectBoot(page)` before the first goto. */
export async function injectBoot(page: Page): Promise<void> {
	await page.addInitScript(() => {
		window.infra_boot = {
			csrf_token: "e2e",
			site_name: "e2e.localhost",
			session_user: "e2e@localhost",
			roles: ["Infra Admin", "Infra Operator", "Infra Viewer"],
			base_path: "/infra/",
			api_base: "/api/method/infra_control.api.",
			socketio_path: "/socket.io",
		};
	});
}

export const test = base.extend({
	page: async ({ page }, use) => {
		await injectBoot(page);
		await use(page);
	},
});
