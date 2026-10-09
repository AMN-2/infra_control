"""Tenants: create/update/list/get, one tenant per site, suspend = one job per site."""

from __future__ import annotations

from typing import Any

import pytest
from fake_frappe import FakeFrappe
from test_api import call, validate

import infra_control.api as api_pkg
from infra_control.api import _inventory_helpers, _pagination, _serialize, tenants
from infra_control.core import permissions


@pytest.fixture
def ff(monkeypatch: pytest.MonkeyPatch) -> FakeFrappe:
	f = FakeFrappe()
	for module in (api_pkg, _inventory_helpers, _pagination, _serialize, tenants, permissions):
		monkeypatch.setattr(module, "frappe", f)
	monkeypatch.setattr(_serialize, "system_timezone", lambda: "UTC")
	for d in ("a.iq", "b.iq", "c.iq"):
		f.add(
			"Site",
			name=d,
			domain=d,
			status="Active",
			bench="BENCH-0001",
			server="SRV-0001",
			provider="digitalocean",
			provider_account="DO",
		)
	return f


def test_tenant_lifecycle_and_one_tenant_per_site(ff: FakeFrappe) -> None:
	status, body = call(
		tenants.create, label="client-d", title="Client D", plan="Business", contact_email="it@client-d.iq"
	)
	assert status == 200
	validate("tenants.create", body)
	t = body["tenant"]
	assert (t["name"], t["title"], t["plan"], t["site_count"], t["sites"]) == (
		"CLIENT-D",
		"Client D",
		"Business",
		0,
		[],
	)
	status, body = call(tenants.create, label="CLIENT-D")
	assert status == 409
	status, body = call(tenants.create, label="CLIENT-X", contact_email="not-an-email")
	assert status == 400
	status, body = call(tenants.update, tenant="CLIENT-D", notes="VIP", plan="")
	assert status == 200 and body["tenant"]["notes"] == "VIP" and body["tenant"]["plan"] is None
	status, body = call(tenants.assign, tenant="CLIENT-D", site="a.iq")
	assert status == 200 and [s["domain"] for s in body["tenant"]["sites"]] == ["a.iq"]
	validate("tenants.assign", body)
	call(tenants.assign, tenant="CLIENT-D", site="b.iq")
	call(tenants.create, label="CLIENT-E", title="Client E")
	status, body = call(tenants.assign, tenant="CLIENT-E", site="a.iq")
	assert status == 409 and "CLIENT-D" in body["error"]["message"]
	status, body = call(tenants.assign, tenant="CLIENT-D", site="a.iq", remove=True)
	assert [s["domain"] for s in body["tenant"]["sites"]] == ["b.iq"]
	status, body = call(tenants.list)
	validate("tenants.list", body)
	assert [(x["name"], x["site_count"]) for x in body["items"]] == [("CLIENT-D", 1), ("CLIENT-E", 0)]
	status, body = call(tenants.list, query="client e")
	assert [x["name"] for x in body["items"]] == ["CLIENT-E"]
	status, body = call(tenants.get, tenant="CLIENT-D")
	validate("tenants.get", body)
	assert body["sites"][0]["server"] == "SRV-0001"
	status, body = call(tenants.get, tenant="NOPE")
	assert status == 404


def test_suspend_creates_one_job_per_site(ff: FakeFrappe, monkeypatch: pytest.MonkeyPatch) -> None:
	created: list[tuple[str, dict[str, Any]]] = []

	class _Job:
		def __init__(self, n: int) -> None:
			self.name = f"JOB-{n}"

	def fake_create(pb: str, dt: str, name: str, params: dict[str, Any], **kw: Any) -> _Job:
		if name == "c.iq":
			from infra_control.core.errors import InvalidState

			raise InvalidState("locked", {})
		created.append((name, params))
		return _Job(len(created))

	monkeypatch.setattr(tenants.engine, "create_job", fake_create)
	call(tenants.create, label="CLIENT-D", title="Client D")
	for d in ("a.iq", "b.iq", "c.iq"):
		call(tenants.assign, tenant="CLIENT-D", site=d)
	status, body = call(tenants.suspend, tenant="CLIENT-D", suspended=True)
	assert status == 200
	validate("tenants.suspend", body)
	assert body["jobs"] == ["JOB-1", "JOB-2"] and body["errors"][0]["site"] == "c.iq"
	assert created == [("a.iq", {"suspended": True}), ("b.iq", {"suspended": True})]
	assert body["tenant"]["status"] == "suspended"
	status, body = call(tenants.suspend, tenant="CLIENT-D", suspended=False)
	assert body["tenant"]["status"] == "active" and created[-1] == ("b.iq", {"suspended": False})
