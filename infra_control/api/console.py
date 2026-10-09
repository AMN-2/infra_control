"""console.* (ADR 0007): the web SSH console.

`ticket` issues a one-time ticket (60 s) that carries a fresh, CA-signed, minutes-long SSH
certificate for one server; the console service redeems it and bridges the browser's
terminal to `ssh`. `sessions` and `transcript` expose what happened in each session. Infra
Admin only; every ticket is an audit row.
"""

from __future__ import annotations

import json
import secrets
import time
from pathlib import Path
from typing import Any

import frappe

from infra_control.api import _serialize as ser
from infra_control.api import api, int_param, str_param
from infra_control.console import ca
from infra_control.core import audit
from infra_control.core.enums import Capability
from infra_control.core.errors import NotFound, NotSupported, ValidationError
from infra_control.core.permissions import INFRA_ADMIN
from infra_control.providers.registry import capabilities_for

TICKET_TTL_SECONDS = 60
TICKET_PREFIX = "infra:console:"
WS_PATH = "/console/ws"
TRANSCRIPT_TAIL = 200_000


def ticket_key(ticket: str) -> str:
	return TICKET_PREFIX + ticket


def transcript_dir() -> Path:
	d = Path(frappe.get_site_path("private", "infra_console"))
	d.mkdir(parents=True, exist_ok=True, mode=0o700)
	return d


def build_ticket(
	server: dict[str, Any], user: str, cert: ca.IssuedCertificate, session: str, transcripts: Path
) -> dict[str, Any]:
	"""Pure given its inputs: what the console service needs to open the session."""
	address = server.get("public_ip") or server.get("private_ip")
	if not address:
		raise ValidationError("Server has no IP address to connect to", {"server": server.get("name")})
	return {
		"session": session,
		"server": str(server["name"]),
		"hostname": str(server.get("hostname") or server["name"]),
		"host": str(address),
		"port": int(server.get("ssh_port") or 22),
		"user": str(server.get("ssh_user") or ca.PRINCIPAL),
		"by": user,
		"key_path": str(cert.key_path),
		"cert_path": str(cert.cert_path),
		"identity": cert.identity,
		"transcript_dir": str(transcripts),
	}


@api(methods=("POST",), role=INFRA_ADMIN)
def ticket(server: str | None = None) -> dict[str, Any]:
	name = str_param("server", server, required=True) or ""
	if not frappe.db.exists("Server", name):
		raise NotFound("Server", name)
	row: Any = frappe.db.get_value(
		"Server",
		name,
		["name", "hostname", "status", "provider", "public_ip", "private_ip", "ssh_user", "ssh_port"],
		as_dict=True,
	)
	if Capability.SSH not in capabilities_for(str(row["provider"])):
		raise NotSupported(Capability.SSH, str(row["provider"]))
	if str(row.get("status")) == "Archived":
		raise ValidationError("Archived servers have no console", {"server": name})
	user = str(frappe.session.user)
	session = time.strftime("%Y%m%d-%H%M%S", time.gmtime()) + "-" + secrets.token_hex(3)
	transcripts = transcript_dir()
	cert = ca.issue(user, name, transcripts / "keys")
	payload = build_ticket(dict(row), user, cert, session, transcripts)
	token = secrets.token_urlsafe(32)
	frappe.cache().set(ticket_key(token), json.dumps(payload), ex=TICKET_TTL_SECONDS)
	audit.record(
		"console.open",
		result="success",
		target_doctype="Server",
		target_name=name,
		params={"session": session},
	)
	return {
		"ticket": token,
		"path": WS_PATH,
		"expires_in": TICKET_TTL_SECONDS,
		"session": session,
		"server": payload["server"],
		"hostname": payload["hostname"],
		"user": payload["user"],
		"certificate_valid_for": cert.valid_for,
	}


def _sidecars(server: str | None) -> list[dict[str, Any]]:
	out: list[dict[str, Any]] = []
	for path in transcript_dir().glob("*.json"):
		try:
			meta = json.loads(path.read_text())
		except (OSError, ValueError):
			continue
		if server and meta.get("server") != server:
			continue
		out.append(meta)
	out.sort(key=lambda m: str(m.get("started_at") or ""), reverse=True)
	return out


def _session_row(meta: dict[str, Any]) -> dict[str, Any]:
	return {
		"session": str(meta.get("session") or ""),
		"server": str(meta.get("server") or ""),
		"hostname": str(meta.get("hostname") or ""),
		"by": str(meta.get("by") or ""),
		"started_at": ser.iso_utc(meta.get("started_at")),
		"ended_at": ser.iso_utc(meta.get("ended_at")),
		"bytes": int(meta.get("bytes") or 0),
		"status": "open" if not meta.get("ended_at") else "closed",
		"reason": (str(meta["reason"]) if meta.get("reason") else None),
	}


@api()
def sessions(server: str | None = None, limit: Any = None) -> dict[str, Any]:
	n = int_param("limit", limit, default=50, minimum=1, maximum=200)
	rows = _sidecars(str_param("server", server))[:n]
	return {"items": [_session_row(m) for m in rows]}


@api()
def transcript(session: str | None = None) -> dict[str, Any]:
	sid = str_param("session", session, required=True) or ""
	if not all(c.isalnum() or c in "-_" for c in sid):
		raise ValidationError("session has an invalid id", {"field": "session"})
	meta_path = transcript_dir() / f"{sid}.json"
	if not meta_path.exists():
		raise NotFound("Console session", sid)
	meta = json.loads(meta_path.read_text())
	log = transcript_dir() / f"{sid}.log"
	text = ""
	if log.exists():
		data = log.read_bytes()
		text = data[-TRANSCRIPT_TAIL:].decode("utf-8", errors="replace")
	return {
		**_session_row(meta),
		"transcript": text,
		"truncated": log.exists() and log.stat().st_size > TRANSCRIPT_TAIL,
	}
