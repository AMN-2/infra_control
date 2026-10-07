#!/usr/bin/env node
// Enforces the initial-JS budget (plan §10.4): the entry chunk plus everything it
// imports statically must stay under 250 KB gzipped. Lazy chunks are excluded.
import { readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { fileURLToPath } from "node:url";

const BUDGET_KB = 250;
const dist = fileURLToPath(new URL("../dist/", import.meta.url));
const manifest = JSON.parse(readFileSync(`${dist}.vite/manifest.json`, "utf8"));

const seen = new Set();
const visit = (key) => {
	if (seen.has(key)) return;
	seen.add(key);
	for (const dep of manifest[key].imports ?? []) visit(dep);
};
for (const [key, chunk] of Object.entries(manifest)) if (chunk.isEntry) visit(key);

let total = 0;
for (const key of seen) {
	const size = gzipSync(readFileSync(dist + manifest[key].file)).length;
	total += size;
	console.log(`  ${(size / 1024).toFixed(1).padStart(7)} KB  ${manifest[key].file}`);
}
const totalKb = total / 1024;
console.log(`Initial JS: ${totalKb.toFixed(1)} KB gzipped (budget ${BUDGET_KB} KB)`);
if (totalKb > BUDGET_KB) {
	console.error("Initial JS is over budget.");
	process.exit(1);
}
