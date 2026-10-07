// @vitest-environment node
/**
 * Enforces the "no hard-coded values" and "logical properties" rules across the app.
 * Only src/design/ may define raw colours, durations and easings.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const SRC = fileURLToPath(new URL("../../../frontend/src", import.meta.url));
// Only the token sources may hold raw values; design/components are checked like any feature.
const EXEMPT = [
	"design/tokens.css",
	"design/theme.css",
	"design/base.css",
	"design/motion.ts",
	"design/color.ts",
	"api/schema.d.ts",
	"realtime/events.generated.ts",
];

function walk(dir: string): string[] {
	return readdirSync(dir).flatMap((name) => {
		const path = join(dir, name);
		return statSync(path).isDirectory() ? walk(path) : [path];
	});
}

const files = walk(SRC)
	.filter((f) => /\.(vue|ts|css)$/.test(f))
	.map((f) => ({ path: relative(SRC, f), text: readFileSync(f, "utf8") }))
	.filter((f) => !EXEMPT.some((e) => f.path.startsWith(e)));

const RULES: { name: string; pattern: RegExp }[] = [
	{ name: "hex colour", pattern: /(?<![\w&])#[0-9a-fA-F]{3,8}\b(?![\w-])/ },
	{ name: "colour function", pattern: /\b(?:rgba?|hsla?|oklch|oklab|lab|lch)\(/ },
	{ name: "raw duration", pattern: /\b\d+m?s\b(?=[\s;,'"`)])/ },
	{ name: "raw easing", pattern: /cubic-bezier\(|\bease-(?:in|out|in-out|linear)\b/ },
	{ name: "Tailwind numeric duration", pattern: /\bduration-\d/ },
	{ name: "Tailwind arbitrary colour", pattern: /-\[(?:#|rgb|hsl|oklch)/ },
	{
		name: "physical CSS property (use logical)",
		pattern:
			/\b(?:margin|padding|border)-(?:left|right)\b|(?<![-\w])(?:left|right):|text-align:\s*(?:left|right)/,
	},
	{
		name: "physical Tailwind utility (use ms/me/ps/pe/start/end)",
		pattern:
			/(?<![\w-])(?:-?(?:ml|mr|pl|pr|left|right|rounded-[lr]|rounded-[tb][lr]|border-[lr])-(?:\d|\[|px\b|auto\b|full\b)|text-(?:left|right)\b)/,
	},
];

describe("design guard", () => {
	it("scans at least one file", () => {
		expect(files.length).toBeGreaterThan(0);
	});

	for (const rule of RULES) {
		it(`no ${rule.name} outside src/design`, () => {
			const hits = files.flatMap((f) =>
				f.text
					.split("\n")
					.map((line, i) => ({ line, i }))
					.filter(({ line }) => rule.pattern.test(line))
					.map(({ line, i }) => `${f.path}:${i + 1}  ${line.trim()}`)
			);
			expect(hits).toEqual([]);
		});
	}
});
