"""servers.list / servers.get (contracts/openapi.yaml)."""

from __future__ import annotations

import builtins
from typing import Any

import frappe

from infra_control.api import _serialize as ser
from infra_control.api import api, enum_param, int_param, str_param
from infra_control.api._inventory_helpers import child_rows, child_values, count_by, running_job_for
from infra_control.api._pagination import LIMIT_DEFAULT, LIMIT_MAX, page_by_name
from infra_control.core.enums import ServerRole, ServerStatus
from infra_control.core.errors import NotFound


def _enrich(rows: builtins.list[dict[str, Any]]) -> builtins.list[dict[str, Any]]:
	names = [r["name"] for r in rows]
	tags = child_values("Server", "Server Tag", "tag", names)
	benches = count_by("Bench", "server", {"server": ["in", names]}) if names else {}
	sites = count_by("Site", "server", {"server": ["in", names]}) if names else {}
	return [
		ser.server(
			r,
			tags=tags.get(r["name"], []),
			bench_count=benches.get(r["name"], 0),
			site_count=sites.get(r["name"], 0),
		)
		for r in rows
	]


@api()
def list(
	status: str | None = None,
	provider_account: str | None = None,
	role: str | None = None,
	region: str | None = None,
	limit: Any = None,
	cursor: str | None = None,
) -> dict[str, Any]:
	filters: dict[str, Any] = {}
	if s := enum_param("status", status, ServerStatus):
		filters["status"] = s
	if r := enum_param("role", role, ServerRole):
		filters["role"] = r
	if provider_account:
		filters["provider_account"] = provider_account
	if region:
		filters["region"] = region
	page = page_by_name(
		"Server",
		filters=filters,
		fields=ser.SERVER_FIELDS,
		limit=int_param("limit", limit, default=LIMIT_DEFAULT, minimum=1, maximum=LIMIT_MAX),
		cursor=cursor,
		serialize=lambda r: r,
	)
	page["items"] = _enrich(page["items"])
	return page


@api()
def get(server: str | None = None) -> dict[str, Any]:
	name = str_param("server", server, required=True)
	assert name is not None
	rows = frappe.get_all("Server", filters={"name": name}, fields=ser.SERVER_FIELDS, limit=1)
	if not rows:
		raise NotFound("Server", name)
	out = _enrich(rows)[0]
	bench_rows = frappe.get_all(
		"Bench", filters={"server": name}, fields=ser.BENCH_FIELDS, order_by="name asc"
	)
	apps = child_rows("Bench", "Bench App", ["app", "version", "branch"], [b["name"] for b in bench_rows])
	site_counts = count_by("Site", "bench", {"server": name})
	out["benches"] = [
		ser.bench(b, apps=apps.get(b["name"], []), site_count=site_counts.get(b["name"], 0))
		for b in bench_rows
	]
	latest = frappe.get_all(
		"Server Metric",
		filters={"server": name, "resolution": "1m"},
		fields=["ts", "cpu", "ram", "disk", "load1", "queue_backlog"],
		order_by="ts desc",
		limit=1,
	)
	out["latest_metrics"] = (
		{
			"ts": ser.iso_utc(latest[0]["ts"]),
			"cpu": float(latest[0]["cpu"] or 0),
			"ram": float(latest[0]["ram"] or 0),
			"disk": float(latest[0]["disk"] or 0),
			"load1": float(latest[0]["load1"] or 0),
			"queue_backlog": int(latest[0]["queue_backlog"] or 0),
		}
		if latest
		else None
	)
	out["running_job"] = running_job_for("Server", name, name)
	return out
