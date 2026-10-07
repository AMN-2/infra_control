// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { contrastRatio } from "@/design/color";
import { duration, ease, pulsePeriodMs } from "@/design/motion";

const css = readFileSync(
	fileURLToPath(new URL("../../../frontend/src/design/tokens.css", import.meta.url)),
	"utf8"
);
const rootBlock = css.slice(css.indexOf(":root {"), css.indexOf("@media"));

function tokenValue(name: string): string {
	const m = new RegExp(`${name}:\\s*([^;]+);`).exec(rootBlock);
	if (!m?.[1]) throw new Error(`token ${name} not found`);
	return m[1].trim();
}

describe("motion tokens", () => {
	it("tokens.css and motion.ts agree", () => {
		expect(tokenValue("--ic-dur-press")).toBe(`${duration.press * 1000}ms`);
		expect(tokenValue("--ic-dur-base")).toBe(`${duration.base * 1000}ms`);
		expect(tokenValue("--ic-dur-emphasis")).toBe(`${duration.emphasis * 1000}ms`);
		expect(tokenValue("--ic-dur-scene")).toBe(`${duration.scene * 1000}ms`);
		expect(tokenValue("--ic-ease")).toBe(`cubic-bezier(${ease.join(", ")})`);
		expect(tokenValue("--ic-pulse-period")).toBe(`${pulsePeriodMs}ms`);
	});

	it("respects the binding duration limits (§10.3.2)", () => {
		expect(duration.press).toBe(0.12);
		expect(duration.base).toBeGreaterThanOrEqual(0.2);
		expect(duration.emphasis).toBeLessThanOrEqual(0.24);
		expect(duration.scene).toBeLessThanOrEqual(0.4);
	});

	it("zeroes every duration under reduced motion", () => {
		const reduced = css.slice(css.search(/:root\[data-motion=["']reduce["']\]/));
		for (const name of ["press", "base", "emphasis", "scene"]) {
			expect(reduced).toContain(`--ic-dur-${name}: 0ms`);
		}
	});
});

describe("colour contrast (WCAG 2.x)", () => {
	const surfaces = ["--ic-canvas", "--ic-surface-1", "--ic-surface-2", "--ic-surface-3"];
	const AA = 4.5;
	const UI = 3;

	it.each(surfaces)("body text tokens are AA on %s", (surface) => {
		const bg = tokenValue(surface);
		for (const fg of ["--ic-fg", "--ic-fg-muted", "--ic-fg-subtle", "--ic-accent-text"]) {
			expect(
				contrastRatio(tokenValue(fg), bg),
				`${fg} on ${surface}`
			).toBeGreaterThanOrEqual(AA);
		}
	});

	it.each(surfaces)("status colours are readable as text on %s", (surface) => {
		const bg = tokenValue(surface);
		for (const tone of ["healthy", "degraded", "down", "running", "neutral"]) {
			expect(
				contrastRatio(tokenValue(`--ic-${tone}`), bg),
				`--ic-${tone} on ${surface}`
			).toBeGreaterThanOrEqual(AA);
		}
	});

	it("accent button text is AA in every state and the accent stands off the canvas", () => {
		for (const state of ["--ic-accent", "--ic-accent-hover", "--ic-accent-press"]) {
			expect(
				contrastRatio(tokenValue("--ic-accent-fg"), tokenValue(state)),
				`--ic-accent-fg on ${state}`
			).toBeGreaterThanOrEqual(AA);
		}
		expect(
			contrastRatio(tokenValue("--ic-accent"), tokenValue("--ic-canvas"))
		).toBeGreaterThanOrEqual(UI);
	});

	it("elevations are ordered from dark to light", () => {
		const l = surfaces.map((s) =>
			parseFloat(/oklch\(([\d.]+)/.exec(tokenValue(s))?.[1] ?? "")
		);
		expect([...l].sort((a, b) => a - b)).toEqual(l);
	});
});
