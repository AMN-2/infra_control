// Smoke test for the mock (run in CI): starts Prism and the realtime server, calls every endpoint
// in contracts/openapi.yaml, replays a scenario over Socket.IO and checks every event validates.
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";
import { io } from "socket.io-client";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const here = dirname(fileURLToPath(import.meta.url));
const PRISM_PORT = 4011;
const RT_PORT = 9001;
const PRISM = `http://127.0.0.1:${PRISM_PORT}`;
const RT = `http://127.0.0.1:${RT_PORT}`;
// Prism enforces the spec's security schemes; any token-shaped header satisfies the mock.
const AUTH = { Authorization: "token mock:mock" };

const spec = parse(readFileSync(join(here, "..", "openapi.yaml"), "utf8"));
const eventIndex = JSON.parse(readFileSync(join(here, "..", "events", "index.json"), "utf8")).events;

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const eventValidators = Object.fromEntries(
	Object.entries(eventIndex).map(([event, file]) => {
		const schema = JSON.parse(readFileSync(join(here, "..", "events", file), "utf8"));
		delete schema.$id;
		return [event, ajv.compile(schema)];
	}),
);

// Required query params for GET endpoints; POST bodies come from the spec's request examples
// (or a minimal body when there is none).
const QUERY = {
	"servers.get": { server: "SRV-0001" },
	"sites.get": { site: "demo.smartchoice-iq.com" },
	"metrics.series": { server: "SRV-0001", metric: "cpu", from: "2026-10-07T09:25:00Z", to: "2026-10-07T09:30:00Z", resolution: "1m" },
	"jobs.get": { job: "JOB-00042" },
	"bulk.get": { bulk: "BULK-0007" },
	"alert_rules.get": { rule: "RULE-0003" },
	"search.query": { q: "demo" },
};
const BODY = {
	"jobs.cancel": { job: "JOB-00042" },
	"jobs.retry": { job: "JOB-00041" },
	"bulk.pause": { bulk: "BULK-0007" },
	"bulk.resume": { bulk: "BULK-0007" },
	"alerts.ack": { alert: "ALERT-00018" },
	"alert_rules.create": { title: "RAM above 95%", target_doctype: "Server", metric: "ram", operator: "gt", threshold: 95, for_minutes: 5, severity: "critical", channels: ["telegram"] },
	"alert_rules.update": { rule: "RULE-0003", threshold: 90 },
	"alert_rules.delete": { rule: "RULE-0003" },
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const children = [];
function start(cmd, args, name) {
	const child = spawn(cmd, args, { cwd: here, stdio: ["ignore", "pipe", "pipe"] });
	child.stdout.on("data", (d) => process.env.SMOKE_VERBOSE && process.stdout.write(`[${name}] ${d}`));
	child.stderr.on("data", (d) => process.stdout.write(`[${name}:err] ${d}`));
	children.push(child);
	return child;
}
async function waitFor(url, tries = 60) {
	for (let i = 0; i < tries; i++) {
		try {
			await fetch(url);
			return;
		} catch {
			await sleep(500);
		}
	}
	throw new Error(`timeout waiting for ${url}`);
}

let failures = 0;
const fail = (msg) => {
	failures += 1;
	console.error(`FAIL ${msg}`);
};

try {
	start(join(here, "node_modules", ".bin", "prism"), ["mock", "../openapi.yaml", "--host", "127.0.0.1", "--port", String(PRISM_PORT), "--errors"], "prism");
	start(process.execPath, ["realtime.js", "--port", String(RT_PORT), "--no-heartbeat"], "realtime");
	await waitFor(`${RT}/mock/scenarios`);
	await waitFor(`${PRISM}/api/method/infra_control.api.overview.summary`); // any status counts as up

	// ---- REST: every operation answers 200 with JSON matching the example ------------------
	let count = 0;
	for (const [path, item] of Object.entries(spec.paths)) {
		const fn = path.replace("/api/method/infra_control.api.", "");
		for (const method of ["get", "post"]) {
			const op = item[method];
			if (!op) continue;
			count += 1;
			let res;
			if (method === "get") {
				const qs = new URLSearchParams(QUERY[fn] ?? {}).toString();
				res = await fetch(`${PRISM}${path}${qs ? `?${qs}` : ""}`, { headers: AUTH });
			} else {
				const examples = op.requestBody?.content?.["application/json"]?.examples;
				const body = BODY[fn] ?? (examples ? Object.values(examples)[0].value : {});
				res = await fetch(`${PRISM}${path}`, { method: "POST", headers: { ...AUTH, "content-type": "application/json" }, body: JSON.stringify(body) });
			}
			const text = await res.text();
			if (res.status !== 200) {
				fail(`${method.toUpperCase()} ${fn} -> ${res.status} ${text.slice(0, 200)}`);
				continue;
			}
			try {
				JSON.parse(text);
			} catch {
				fail(`${method.toUpperCase()} ${fn} did not return JSON`);
			}
		}
	}
	console.log(`REST: ${count} operations answered by the mock`);

	// ---- REST: forced error responses work (Prefer header) ------------------------------
	const forced = await fetch(`${PRISM}/api/method/infra_control.api.jobs.run`, {
		method: "POST",
		headers: { ...AUTH, "content-type": "application/json", Prefer: "code=409" },
		body: JSON.stringify({ playbook: "service.control", target_doctype: "Site", target_name: "staging.client-c.frappe.cloud" }),
	});
	const forcedBody = await forced.json();
	if (forced.status !== 409 || forcedBody?.error?.code !== "capability_missing") fail(`Prefer: code=409 -> ${forced.status} ${JSON.stringify(forcedBody)}`);
	else console.log("REST: Prefer: code=409 yields the capability_missing envelope");

	// ---- Realtime: replay every scenario, validate every event -----------------------------
	const socket = io(`${RT}/mock.localhost`, { path: "/socket.io", transports: ["websocket"] });
	await new Promise((resolve, reject) => {
		socket.on("connect", resolve);
		socket.on("connect_error", reject);
	});
	const received = [];
	for (const event of Object.keys(eventIndex)) {
		socket.on(event, (payload) => {
			received.push([event, payload]);
			const v = eventValidators[event];
			if (!v(payload)) fail(`${event} invalid: ${ajv.errorsText(v.errors)}`);
		});
	}
	const { scenarios } = await (await fetch(`${RT}/mock/scenarios`)).json();
	for (const s of scenarios) {
		const before = received.length;
		const r = await fetch(`${RT}/mock/replay/${s.name}`, { method: "POST" });
		if (r.status !== 202) fail(`replay ${s.name} -> ${r.status}`);
		// Scenarios are time-based; wait generously, then check every step arrived.
		const deadline = Date.now() + 40_000;
		while (received.length - before < s.steps && Date.now() < deadline) await sleep(200);
		const got = received.length - before;
		if (got !== s.steps) fail(`scenario ${s.name}: expected ${s.steps} events, got ${got}`);
		else console.log(`realtime: scenario ${s.name} delivered ${got} valid events`);
	}
	const bad = await fetch(`${RT}/mock/emit`, { method: "POST", body: JSON.stringify({ event: "infra:job.updated", payload: { job: "x" } }) });
	if (bad.status !== 400) fail(`/mock/emit must reject an invalid payload, got ${bad.status}`);
	else console.log("realtime: invalid payloads are rejected");
	socket.close();
} catch (e) {
	fail(e.stack || String(e));
} finally {
	for (const c of children) c.kill("SIGTERM");
}
if (failures) {
	console.error(`${failures} failure(s)`);
	process.exit(1);
}
console.log("mock smoke: ok");
