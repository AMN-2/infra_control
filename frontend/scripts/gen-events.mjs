#!/usr/bin/env node
// Generates src/realtime/events.generated.ts from contracts/events/*.schema.json (plan §10.4):
// the payload types and the schemas themselves (for runtime validation with Ajv).
//   node scripts/gen-events.mjs          write the file
//   node scripts/gen-events.mjs --check  fail if the committed file is stale (CI)
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";

const eventsDir = fileURLToPath(new URL("../../contracts/events/", import.meta.url));
const target = fileURLToPath(new URL("../src/realtime/events.generated.ts", import.meta.url));
const check = process.argv.includes("--check");

const index = JSON.parse(readFileSync(`${eventsDir}index.json`, "utf8")).events;
const typeName = (event) =>
	event
		.replace(/^infra:/, "")
		.split(/[.\-_]/)
		.map((p) => p[0].toUpperCase() + p.slice(1))
		.join("");

let types = "";
const schemas = {};
for (const [event, file] of Object.entries(index)) {
	const schema = JSON.parse(readFileSync(eventsDir + file, "utf8"));
	delete schema.$id;
	delete schema.examples;
	schemas[event] = schema;
	types += await compile({ ...schema, title: typeName(event) }, typeName(event), {
		bannerComment: "",
		additionalProperties: false,
		style: { useTabs: true, singleQuote: false, printWidth: 100 },
	});
}
const mapEntries = Object.keys(index)
	.map((event) => `\t"${event}": ${typeName(event)};`)
	.join("\n");

const output =
	"/* eslint-disable */\n// GENERATED from contracts/events by scripts/gen-events.mjs. Do not edit.\n\n" +
	types +
	`\n/** Event name -> payload type. */\nexport interface EventMap {\n${mapEntries}\n}\n\n` +
	`export type EventName = keyof EventMap;\n\n` +
	`/** JSON Schemas (2020-12) for runtime validation; identical to contracts/events. */\n` +
	`export const eventSchemas: Record<EventName, Record<string, unknown>> = ${JSON.stringify(schemas, null, "\t")};\n`;

if (check) {
	const current = existsSync(target) ? readFileSync(target, "utf8") : "";
	if (current !== output) {
		console.error(
			"[gen-events] src/realtime/events.generated.ts is out of date. Run `npm run gen:events` and commit."
		);
		process.exit(1);
	}
	console.log("[gen-events] events.generated.ts is up to date.");
} else {
	writeFileSync(target, output);
	console.log(`[gen-events] wrote ${target}`);
}
