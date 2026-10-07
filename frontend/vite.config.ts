import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";

const src = fileURLToPath(new URL("./src", import.meta.url));
const testsDir = fileURLToPath(new URL("../tests/frontend", import.meta.url));

/**
 * Where the built SPA is served from. The SPA itself always routes under `/infra`
 * (plan §2); the asset base depends on how the Frappe app serves the bundle,
 * which is an open question (docs/QUESTIONS.md, Q-B2). Override with INFRA_UI_BASE.
 */
const assetBase = process.env.INFRA_UI_BASE ?? "/infra/";

/** Dev only: where `/api` is proxied. Defaults to the Prism mock in contracts/mock. */
const apiTarget = process.env.INFRA_API_TARGET ?? "http://127.0.0.1:4010";
/** Dev only: where `/socket.io` is proxied. Defaults to the realtime replay in contracts/mock. */
const realtimeTarget = process.env.INFRA_REALTIME_TARGET ?? "http://127.0.0.1:9000";
/**
 * Dev only, real API: the Frappe site to talk to and an API token (`key:secret`) the proxy adds,
 * because a browser on the dev server has no session cookie for that site. Never exported to the
 * bundle. Use only with the dev server bound to 127.0.0.1: anyone reaching it acts as that user.
 */
const realSite = process.env.INFRA_SITE;
const realToken = process.env.INFRA_API_TOKEN;

/**
 * Prism validates the contract's security schemes, so against the default mock the proxy adds the
 * placeholder token the mock smoke test uses. Against a real site it adds INFRA_API_TOKEN (if
 * given) and the site header Frappe uses to pick the site.
 */
function apiHeaders(): Record<string, string> | undefined {
	if (!process.env.INFRA_API_TARGET) return { Authorization: "token mock:mock" };
	const headers: Record<string, string> = {};
	if (realToken) headers.Authorization = `token ${realToken}`;
	if (realSite) headers["X-Frappe-Site-Name"] = realSite;
	return headers;
}
/**
 * Frappe's Socket.IO server resolves the site from X-Frappe-Site-Name, rejects an Origin whose
 * host differs from Host, and authenticates by calling back `<Origin>/api/method/...`. Against a
 * real site the proxy therefore sends the site header, the token and an Origin on the site's web
 * port (INFRA_API_TARGET).
 */
function realtimeHeaders(): Record<string, string> | undefined {
	if (!process.env.INFRA_REALTIME_TARGET || !realSite) return undefined;
	const headers: Record<string, string> = { "X-Frappe-Site-Name": realSite };
	if (realToken) headers.Authorization = `token ${realToken}`;
	if (process.env.INFRA_API_TARGET) headers.Origin = process.env.INFRA_API_TARGET;
	return headers;
}

export default defineConfig(({ command }) => ({
	base: command === "build" ? assetBase : "/infra/",
	plugins: [vue(), tailwindcss()],
	resolve: {
		alias: { "@": src },
	},
	server: {
		port: 5173,
		strictPort: true,
		proxy: {
			"/api": { target: apiTarget, changeOrigin: true, headers: apiHeaders() },
			// Realtime: the replay server from contracts/mock (`npm run realtime`) or a real site.
			"/socket.io": {
				target: realtimeTarget,
				ws: true,
				changeOrigin: true,
				headers: realtimeHeaders(),
			},
		},
	},
	build: {
		outDir: "dist",
		emptyOutDir: true,
		manifest: true,
		target: "es2022",
		sourcemap: true,
	},
	test: {
		root: testsDir,
		include: ["unit/**/*.spec.ts"],
		environment: "jsdom",
		css: false,
	},
}));
