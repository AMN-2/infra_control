"""benches.list / benches.get / benches.check_updates / benches.refs (ADR 0009)."""

from __future__ import annotations

import builtins
from typing import Any

import frappe

from infra_control.api import _serialize as ser
from infra_control.api import api, int_param, str_param
from infra_control.api._inventory_helpers import child_rows, child_values, count_by, running_job_for
from infra_control.api._pagination import LIMIT_DEFAULT, LIMIT_MAX, page_by_name
from infra_control.benches import updates
from infra_control.core import audit
from infra_control.core.enums import AuditResult
from infra_control.core.errors import NotFound
from infra_control.core.permissions import INFRA_OPERATOR


def _enrich(rows: builtins.list[dict[str, Any]]) -> builtins.list[dict[str, Any]]:
	names = [r["name"] for r in rows]
	apps = child_rows("Bench", "Bench App", updates.APP_FIELDS, names)
	sites = count_by("Site", "bench", {"bench": ["in", names]}) if names else {}
	return [ser.bench(r, apps=apps.get(r["name"], []), site_count=sites.get(r["name"], 0)) for r in rows]


@api()
def list(
	provider_account: str | None = None,
	server: str | None = None,
	limit: Any = None,
	cursor: str | None = None,
) -> dict[str, Any]:
	filters: dict[str, Any] = {}
	if provider_account:
		filters["provider_account"] = provider_account
	if server:
		filters["server"] = server
	page = page_by_name(
		"Bench",
		filters=filters,
		fields=ser.BENCH_FIELDS,
		limit=int_param("limit", limit, default=LIMIT_DEFAULT, minimum=1, maximum=LIMIT_MAX),
		cursor=cursor,
		serialize=lambda r: r,
	)
	page["items"] = _enrich(page["items"])
	return page


@api()
def get(bench: str | None = None) -> dict[str, Any]:
	name = str_param("bench", bench, required=True)
	assert name is not None
	return _detail(name)


def _detail(name: str) -> dict[str, Any]:
	rows = frappe.get_all("Bench", filters={"name": name}, fields=ser.BENCH_FIELDS, limit=1)
	if not rows:
		raise NotFound("Bench", name)
	out = _enrich(rows)[0]
	site_rows = frappe.get_all("Site", filters={"bench": name}, fields=ser.SITE_FIELDS, order_by="name asc")
	domains = child_values("Site", "Site Domain", "domain", [s["name"] for s in site_rows])
	out["sites"] = [ser.site(s, custom_domains=domains.get(s["name"], [])) for s in site_rows]
	out["running_job"] = running_job_for("Bench", name, rows[0].get("server"))
	return out


@api(methods=("POST",), role=INFRA_OPERATOR)
def check_updates(bench: str | None = None) -> dict[str, Any]:
	"""Ask upstream (GitHub) how far every app on the bench is behind; returns the bench detail."""
	name = str_param("bench", bench, required=True)
	assert name is not None
	updates.check_bench(name)
	audit.record("bench.check_updates", result=AuditResult.SUCCESS, target_doctype="Bench", target_name=name)
	return _detail(name)


@api()
def refs(bench: str | None = None, app: str | None = None) -> dict[str, Any]:
	"""Branches and tags of one app's upstream repository (for switching its version)."""
	name = str_param("bench", bench, required=True)
	app_name = str_param("app", app, required=True)
	assert name is not None and app_name is not None
	return updates.refs_for(name, app_name)
