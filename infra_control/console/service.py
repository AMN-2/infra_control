"""Console service (ADR 0007): WebSocket <-> SSH bridge for the web console.

    python -m infra_control.console.service            # 127.0.0.1:8012 by default

One session per ticket: the browser connects to `/console/ws?ticket=<t>`, the service redeems
the ticket from Redis (single use, 60 s), spawns the system `ssh` under a pseudo-terminal with
the session's CA-signed certificate, relays bytes both ways, records a transcript next to a
JSON sidecar (who, where, when, how many bytes, why it ended), deletes the ephemeral key, and
ends the session on idle or maximum duration. Control frames (JSON text) carry resizes.

No Frappe import: the ticket already carries everything, so the service runs as a plain
long-lived process next to the edge proxy. Dependencies: aiohttp and redis (bench env).
"""

from __future__ import annotations

import asyncio
import contextlib
import fcntl
import json
import logging
import os
import pty
import signal
import struct
import termios
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aiohttp import WSMsgType, web

HOST = os.environ.get("CONSOLE_HOST", "127.0.0.1")
PORT = int(os.environ.get("CONSOLE_PORT", "8012"))
TICKET_PREFIX = "infra:console:"
IDLE_SECONDS = int(os.environ.get("CONSOLE_IDLE_SECONDS", str(30 * 60)))
MAX_SECONDS = int(os.environ.get("CONSOLE_MAX_SECONDS", str(4 * 3600)))
MAX_INPUT_FRAME = 64 * 1024
log = logging.getLogger("infra_control.console")


def bench_root() -> Path:
	return Path(os.environ.get("BENCH", str(Path.home() / "frappe-bench")))


def redis_url() -> str:
	configured = os.environ.get("CONSOLE_REDIS")
	if configured:
		return configured
	cfg = json.loads((bench_root() / "sites" / "common_site_config.json").read_text())
	return str(cfg.get("redis_cache") or "redis://127.0.0.1:13000")


def ssh_argv(target: dict[str, Any]) -> list[str]:
	"""Pure: the ssh command for a ticket (certificate auth; host keys pinned on first contact)."""
	return [
		"ssh",
		"-tt",
		"-i",
		str(target["key_path"]),
		"-o",
		f"CertificateFile={target['cert_path']}",
		"-o",
		"IdentitiesOnly=yes",
		"-o",
		"StrictHostKeyChecking=accept-new",
		"-o",
		"ServerAliveInterval=30",
		"-o",
		"ConnectTimeout=15",
		"-p",
		str(int(target.get("port") or 22)),
		f"{target.get('user') or 'frappe'}@{target['host']}",
	]


def parse_control(text: str) -> dict[str, Any] | None:
	"""Pure: a JSON control frame (`{"t": "resize", "cols": 120, "rows": 40}` or input) or None."""
	try:
		data = json.loads(text)
	except ValueError:
		return None
	if not isinstance(data, dict) or data.get("t") not in ("resize", "input"):
		return None
	if data["t"] == "resize":
		try:
			cols, rows = int(data.get("cols", 0)), int(data.get("rows", 0))
		except (TypeError, ValueError):
			return None
		if not (10 <= cols <= 500 and 3 <= rows <= 200):
			return None
		return {"t": "resize", "cols": cols, "rows": rows}
	payload = data.get("data")
	return {"t": "input", "data": str(payload)} if isinstance(payload, str) else None


def set_winsize(fd: int, cols: int, rows: int) -> None:
	fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def redeem_ticket(ticket: str) -> dict[str, Any] | None:
	import redis

	if not ticket or len(ticket) > 128 or not all(c.isalnum() or c in "-_" for c in ticket):
		return None
	client = redis.from_url(redis_url())
	raw = client.getdel(TICKET_PREFIX + ticket)
	if not raw:
		return None
	data = json.loads(raw)
	return data if isinstance(data, dict) and data.get("host") and data.get("key_path") else None


