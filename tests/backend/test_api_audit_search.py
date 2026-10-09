"""audit.list (newest first, filters, cursor) and search.query (palette) on the fake."""

from __future__ import annotations

from datetime import datetime

import pytest
from fake_frappe import FakeFrappe
from test_api import call, validate

import infra_control.api as api_pkg
from infra_control.api import _pagination, _serialize, audit, search
from infra_control.core import permissions


@pytest.fixture
def ff(monkeypatch: pytest.MonkeyPatch) -> FakeFrappe:
	f = FakeFrappe()
	for module in (api_pkg, _pagination, _serialize, audit, search, permissions):
		monkeypatch.setattr(module, "frappe", f, raising=False)
	monkeypatch.setattr(_serialize, "system_timezone", lambda: "UTC")
	monkeypatch.setattr(audit, "get_datetime", lambda v: v)
	monkeypatch.setattr(_pagination, "get_datetime", lambda v: datetime.fromisoformat(str(v)))
	for i, (action, dt, name) in enumerate(
		[
			("jobs.run:site.migrate", "Site", "demo.iq"),
			("alerts.ack", "Server", "SRV-0002"),
			("git.connect", None, None),
		],
		start=1,
	):
		f.add(
			"Infra Audit Log",
			name=f"AUD-{i:06d}",
			ts=f"2026-10-07 09:{i:02d}:00",
			user="ameen@x",
			action=action,
			result="success",
			target_doctype=dt,
			target_name=name,
			job="JOB-00042" if i == 1 else None,
			params_hash="e3b0",
		)
	f.add(
		"Server",
		name="SRV-0001",
		hostname="app-01.fra1",
		status="Active",
		provider="digitalocean",
		public_ip="1.2.3.4",
		region="fra1",
	)
	f.add(
		"Site",
		name="demo.iq",
		domain="demo.iq",
		status="Active",
		provider="digitalocean",
		bench="BENCH-0001",
		server="SRV-0001",
	)
	f.add(
		"Playbook",
		name="site.migrate",
		key="site.migrate",
		title="Migrate site",
		target_doctype="Site",
		risk="medium",
	)
	f.add(
		"Infra Job",
		name="JOB-00042",
		playbook_title="Migrate site",
		target_name="demo.iq",
		status="Running",
		progress=40,
	)
	f.add(
		"Alert Rule", name="RULE-0002", title="CPU above 90%", kind="metric", severity="critical", enabled=1
	)
	return f


def test_audit_list_is_newest_first_with_filters_and_cursor(ff: FakeFrappe) -> None:
	status, body = call(audit.list, limit=2)
	assert status == 200, body
	validate("audit.list", body)
	assert [e["name"] for e in body["items"]] == ["AUD-000003", "AUD-000002"] and body["next_cursor"]
	assert body["items"][0]["target"] is None and body["items"][1]["target"] == {
		"target_doctype": "Server",
		"target_name": "SRV-0002",
	}
	status, body = call(audit.list, cursor=body["next_cursor"], limit=2)
	assert [e["name"] for e in body["items"]] == ["AUD-000001"] and body["items"][0]["job"] == "JOB-00042"
	status, body = call(audit.list, action="jobs.run")
	assert [e["name"] for e in body["items"]] == ["AUD-000001"]
	status, body = call(audit.list, target_doctype="Server", target_name="SRV-0002")
	assert [e["action"] for e in body["items"]] == ["alerts.ack"]
	status, body = call(
		audit.list, **{"from": datetime(2026, 10, 7, 9, 2), "to": datetime(2026, 10, 7, 9, 3)}
	)
	assert [e["name"] for e in body["items"]] == ["AUD-000003", "AUD-000002"]
	status, body = call(audit.list, target_doctype="Nope")
	assert status == 400


def test_search_covers_every_type(ff: FakeFrappe) -> None:
	status, body = call(search.query, q="mi")
	assert status == 200
	validate("search.query", body)
	types = {r["type"] for r in body["items"]}
	assert {"playbook", "job"} <= types
	status, body = call(search.query, q="demo")
	assert {r["type"] for r in body["items"]} >= {"site", "job"}
	status, body = call(search.query, q="app-01")
	assert body["items"][0] == {
		"type": "server",
		"id": "SRV-0001",
		"title": "app-01.fra1",
		"subtitle": "1.2.3.4 · fra1",
		"status": "Active",
		"provider": "digitalocean",
	}
	status, body = call(search.query, q="cpu")
	assert body["items"][0]["type"] == "alert" and body["items"][0]["status"] == "enabled"
	status, body = call(search.query, q="")
	assert status == 400
