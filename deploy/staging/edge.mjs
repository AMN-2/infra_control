// Edge proxy for the staging control plane (deploy/staging/README.md). No dependencies.
//
//   node edge.mjs
//
// Listens on EDGE_HOST:EDGE_PORT (default 127.0.0.1:8010, never a public address) and plays the
// part nginx plays in production:
//   /socket.io/*  (HTTP polling and WebSocket upgrades) -> Frappe's Socket.IO server
//   everything else                                    -> the staging gunicorn
// It adds X-Frappe-Site-Name so both servers pick the staging site regardless of the Host the
// browser used. For Socket.IO it also pins Host and Origin to this proxy's own address: Frappe's
// realtime server rejects an Origin whose host differs from Host, and authenticates the user by
// calling back <Origin>/api/method/frappe.realtime.get_user_info, which must reach this proxy
// even when the browser came in through a forwarded port with another number.
import http from "node:http";
import net from "node:net";

const SITE = process.env.INFRA_SITE ?? "ops-staging.localhost";
const EDGE_HOST = process.env.EDGE_HOST ?? "127.0.0.1";
const EDGE_PORT = Number(process.env.EDGE_PORT ?? 8010);
const WEB = { host: process.env.WEB_HOST ?? "127.0.0.1", port: Number(process.env.WEB_PORT ?? 8011) };
const RT = { host: process.env.RT_HOST ?? "127.0.0.1", port: Number(process.env.RT_PORT ?? 9000) };
const SELF = `${EDGE_HOST}:${EDGE_PORT}`;

if (!["127.0.0.1", "::1", "localhost"].includes(EDGE_HOST)) {
	console.error(`refusing to listen on ${EDGE_HOST}: the staging edge is local-only`);
	process.exit(2);
}

const isRealtime = (url = "") => url.startsWith("/socket.io");

function upstreamHeaders(req, realtime) {
	const headers = { ...req.headers, "x-frappe-site-name": SITE };
	headers["x-forwarded-for"] = req.socket.remoteAddress ?? "";
	headers["x-forwarded-proto"] = "http";
	if (realtime) {
		headers.host = SELF;
		headers.origin = `http://${SELF}`;
	}
	return headers;
}

const server = http.createServer((req, res) => {
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
});

// WebSocket upgrades (Socket.IO): replay the request line and rewritten headers, then splice.
server.on("upgrade", (req, client, head) => {
	if (!isRealtime(req.url)) {
		client.destroy();
		return;
	}
	const upstream = net.connect(RT.port, RT.host, () => {
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
	console.log(`staging edge on http://${SELF} -> web ${WEB.host}:${WEB.port}, realtime ${RT.host}:${RT.port}, site ${SITE}`);
});
