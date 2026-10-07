"""sites.list / sites.get."""

from __future__ import annotations

import builtins
from typing import Any

import frappe

from infra_control.api import _serialize as ser
from infra_control.api import api, enum_param, int_param, str_param
from infra_control.api._inventory_helpers import child_rows, child_values, count_by, running_job_for
from infra_control.api._pagination import LIMIT_DEFAULT, LIMIT_MAX, page_by_name
from infra_control.core.enums import SiteStatus
from infra_control.core.errors import NotFound


def _enrich(rows: builtins.list[dict[str, Any]]) -> builtins.list[dict[str, Any]]:
	domains = child_values("Site", "Site Domain", "domain", [r["name"] for r in rows])
	return [ser.site(r, custom_domains=domains.get(r["name"], [])) for r in rows]


@api()
def list(
	status: str | None = None,
	provider_account: str | None = None,
	bench: str | None = None,
	server: str | None = None,
	limit: Any = None,
	cursor: str | None = None,
) -> dict[str, Any]:
	filters: dict[str, Any] = {}
	if s := enum_param("status", status, SiteStatus):
		filters["status"] = s
	for key, value in (("provider_account", provider_account), ("bench", bench), ("server", server)):
		if value:
			filters[key] = value
	page = page_by_name(
		"Site",
		filters=filters,
		fields=ser.SITE_FIELDS,
		limit=int_param("limit", limit, default=LIMIT_DEFAULT, minimum=1, maximum=LIMIT_MAX),
		cursor=cursor,
		serialize=lambda r: r,
	)
	page["items"] = _enrich(page["items"])
	return page


@api()
def get(site: str | None = None) -> dict[str, Any]:
	name = str_param("site", site, required=True)
	assert name is not None
	rows = frappe.get_all("Site", filters={"name": name}, fields=ser.SITE_FIELDS, limit=1)
	if not rows:
		raise NotFound("Site", name)
	out = _enrich(rows)[0]
	bench_rows = frappe.get_all("Bench", filters={"name": rows[0]["bench"]}, fields=ser.BENCH_FIELDS, limit=1)
	if not bench_rows:
		raise NotFound("Bench", str(rows[0]["bench"]))
	apps = child_rows("Bench", "Bench App", ["app", "version", "branch"], [bench_rows[0]["name"]])
	out["bench_info"] = ser.bench(
		bench_rows[0],
		apps=apps.get(bench_rows[0]["name"], []),
		site_count=count_by("Site", "bench", {"bench": bench_rows[0]["name"]}).get(bench_rows[0]["name"], 0),
	)
	backups = frappe.get_all(
		"Backup",
		filters={"site": name},
		fields=[
			"name",
			"site",
			"kind",
			"location",
			"size_mb",
			"created_at",
			"last_restore_test",
			"restore_test_result",
			"creation",
		],
		order_by="created_at desc",
		limit=10,
	)
	out["backups"] = [ser.backup(b) for b in backups]
	out["running_job"] = running_job_for("Site", name, rows[0].get("server"))
	return out
