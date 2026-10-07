"""A1.4: every read endpoint answers in the contract's shape (validated against openapi.yaml)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from fake_frappe import FakeFrappe
from jsonschema import Draft202012Validator, FormatChecker

import infra_control.api as api_pkg
from infra_control.api import (
	_inventory_helpers,
	_pagination,
	_serialize,
	benches,
	inventory,
	jobs,
	overview,
	playbooks,
	servers,
	sites,
)
from infra_control.core import audit, permissions
from infra_control.install import PLAYBOOKS
from infra_control.job_engine import engine, realtime
from infra_control.providers import registry

REPO = Path(__file__).resolve().parents[2]
with (REPO / "contracts" / "openapi.yaml").open() as fh:
	SPEC = yaml.safe_load(fh)
BASE = "/api/method/infra_control.api."


def validate(fn: str, payload: dict[str, Any], status: str = "200") -> None:
	op = next(iter(v for k, v in SPEC["paths"][BASE + fn].items() if k in ("get", "post")))
	resp = op["responses"][status]
	if "$ref" in resp:
		resp = SPEC["components"]["responses"][resp["$ref"].rsplit("/", 1)[1]]
	schema = resp["content"]["application/json"]["schema"]
	if status == "200":
		assert not (isinstance(payload.get("error"), dict) and "code" in payload["error"]), (
			f"{fn}: {payload['error']}"
		)
	wrapped = {"$id": "urn:openapi", "components": SPEC["components"], "allOf": [schema]}
	errors = sorted(
		Draft202012Validator(wrapped, format_checker=FormatChecker()).iter_errors(
			json.loads(json.dumps(payload, default=str))
		),
		key=lambda e: list(e.path),
	)
	assert not errors, f"{fn}: " + "; ".join(f"{list(e.path)}: {e.message}" for e in errors[:5])


@pytest.fixture
def ff(monkeypatch: pytest.MonkeyPatch) -> FakeFrappe:
	f = FakeFrappe()
	for module in (
		api_pkg,
		_inventory_helpers,
		_pagination,
		_serialize,
		benches,
		inventory,
		jobs,
		overview,
		playbooks,
		servers,
		sites,
		engine,
		realtime,
		audit,
		permissions,
		registry,
	):
		monkeypatch.setattr(module, "frappe", f)
	monkeypatch.setattr(_serialize, "system_timezone", lambda: "UTC")
	monkeypatch.setattr(overview, "now_datetime", f.now)
	monkeypatch.setattr(inventory, "now_datetime", f.now)
	monkeypatch.setattr(engine, "now_datetime", f.now)
	monkeypatch.setattr(audit, "now_datetime", f.now)
	monkeypatch.setattr(engine, "sleep", lambda s: None)
	f.conf["infra_use_dummy_provider"] = 1
	for spec in PLAYBOOKS:
		f.add(
			"Playbook",
			name=spec["key"],
			key=spec["key"],
			title=spec["title"],
			description=spec["description"],
			target_doctype=str(spec["target_doctype"]),
			creates=spec.get("creates") or "",
			risk=str(spec["risk"]),
			required_capability=str(spec["required_capability"]) if spec.get("required_capability") else "",
			ansible_file=spec.get("ansible_file") or "",
			provider_method=spec.get("provider_method") or "",
			params_schema=json.dumps(
				spec.get("params_schema")
				or {"type": "object", "additionalProperties": False, "properties": {}}
			),
			enabled=1,
		)
	f.add(
		"Provider Account",
		name="DO-STAGING",
		label="DigitalOcean (staging)",
		provider="digitalocean",
		api_token="dop_v1_" + "1" * 64,
		is_staging=1,
		enabled=1,
	)
	f.add(
		"Provider Account",
		name="FC-STAGING",
		label="Frappe Cloud (staging)",
		provider="frappe_cloud",
		api_token="t",
		team="team",
		is_staging=1,
		enabled=1,
	)
	srv = f.add(
		"Server",
		name="SRV-0001",
		hostname="app-01.fra1",
		provider_account="DO-STAGING",
		provider="digitalocean",
		provider_ref="412345678",
		public_ip="164.92.10.11",
		private_ip="10.114.0.2",
		role="all",
		region="fra1",
		size="s-4vcpu-8gb",
		status="Active",
		last_heartbeat=f.now(),
	)
	f.add_child(srv, "Server Tag", tag="staging")
	f.add(
		"Server",
		name="SRV-0002",
		hostname="app-02.fra1",
		provider_account="DO-STAGING",
		provider="digitalocean",
		provider_ref="412345679",
		role="all",
		region="fra1",
		size="s-2vcpu-4gb",
		status="Degraded",
	)
	b = f.add(
		"Bench",
		name="BENCH-0001",
		title="v15-prod",
		provider_account="DO-STAGING",
		provider="digitalocean",
		provider_ref="SRV-0001:/home/frappe/v15-prod",
		server="SRV-0001",
		path="/home/frappe/v15-prod",
		frappe_version="15.98.1",
	)
	f.add_child(b, "Bench App", app="frappe", version="15.98.1", branch="version-15")
	f.add(
		"Bench",
		name="BENCH-FC-01",
		title="fc-bench-01",
		provider_account="FC-STAGING",
		provider="frappe_cloud",
		provider_ref="bench-abc",
		server=None,
		path=None,
		frappe_version="15.98.1",
	)
	s = f.add(
		"Site",
		name="demo.smartchoice-iq.com",
		domain="demo.smartchoice-iq.com",
		bench="BENCH-0001",
		server="SRV-0001",
		provider_account="DO-STAGING",
		provider="digitalocean",
		provider_ref="x",
		status="Active",
		db_size_mb=812.4,
		ssl_expiry=f.now() + timedelta(days=60),
	)
	f.add_child(s, "Site Domain", domain="demo.smartchoice.iq")
	f.add(
		"Site",
		name="erp.client-a.iq",
		domain="erp.client-a.iq",
		bench="BENCH-0001",
		server="SRV-0001",
		provider_account="DO-STAGING",
		provider="digitalocean",
		provider_ref="y",
		status="Maintenance",
	)
	f.add(
		"Site",
		name="staging.client-c.frappe.cloud",
		domain="staging.client-c.frappe.cloud",
		bench="BENCH-FC-01",
		server=None,
		provider_account="FC-STAGING",
		provider="frappe_cloud",
		provider_ref="z",
		status="Active",
		plan="USD 25",
	)
	f.add(
		"Backup",
		name="BKP-000311",
		site="demo.smartchoice-iq.com",
		kind="db",
		location="spaces://b/x.sql.gz",
		size_mb=96.3,
		created_at=f.now(),
		restore_test_result="ok",
		last_restore_test=f.now(),
	)
	f.add(
		"Server Metric",
		server="SRV-0001",
		ts=f.now(),
		resolution="1m",
		cpu=23.5,
		ram=61.2,
		disk=54.0,
		load1=0.82,
		queue_backlog=3,
	)
	f.add(
		"Alert Rule",
		name="RULE-0003",
		title="Disk above 85%",
		kind="metric",
		severity="warning",
		target_doctype="Server",
		metric="disk",
		operator="gt",
		threshold=85,
		for_minutes=10,
		enabled=1,
		builtin=0,
	)
	f.add(
		"Alert",
		name="ALERT-00017",
		rule="RULE-0003",
		rule_title="Disk above 85%",
		kind="metric",
		severity="warning",
		status="firing",
		target_doctype="Server",
		target_name="SRV-0002",
		metric="disk",
		value=88.4,
		message="Disk usage 88.4%",
		fired_at=f.now(),
	)
	return f


def call(fn: Any, **kwargs: Any) -> tuple[int, dict[str, Any]]:
	"""Invoke the handler behind a whitelisted endpoint and return (status, body)."""
	fn.handler(**kwargs)
	ff = api_pkg.frappe
	body = dict(ff.local.response)
	status = body.pop("http_status_code")
	ff.local.response = type(ff.local.response)({"docs": []})
	return status, body


# --- envelope and conventions --------------------------------------------------------------
def test_success_body_is_top_level_without_frappe_keys(ff: FakeFrappe) -> None:
	status, body = call(servers.list)
	assert status == 200 and "message" not in body and "docs" not in body
	validate("servers.list", body)


def test_errors_use_the_envelope_and_status(ff: FakeFrappe) -> None:
	status, body = call(servers.get, server="SRV-9999")
	assert status == 404 and body == {
		"error": {
			"code": "not_found",
			"message": "Server SRV-9999 not found",
			"details": {"doctype": "Server", "name": "SRV-9999"},
		}
	}
	validate("servers.get", body, "404")
	status, body = call(servers.list, status="Broken")
	assert (
		status == 400
		and body["error"]["code"] == "validation_error"
		and body["error"]["details"] == {"field": "status"}
	)
	status, body = call(servers.list, limit="500")
	assert status == 400
	status, body = call(jobs.list, cursor="not-a-cursor")
	assert status == 400 and body["error"]["code"] == "invalid_cursor"


def test_role_denied_is_403_envelope(ff: FakeFrappe) -> None:
	ff.session.user = "nobody@x"
	ff.roles["nobody@x"] = ("System Manager",)
	status, body = call(overview.summary)
	assert status == 403 and body["error"]["code"] == "permission_denied"
	assert body["error"]["details"] == {"role": "no Infra role", "required": "Infra Viewer"}
	validate("overview.summary", body, "403")
	ff.roles["nobody@x"] = ("Infra Viewer",)
	status, body = call(
		jobs.run, playbook="site.backup", target_doctype="Site", target_name="demo.smartchoice-iq.com"
	)
	assert status == 403 and body["error"]["details"]["required"] == "Infra Operator"


def test_unexpected_exception_is_internal_error_and_logged(
	ff: FakeFrappe, monkeypatch: pytest.MonkeyPatch
) -> None:
	monkeypatch.setattr(servers, "_enrich", lambda rows: 1 / 0)
	status, body = call(servers.list)
	assert status == 500 and body["error"]["code"] == "internal_error" and ff.errors and ff.rollbacks == 1


# --- endpoints -----------------------------------------------------------------------------
def test_servers_list_and_get(ff: FakeFrappe) -> None:
	status, body = call(servers.list, status="Active", role="all", region="fra1")
	validate("servers.list", body)
	assert [i["name"] for i in body["items"]] == ["SRV-0001"]
	item = body["items"][0]
	assert (
		item["hostname"] == "app-01.fra1"
		and item["tags"] == ["staging"]
		and item["bench_count"] == 1
		and item["site_count"] == 2
	)
	assert item["capabilities"] == sorted(
		["site", "bench", "server", "ssh", "snapshot", "service_control", "metrics", "custom_playbook"]
	)
	assert item["last_heartbeat"].endswith("Z")
	ff.cache_client.set("infra:lock:server:SRV-0001", "JOB-RUN")
	running = ff.add(
		"Infra Job",
		playbook="site.backup",
		target_doctype="Site",
		target_name="erp.client-a.iq",
		status="Running",
		lock_key="infra:lock:server:SRV-0001",
		triggered_by="x",
	)
	status, body = call(servers.get, server="SRV-0001")
	ff.cache_client.set("infra:lock:server:SRV-0001", running.name)
	validate("servers.get", body)
	assert body["benches"][0]["apps"] == [{"app": "frappe", "version": "15.98.1", "branch": "version-15"}]
	assert body["latest_metrics"]["cpu"] == 23.5 and body["running_job"] == running.name
	status, body = call(servers.get, server="SRV-0002")
	assert body["latest_metrics"] is None and body["running_job"] is None and body["benches"] == []


def test_benches_list_and_get_including_frappe_cloud(ff: FakeFrappe) -> None:
	status, body = call(benches.list)
	validate("benches.list", body)
	assert {b["name"]: b["server"] for b in body["items"]} == {"BENCH-0001": "SRV-0001", "BENCH-FC-01": None}
	status, body = call(benches.get, bench="BENCH-FC-01")
	validate("benches.get", body)
	assert body["sites"][0]["name"] == "staging.client-c.frappe.cloud" and body["capabilities"] == [
		"bench",
		"managed_backup",
		"managed_update",
		"site",
	]
	status, body = call(benches.list, server="SRV-0001")
	assert [b["name"] for b in body["items"]] == ["BENCH-0001"]
	assert call(benches.get, bench="nope")[0] == 404


def test_sites_list_and_get(ff: FakeFrappe) -> None:
	status, body = call(sites.list, bench="BENCH-0001")
	validate("sites.list", body)
	assert [s["name"] for s in body["items"]] == ["demo.smartchoice-iq.com", "erp.client-a.iq"]
	status, body = call(sites.get, site="demo.smartchoice-iq.com")
	validate("sites.get", body)
	assert body["custom_domains"] == ["demo.smartchoice.iq"] and body["bench_info"]["site_count"] == 2
	assert body["backups"][0]["restore_test_ok"] is True and body["db_size_mb"] == 812.4
	assert call(sites.list, status="Nope")[0] == 400


def test_pagination_by_name_and_newest_first(ff: FakeFrappe) -> None:
	status, page1 = call(sites.list, limit=2)
	validate("sites.list", page1)
	assert len(page1["items"]) == 2 and page1["next_cursor"]
	status, page2 = call(sites.list, limit=2, cursor=page1["next_cursor"])
	assert [s["name"] for s in page2["items"]] == ["staging.client-c.frappe.cloud"] and page2[
		"next_cursor"
	] is None
	for _ in range(5):
		ff.clock = ff.clock + timedelta(seconds=1)
		ff.add(
			"Infra Job",
			playbook="site.backup",
			playbook_title="Backup site",
			target_doctype="Site",
			target_name="demo.smartchoice-iq.com",
			status="Success",
			progress=100,
			triggered_by="x",
			creation=ff.clock,
			started_at=ff.clock,
			ended_at=ff.clock,
		)
	seen: list[str] = []
	cursor = None
	for _ in range(5):
		status, body = call(jobs.list, limit=2, cursor=cursor)
		validate("jobs.list", body)
		seen += [j["name"] for j in body["items"]]
		cursor = body["next_cursor"]
		if not cursor:
			break
	assert seen == sorted(seen, reverse=True) and len(seen) == 5, "newest first, no gaps, no repeats"
	status, body = call(jobs.list, cursor=_pagination.encode_cursor({"n": "x"}))
	assert status == 400 and body["error"]["code"] == "invalid_cursor"


def test_jobs_get_with_steps_and_run_cancel_retry(ff: FakeFrappe) -> None:
	status, body = call(
		jobs.run,
		playbook="site.backup",
		target_doctype="Site",
		target_name="demo.smartchoice-iq.com",
		params={"with_files": False},
	)
	assert status == 200
	validate("jobs.run", body)
	name = body["job"]["name"]
	assert (
		body["job"]["status"] == "Queued"
		and body["job"]["created"] is None
		and body["job"]["cancel_requested"] is False
	)
	status, body = call(jobs.run, playbook="server.reboot", target_doctype="Server", target_name="SRV-0001")
	assert status == 400 and body["error"]["code"] == "confirmation_required"
	validate("jobs.run", body, "400")
	status, body = call(
		jobs.run,
		playbook="server.snapshot",
		target_doctype="Server",
		target_name="SRV-0001",
		params="{bad json",
	)
	assert status == 400
	engine.run_job(name)
	status, body = call(jobs.get, job=name)
	validate("jobs.get", body)
	assert (
		body["status"] == "Success"
		and [s["idx"] for s in body["steps"]] == [0, 1]
		and body["steps"][0]["status"] == "Success"
	)
	status, body = call(jobs.cancel, job=name)
	assert status == 409 and body["error"]["code"] == "invalid_state"
	status, body = call(jobs.retry, job=name)
	assert status == 409
	status, body = call(jobs.list, status="Success", target_name="demo.smartchoice-iq.com")
	assert [j["name"] for j in body["items"]] == [name]
	queued = call(jobs.run, playbook="site.backup", target_doctype="Site", target_name="erp.client-a.iq")[1][
		"job"
	]["name"]
	status, body = call(jobs.cancel, job=queued)
	validate("jobs.cancel", body)
	assert body["job"]["status"] == "Cancelled" and body["job"]["cancel_requested"] is True


def test_playbooks_list_filters_by_capability(ff: FakeFrappe) -> None:
	status, body = call(playbooks.list)
	validate("playbooks.list", body)
	assert len(body["items"]) == len(PLAYBOOKS)
	status, body = call(playbooks.list, target_doctype="Server", target_name="SRV-0001")
	assert {p["key"] for p in body["items"]} == {
		"server.reboot",
		"server.snapshot",
		"server.apt_security",
		"service.control",
		"metrics.collect",
	}
	ff.add(
		"Server",
		name="SRV-FC",
		hostname="fc",
		provider_account="FC-STAGING",
		provider="frappe_cloud",
		status="Active",
	)
	status, body = call(playbooks.list, target_doctype="Server", target_name="SRV-FC")
	assert body["items"] == []
	status, body = call(playbooks.list, target_doctype="Bench", target_name="BENCH-FC-01")
	assert [p["key"] for p in body["items"]] == ["site.create"] and body["items"][0]["creates"] == "Site"
	assert call(playbooks.list, target_name="x")[0] == 400
	assert call(playbooks.list, target_doctype="Site", target_name="ghost")[0] == 404


def test_overview_summary(ff: FakeFrappe) -> None:
	ff.add(
		"Infra Job",
		playbook="site.migrate",
		playbook_title="Migrate site",
		target_doctype="Site",
		target_name="demo.smartchoice-iq.com",
		status="Running",
		progress=40,
		triggered_by="x",
		creation=ff.now(),
		started_at=ff.now(),
	)
	ff.add(
		"Infra Job",
		playbook="site.backup",
		playbook_title="Backup site",
		target_doctype="Site",
		target_name="demo.smartchoice-iq.com",
		status="Failed",
		progress=60,
		triggered_by="scheduler",
		creation=ff.now(),
		ended_at=ff.now() - timedelta(hours=1),
	)
	ff.add(
		"Infra Job",
		playbook="site.backup",
		playbook_title="Backup site",
		target_doctype="Site",
		target_name="demo.smartchoice-iq.com",
		status="Success",
		progress=100,
		triggered_by="scheduler",
		creation=ff.now(),
		ended_at=ff.now() - timedelta(days=2),
	)
	status, body = call(overview.summary)
	validate("overview.summary", body)
	assert body["servers"] == {
		"total": 2,
		"by_status": {"Provisioning": 0, "Active": 1, "Degraded": 1, "Down": 0, "Archived": 0},
	}
	assert body["sites"]["total"] == 3 and body["sites"]["by_status"]["Maintenance"] == 1
	assert body["jobs"] == {"queued": 0, "running": 1, "success_24h": 0, "failed_24h": 1}
	assert body["alerts"] == {"unresolved": 1, "info": 0, "warning": 1, "critical": 0}
	assert body["running_jobs"][0]["progress"] == 40 and body["recent_alerts"][0]["target"] == {
		"target_doctype": "Server",
		"target_name": "SRV-0002",
	}


def test_topology(ff: FakeFrappe) -> None:
	ff.add(
		"Infra Job",
		playbook="site.migrate",
		target_doctype="Site",
		target_name="demo.smartchoice-iq.com",
		status="Running",
		lock_key="infra:lock:server:SRV-0001",
		triggered_by="x",
	)
	status, body = call(inventory.topology)
	validate("inventory.topology", body)
	by_id = {n["id"]: n for n in body["nodes"]}
	assert (
		by_id["server:SRV-0001"]["label"] == "app-01.fra1"
		and by_id["server:SRV-0001"]["has_running_job"] is True
	)
	assert (
		by_id["site:demo.smartchoice-iq.com"]["has_running_job"] is True
		and by_id["site:erp.client-a.iq"]["has_running_job"] is False
	)
	assert (
		by_id["bench:BENCH-FC-01"]["status"] is None
		and by_id["provider:FC-STAGING"]["label"] == "Frappe Cloud (staging)"
	)
	edges = {e["id"] for e in body["edges"]}
	assert "provider:DO-STAGING->server:SRV-0001" in edges and "server:SRV-0001->bench:BENCH-0001" in edges
	assert (
		"provider:FC-STAGING->bench:BENCH-FC-01" in edges
		and "bench:BENCH-FC-01->site:staging.client-c.frappe.cloud" in edges
	)
	assert len(body["nodes"]) == 2 + 2 + 2 + 3 and len(body["edges"]) == 2 + 2 + 3


def test_iso_utc_converts_system_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(_serialize, "system_timezone", lambda: "Asia/Baghdad")
	assert _serialize.iso_utc(datetime(2026, 10, 7, 12, 30, 0)) == "2026-10-07T09:30:00Z"
	assert _serialize.iso_utc(None) is None
	assert _serialize.iso_utc("2026-10-07 12:30:00.123456") == "2026-10-07T09:30:00Z"