def _now() -> str:
	return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class Transcript:
	"""Transcript (.log) and sidecar (.json) of one session, in the ticket's transcript_dir."""

	def __init__(self, target: dict[str, Any]) -> None:
		d = Path(target["transcript_dir"])
		d.mkdir(parents=True, exist_ok=True, mode=0o700)
		self.session = str(target.get("session") or time.strftime("%Y%m%d-%H%M%S"))
		self.log = d / f"{self.session}.log"
		self.meta_path = d / f"{self.session}.json"
		self.meta: dict[str, Any] = {
			"session": self.session,
			"server": target.get("server"),
			"hostname": target.get("hostname"),
			"host": target.get("host"),
			"user": target.get("user"),
			"by": target.get("by"),
			"identity": target.get("identity"),
			"started_at": _now(),
			"ended_at": None,
			"bytes": 0,
			"reason": None,
		}
		self.fd = os.open(self.log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
		os.write(
			self.fd,
			f"# console session {self.session}: {self.meta['by']} -> {self.meta['user']}@{self.meta['host']} ({self.meta['server']})\r\n".encode(),
		)
		self.flush()

	def write(self, data: bytes) -> None:
		os.write(self.fd, data)
		self.meta["bytes"] = int(self.meta["bytes"]) + len(data)

	def flush(self) -> None:
		tmp = self.meta_path.with_suffix(".json.tmp")
		tmp.write_text(json.dumps(self.meta))
		tmp.chmod(0o600)
		tmp.replace(self.meta_path)

	def close(self, reason: str) -> None:
		self.meta["ended_at"] = _now()
		self.meta["reason"] = reason
		os.write(self.fd, f"\r\n# session ended: {reason}\r\n".encode())
		os.close(self.fd)
		self.flush()


def _cleanup_keys(target: dict[str, Any]) -> None:
	for key in ("key_path", "cert_path"):
		with contextlib.suppress(OSError):
			os.unlink(str(target[key]))
	with contextlib.suppress(OSError):
		os.unlink(str(target["key_path"]) + ".pub")


async def handle_ws(request: web.Request) -> web.StreamResponse:
	ticket = request.query.get("ticket", "")
	target = await asyncio.get_running_loop().run_in_executor(None, redeem_ticket, ticket)
	if target is None:
		raise web.HTTPForbidden(text="invalid or expired ticket")
	ws = web.WebSocketResponse(heartbeat=25, max_msg_size=MAX_INPUT_FRAME)
	await ws.prepare(request)
	transcript = Transcript(target)

	pid, fd = pty.fork()
	if pid == 0:  # child: become ssh
		os.environ["TERM"] = "xterm-256color"
		# The argv is built by ssh_argv from the redeemed ticket (never from the browser).
		os.execvp("/usr/bin/ssh", ssh_argv(target))  # noqa: S606
	loop = asyncio.get_running_loop()
	started = time.monotonic()
	last_activity = started
	closed = asyncio.Event()
	reason = "client closed"
	sends: set[asyncio.Task[None]] = set()

	def on_pty_readable() -> None:
		nonlocal last_activity, reason
		try:
			data = os.read(fd, 65536)
		except OSError:
			data = b""
		if not data:
			loop.remove_reader(fd)
			reason = "ssh exited"
			closed.set()
			return
		last_activity = time.monotonic()
		transcript.write(data)
		task = loop.create_task(ws.send_bytes(data))
		sends.add(task)
		task.add_done_callback(sends.discard)

	loop.add_reader(fd, on_pty_readable)

	async def watchdog() -> None:
		nonlocal reason
		while not closed.is_set():
			await asyncio.sleep(5)
			now = time.monotonic()
			if now - last_activity > IDLE_SECONDS or now - started > MAX_SECONDS:
				reason = "idle timeout" if now - last_activity > IDLE_SECONDS else "maximum session length"
				with contextlib.suppress(Exception):
					await ws.send_bytes(f"\r\n[console closed: {reason}]\r\n".encode())
				closed.set()
				return

	async def reader() -> None:
		nonlocal last_activity
		async for msg in ws:
			if closed.is_set():
				break
			last_activity = time.monotonic()
			if msg.type == WSMsgType.BINARY:
				os.write(fd, msg.data)
			elif msg.type == WSMsgType.TEXT:
				control = parse_control(msg.data)
				if control is None:
					continue
				if control["t"] == "resize":
					with contextlib.suppress(OSError):
						set_winsize(fd, control["cols"], control["rows"])
				else:
					os.write(fd, control["data"].encode())
			elif msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
				break
		closed.set()

	watch = asyncio.ensure_future(watchdog())
	read = asyncio.ensure_future(reader())
	try:
		await closed.wait()
	finally:
		watch.cancel()
		read.cancel()
		with contextlib.suppress(Exception):
			loop.remove_reader(fd)
		with contextlib.suppress(ProcessLookupError):
			os.kill(pid, signal.SIGHUP)
		with contextlib.suppress(OSError):
			os.close(fd)
		with contextlib.suppress(ChildProcessError):
			os.waitpid(pid, os.WNOHANG)
		transcript.close(reason)
		_cleanup_keys(target)
		with contextlib.suppress(Exception):
			await ws.close()
	return ws


async def handle_health(_: web.Request) -> web.Response:
	return web.json_response({"ok": True, "idle_seconds": IDLE_SECONDS, "max_seconds": MAX_SECONDS})


def make_app() -> web.Application:
	app = web.Application()
	app.router.add_get("/console/ws", handle_ws)
	app.router.add_get("/console/health", handle_health)
	return app


def main() -> None:
	logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
	log.info("console service on http://%s:%s/console (redis %s)", HOST, PORT, redis_url())
	web.run_app(make_app(), host=HOST, port=PORT, print=None)


if __name__ == "__main__":
	main()
