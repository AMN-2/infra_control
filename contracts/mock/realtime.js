// Socket.IO replay server that mimics Frappe's realtime transport (plan section 6.3).
//
//   node realtime.js [--port 9000] [--no-heartbeat] [--loop <scenario>]
//
// Mirrors Frappe: any namespace is accepted (the site name), path /socket.io, event name is the
// Socket.IO event, payload is the message object. Every payload is validated against
// contracts/events/*.schema.json before it is emitted, so the mock can never teach the UI a shape
// the backend will not send.
//
// Control API (plain HTTP on the same port):
//   GET  /mock/scenarios            list scenarios
//   POST /mock/replay/<scenario>    replay one scenario to every connected client
//   POST /mock/emit                 body {event, payload}: emit one validated event
import { createServer } from "node:http";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { Server } from "socket.io";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const here = dirname(fileURLToPath(import.meta.url));
const eventsDir = join(here, "..", "events");
const scenariosDir = join(here, "scenarios");

const args = process.argv.slice(2);
const flag = (name, fallback) => {
	const i = args.indexOf(name);
	return i === -1 ? fallback : args[i + 1];
};
const PORT = Number(process.env.MOCK_REALTIME_PORT || flag("--port", 9000));
const HEARTBEAT = !args.includes("--no-heartbeat");
const LOOP = flag("--loop", null);
const HEARTBEAT_EVERY_MS = Number(process.env.MOCK_HEARTBEAT_MS || 10_000);

// ---------------------------------------------------------------------------
// Event schema validation
// ---------------------------------------------------------------------------
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const index = JSON.parse(readFileSync(join(eventsDir, "index.json"), "utf8")).events;
const validators = Object.fromEntries(
	Object.entries(index).map(([event, file]) => {
		const schema = JSON.parse(readFileSync(join(eventsDir, file), "utf8"));
		delete schema.$id; // avoid ajv id collisions when run twice
		return [event, ajv.compile(schema)];
	}),
);

export function validate(event, payload) {
	const v = validators[event];
	if (!v) throw new Error(`unknown event ${event}; known: ${Object.keys(validators).join(", ")}`);
	if (!v(payload)) throw new Error(`${event} payload invalid: ${ajv.errorsText(v.errors)}`);
}

// ---------------------------------------------------------------------------
// Scenarios: { name, description, steps: [{ delay_ms, event, payload }] }
// ---------------------------------------------------------------------------
export function loadScenarios(dir = scenariosDir) {
	const scenarios = {};
	for (const file of readdirSync(dir).filter((f) => f.endsWith(".json")).sort()) {
		const s = JSON.parse(readFileSync(join(dir, file), "utf8"));
		s.steps.forEach((step, i) => {
			try {
				validate(step.event, step.payload);
			} catch (e) {
				throw new Error(`${file} step ${i}: ${e.message}`);
			}
		});
		scenarios[s.name] = s;
	}
	return scenarios;
}

const scenarios = loadScenarios();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------------------------------------------------------------------------
// Server
// ---------------------------------------------------------------------------
const http = createServer(async (req, res) => {
	const json = (code, body) => {
		res.writeHead(code, { "content-type": "application/json", "access-control-allow-origin": "*" });
		res.end(JSON.stringify(body));
	};
	if (req.method === "OPTIONS") {
		res.writeHead(204, {
			"access-control-allow-origin": "*",
			"access-control-allow-methods": "GET,POST,OPTIONS",
			"access-control-allow-headers": "content-type",
		});
		return res.end();
	}
	if (req.method === "GET" && req.url === "/mock/scenarios") {
		return json(200, {
			scenarios: Object.values(scenarios).map((s) => ({ name: s.name, description: s.description, steps: s.steps.length })),
		});
	}
	const m = req.url.match(/^\/mock\/replay\/([\w.-]+)$/);
	if (req.method === "POST" && m) {
		const s = scenarios[m[1]];
		if (!s) return json(404, { error: { code: "not_found", message: `no scenario ${m[1]}`, details: {} } });
		replay(s).catch((e) => console.error(e));
		return json(202, { replaying: s.name, steps: s.steps.length });
	}
	if (req.method === "POST" && req.url === "/mock/emit") {
		let body = "";
		for await (const chunk of req) body += chunk;
		try {
			const { event, payload } = JSON.parse(body);
			emit(event, payload);
			return json(202, { emitted: event });
		} catch (e) {
			return json(400, { error: { code: "validation_error", message: String(e.message), details: {} } });
		}
	}
	json(404, { error: { code: "not_found", message: "use /mock/scenarios, /mock/replay/<name> or /mock/emit", details: {} } });
});

const io = new Server(http, { cors: { origin: true, credentials: true }, path: "/socket.io" });
const realtime = io.of(/^\/.*$/); // any site name, like Frappe

realtime.on("connection", (socket) => {
	console.log(`[realtime] client connected ns=${socket.nsp.name} id=${socket.id}`);
	socket.on("ping", () => socket.emit("pong"));
	socket.on("disconnect", () => console.log(`[realtime] client left ${socket.id}`));
});

function emit(event, payload) {
	validate(event, payload);
	realtime.emit(event, payload);
	console.log(`[realtime] ${event} ${JSON.stringify(payload).slice(0, 120)}`);
}

async function replay(scenario) {
	console.log(`[realtime] replaying ${scenario.name} (${scenario.steps.length} steps)`);
	for (const step of scenario.steps) {
		await sleep(step.delay_ms ?? 500);
		emit(step.event, step.payload);
	}
	console.log(`[realtime] ${scenario.name} done`);
}

let tick = 0;
function heartbeat() {
	tick += 1;
	const ts = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
	const wobble = (base, amp) => Math.round((base + Math.sin(tick / 3) * amp) * 10) / 10;
	emit("infra:server.heartbeat", { server: "SRV-0001", status: "Active", cpu: wobble(23, 8), ram: wobble(61, 3), disk: 54.0, ts });
	emit("infra:server.heartbeat", { server: "SRV-0002", status: "Degraded", cpu: wobble(78, 12), ram: wobble(90, 4), disk: 88.4, ts });
}

if (process.env.NODE_ENV !== "test" && import.meta.url === `file://${process.argv[1]}`) {
	http.listen(PORT, () => {
		console.log(`[realtime] mock Socket.IO on ws://localhost:${PORT}/<site>  (path /socket.io)`);
		console.log(`[realtime] scenarios: ${Object.keys(scenarios).join(", ")}`);
		console.log(`[realtime] replay with: curl -X POST http://localhost:${PORT}/mock/replay/<scenario>`);
		if (HEARTBEAT) setInterval(heartbeat, HEARTBEAT_EVERY_MS);
		if (LOOP) {
			const s = scenarios[LOOP];
			if (!s) throw new Error(`unknown scenario ${LOOP}`);
			(async () => {
				for (;;) {
					await replay(s);
					await sleep(3000);
				}
			})();
		}
	});
}
