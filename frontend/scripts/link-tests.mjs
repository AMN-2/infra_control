#!/usr/bin/env node
// tests/frontend lives outside this package (plan §8). Link it to our node_modules
// so Node, TypeScript, Vitest, Playwright and ESLint resolve the same dependencies.
import { existsSync, lstatSync, symlinkSync } from "node:fs";
import { fileURLToPath } from "node:url";

const link = fileURLToPath(new URL("../../tests/frontend/node_modules", import.meta.url));
if (
	!existsSync(link) &&
	!(lstatSync(link, { throwIfNoEntry: false })?.isSymbolicLink() ?? false)
) {
	symlinkSync("../../frontend/node_modules", link, "dir");
	console.log("[link-tests] linked tests/frontend/node_modules");
}
