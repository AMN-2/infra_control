// Edge proxy for the staging control plane (deploy/staging/README.md). No dependencies.
//
//   node edge.mjs
//
// Plays the part nginx plays in production:
//   /socket.io/*  (HTTP polling and WebSocket upgrades) -> Frappe's Socket.IO server
//   everything else                                    -> the staging gunicorn
// and adds X-Frappe-Site-Name so both pick the staging site whatever Host the browser used.
//
// Exposure is opt-in and narrow:
//   EDGE_HOST     bind address, default 127.0.0.1. A non-loopback address needs EDGE_PUBLIC=1.
//   EDGE_ALLOW    comma-separated client IPs allowed in; everyone else gets 403. Required when
//                 public: the staging site must never be open to the whole internet.
//   EDGE_TLS_CERT / EDGE_TLS_KEY  serve HTTPS (staging.sh makes a self-signed pair).
//
// Socket.IO: Frappe's realtime server rejects an Origin whose host differs from Host, and
// authenticates by calling back <Origin>/api/method/frappe.realtime.get_user_info. Host and Origin
// are therefore pinned to the staging gunicorn's internal address, which defaults the site.
import fs from "node:fs";
import http from "node:http";
import https from "node:https";
import net from "node:net";

const SITE = process.env.INFRA_SITE ?? "ops-staging.localhost";
const EDGE_HOST = process.env.EDGE_HOST ?? "127.0.0.1";
const EDGE_PORT = Number(process.env.EDGE_PORT ?? 8010);
const WEB = { host: process.env.WEB_HOST ?? "127.0.0.1", port: Number(process.env.WEB_PORT ?? 8011) };
const RT = { host: process.env.RT_HOST ?? "127.0.0.1", port: Number(process.env.RT_PORT ?? 9000) };
// Web console (ADR 0007): WebSocket upgrades under /console/ go to the console service.
const CONSOLE = { host: process.env.CONSOLE_HOST ?? "127.0.0.1", port: Number(process.env.CONSOLE_PORT ?? 8012) };
const WEB_ORIGIN = `http://${WEB.host}:${WEB.port}`;
const LOOPBACK = ["127.0.0.1", "::1", "localhost"];
const PUBLIC = !LOOPBACK.includes(EDGE_HOST);
const ALLOW = (process.env.EDGE_ALLOW ?? "")
	.split(",")
	.map((s) => s.trim())
	.filter(Boolean);
const ALLOW_ANY = ALLOW.includes("any");
const TLS =
	process.env.EDGE_TLS_CERT && process.env.EDGE_TLS_KEY
		? { cert: fs.readFileSync(process.env.EDGE_TLS_CERT), key: fs.readFileSync(process.env.EDGE_TLS_KEY) }
		: null;

if (PUBLIC && process.env.EDGE_PUBLIC !== "1") {
	console.error(`refusing to listen on ${EDGE_HOST}: set EDGE_PUBLIC=1 to expose the staging edge`);
	process.exit(2);
}
if (PUBLIC && ALLOW.length === 0) {
	console.error("refusing to listen publicly without EDGE_ALLOW (client IP allowlist)");
	process.exit(2);
}
if (PUBLIC && ALLOW_ANY && !TLS) { console.error("refusing EDGE_ALLOW=any without TLS"); process.exit(2); }
if (PUBLIC && !TLS) console.warn("WARNING: public edge without TLS; passwords travel in clear text");

const clientIp = (socket) => (socket.remoteAddress ?? "").replace(/^::ffff:/, "");
const allowed = (socket) => {
	const ip = clientIp(socket);
	return ALLOW_ANY || LOOPBACK.includes(ip) || ALLOW.length === 0 || ALLOW.includes(ip);
};
const isRealtime = (url = "") => url.startsWith("/socket.io");
const isConsole = (url = "") => url.startsWith("/console/");

function upstreamHeaders(req, realtime) {
	const headers = { ...req.headers, "x-frappe-site-name": SITE };
	headers["x-forwarded-for"] = clientIp(req.socket);
	headers["x-forwarded-proto"] = TLS ? "https" : "http";
	if (realtime) {
		headers.host = `${WEB.host}:${WEB.port}`;
		headers.origin = WEB_ORIGIN;
	}
	return headers;
}

function handler(req, res) {
	if (!allowed(req.socket)) {
		console.warn(`403 ${clientIp(req.socket)} ${req.method} ${req.url}`);
		res.writeHead(403, { "content-type": "text/plain" });
		res.end("forbidden\n");
		return;
	}
	const realtime = isRealtime(req.url);
	const target = realtime ? RT : WEB;
	const upstream = http.request(
		{ ...target, method: req.method, path: req.url, headers: upstreamHeaders(req, realtime) },
		(up) => {
			res.writeHead(up.statusCode ?? 502, up.headers);
			up.pipe(res);
		}
	);
	upstream.on("error", (err) => {
		if (!res.headersSent) res.writeHead(502, { "content-type": "text/plain" });
		res.end(`upstream ${realtime ? "realtime" : "web"} unavailable: ${err.code ?? err.message}\n`);
	});
	req.pipe(upstream);
}

const server = TLS ? https.createServer(TLS, handler) : http.createServer(handler);

// WebSocket upgrades (Socket.IO): replay the request line and rewritten headers, then splice.
server.on("upgrade", (req, client, head) => {
	if (!allowed(req.socket) || !(isRealtime(req.url) || isConsole(req.url))) {
		client.destroy();
		return;
	}
	const target = isConsole(req.url) ? CONSOLE : RT;
	const upstream = net.connect(target.port, target.host, () => {
		const headers = upstreamHeaders(req, true);
		const lines = [`${req.method} ${req.url} HTTP/1.1`];
		for (const [k, v] of Object.entries(headers)) {
			for (const value of Array.isArray(v) ? v : [v]) lines.push(`${k}: ${value}`);
		}
		upstream.write(lines.join("\r\n") + "\r\n\r\n");
		if (head?.length) upstream.write(head);
		upstream.pipe(client);
		client.pipe(upstream);
	});
	const close = () => {
		upstream.destroy();
		client.destroy();
	};
	upstream.on("error", close);
	client.on("error", close);
});

server.listen(EDGE_PORT, EDGE_HOST, () => {
	const scheme = TLS ? "https" : "http";
	const who = PUBLIC ? `allow ${ALLOW.join(", ")}` : "loopback only";
	console.log(`staging edge ${scheme}://${EDGE_HOST}:${EDGE_PORT} (${who}) -> web ${WEB_ORIGIN}, realtime ${RT.host}:${RT.port}, site ${SITE}`);
});
