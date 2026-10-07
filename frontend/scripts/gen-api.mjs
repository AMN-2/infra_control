#!/usr/bin/env node
// Generates src/api/schema.d.ts from contracts/openapi.yaml (plan §10.4).
//   node scripts/gen-api.mjs          write the file
//   node scripts/gen-api.mjs --check  fail if the committed file is stale (CI)
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const contract = fileURLToPath(new URL("../../contracts/openapi.yaml", import.meta.url));
const target = fileURLToPath(new URL("../src/api/schema.d.ts", import.meta.url));
const check = process.argv.includes("--check");

const HEADER =
	"/* eslint-disable */\n// GENERATED from contracts/openapi.yaml by scripts/gen-api.mjs. Do not edit.\n\n";
const STUB = `${HEADER}// contracts/openapi.yaml is not merged yet: no endpoints are available.\nexport interface paths {}\nexport interface components {\n  schemas: Record<string, never>\n}\n`;

let output;
if (existsSync(contract)) {
	const ast = await openapiTS(new URL(`file://${contract}`), { immutable: true });
	output = HEADER + astToString(ast);
} else {
	console.warn("[gen-api] contracts/openapi.yaml not found; using the empty stub.");
	output = STUB;
}

if (check) {
	const current = existsSync(target) ? readFileSync(target, "utf8") : "";
	if (current !== output) {
		console.error(
			"[gen-api] src/api/schema.d.ts is out of date. Run `npm run gen:api` and commit."
		);
		process.exit(1);
	}
	console.log("[gen-api] schema.d.ts is up to date.");
} else {
	writeFileSync(target, output);
	console.log(`[gen-api] wrote ${target}`);
}
