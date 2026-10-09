"""ADR 0007: the web console's pure parts (CA signing args, identities, control frames, ssh argv)
and the ticket/sessions/transcript API on the fake Frappe with a stubbed certificate issuer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fake_frappe import FakeFrappe
from test_api import call, validate

import infra_control.api as api_pkg
from infra_control.api import _serialize, console
from infra_control.console import ca, service
from infra_control.core import audit, permissions


def test_sign_args_and_identity() -> None:
	args = ca.sign_args(Path("/ca/ca"), Path("/w/k.pub"), "console:u:SRV-1:20261009T080000Z", 42)
	assert args[:2] == ["/usr/bin/ssh-keygen", "-q"]
	assert args[args.index("-I") + 1] == "console:u:SRV-1:20261009T080000Z"
	assert args[args.index("-n") + 1] == "frappe" and args[args.index("-V") + 1] == "+10m"
	assert args[args.index("-z") + 1] == "42" and args[-1] == "/w/k.pub"
	assert (
		ca.identity_for("ameen@x", "SRV-0003", now=1_000_000.0) == "console:ameen@x:SRV-0003:19700112T134640Z"
	)


def test_ca_is_created_once_and_issues_short_lived_certificates(tmp_path: Path) -> None:
	key = ca.ensure_ca(tmp_path / "ca")
	assert key.exists() and (key.stat().st_mode & 0o777) == 0o600
	pub = ca.public_key(tmp_path / "ca")
	assert pub.startswith("ssh-ed25519 ")
	assert ca.ensure_ca(tmp_path / "ca") == key  # idempotent
	issued = ca.issue("ameen@x", "SRV-0003", tmp_path / "keys", directory=tmp_path / "ca")
	assert issued.key_path.exists() and issued.cert_path.exists()
	assert (issued.key_path.stat().st_mode & 0o777) == 0o600
	assert issued.identity.startswith("console:ameen@x:SRV-0003:")
	import subprocess

	info = subprocess.run(
		["/usr/bin/ssh-keygen", "-L", "-f", str(issued.cert_path)], capture_output=True, text=True, check=True
	).stdout
	assert "frappe" in info and issued.identity in info and "user certificate" in info


def test_control_frames_and_ssh_argv() -> None:
	assert service.parse_control('{"t":"resize","cols":120,"rows":40}') == {
		"t": "resize",
		"cols": 120,
		"rows": 40,
	}
	assert service.parse_control('{"t":"resize","cols":5,"rows":40}') is None
	assert service.parse_control('{"t":"input","data":"ls\\n"}') == {"t": "input", "data": "ls\n"}
	assert service.parse_control("not json") is None and service.parse_control('{"t":"exec"}') is None
	argv = service.ssh_argv(
		{"host": "10.0.0.5", "port": 2222, "user": "frappe", "key_path": "/k", "cert_path": "/k-cert.pub"}
	)
	assert argv[-1] == "frappe@10.0.0.5" and "-p" in argv and argv[argv.index("-p") + 1] == "2222"
	assert "CertificateFile=/k-cert.pub" in argv and "IdentitiesOnly=yes" in argv


@pytest.fixture
def ff(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FakeFrappe:
	f = FakeFrappe()
	for module in (api_pkg, _serialize, console, audit, permissions):
		monkeypatch.setattr(module, "frappe", f)
	monkeypatch.setattr(_serialize, "system_timezone", lambda: "UTC")
	monkeypatch.setattr(audit, "now_datetime", f.now)
	monkeypatch.setattr(console, "transcript_dir", lambda: tmp_path)
	monkeypatch.setattr(
		console.ca,
		"issue",
		lambda user, server, work_dir, **kw: ca.IssuedCertificate(
			key_path=work_dir / "k",
			cert_path=work_dir / "k-cert.pub",
			identity=f"console:{user}:{server}:x",
			serial=7,
			valid_for="+10m",
		),
	)
	f.add(
		"Server",
		name="SRV-0003",
		hostname="gate-02.fra1",
		provider_account="DO",
		provider="digitalocean",
		status="Active",
		public_ip="46.101.242.252",
	)
	f.add(
		"Server",
		name="SRV-FC",
		hostname="fc",
		provider_account="FC",
		provider="frappe_cloud",
		status="Active",
	)
	return f


def test_ticket_is_single_use_and_carries_no_secrets(ff: FakeFrappe, tmp_path: Path) -> None:
	status, body = call(console.ticket, server="SRV-0003")
	assert status == 200
	validate("console.ticket", body)
	assert (
		body["user"] == "frappe" and body["certificate_valid_for"] == "+10m" and "key" not in json.dumps(body)
	)
	stored = json.loads(ff.cache().get(console.ticket_key(body["ticket"])) or "{}")
	assert (
		stored["host"] == "46.101.242.252"
		and stored["key_path"].endswith("/k")
		and stored["by"] == ff.session.user
	)
	assert [a.get("action") for a in ff.store["Infra Audit Log"].values()] == ["console.open"]
	status, body = call(console.ticket, server="SRV-FC")
	assert status == 409 and body["error"]["code"] == "capability_missing"
	status, body = call(console.ticket, server="NOPE")
	assert status == 404


def test_sessions_and_transcript_read_the_service_sidecars(ff: FakeFrappe, tmp_path: Path) -> None:
	meta: dict[str, Any] = {
		"session": "20261009-081500-a1b2c3",
		"server": "SRV-0003",
		"hostname": "gate-02.fra1",
		"by": "ameen@x",
		"started_at": "2026-10-09 08:15:00",
		"ended_at": "2026-10-09 08:21:40",
		"bytes": 42,
		"reason": "client closed",
	}
	(tmp_path / "20261009-081500-a1b2c3.json").write_text(json.dumps(meta))
	(tmp_path / "20261009-081500-a1b2c3.log").write_bytes(
		b"frappe@gate-02:~$ bench version\r\nfrappe 15.98.1\r\n"
	)
	(tmp_path / "20261009-090000-ffffff.json").write_text(
		json.dumps(
			{
				**meta,
				"session": "20261009-090000-ffffff",
				"ended_at": None,
				"reason": None,
				"started_at": "2026-10-09 09:00:00",
			}
		)
	)
	status, body = call(console.sessions, server="SRV-0003")
	assert status == 200
	validate("console.sessions", body)
	assert [s["session"] for s in body["items"]] == ["20261009-090000-ffffff", "20261009-081500-a1b2c3"]
	assert body["items"][0]["status"] == "open" and body["items"][1]["status"] == "closed"
	status, body = call(console.transcript, session="20261009-081500-a1b2c3")
	validate("console.transcript", body)
	assert "bench version" in body["transcript"] and body["truncated"] is False
	status, body = call(console.transcript, session="../etc/passwd")
	assert status == 400
	status, body = call(console.transcript, session="nope")
	assert status == 404
