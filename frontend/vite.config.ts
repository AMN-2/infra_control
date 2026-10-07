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
			"/api": { target: apiTarget, changeOrigin: true },
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
