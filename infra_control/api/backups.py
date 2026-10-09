"""backups.* (A4.2): per-site backup policy (schedule + retention) and the full backup list."""

from __future__ import annotations

import builtins
from typing import Any

import frappe
from frappe.utils import now_datetime

from infra_control.api import _serialize as ser
from infra_control.api import api, bool_param, enum_param, int_param, str_param
from infra_control.api._pagination import LIMIT_DEFAULT, LIMIT_MAX, page_by_name
from infra_control.backups.schedule import FREQUENCIES, WEEKDAYS, next_run_after
from infra_control.core.errors import NotFound
from infra_control.core.permissions import INFRA_OPERATOR

FIELDS = [
	"name",
	"site",
	"enabled",
	"frequency",
	"hour",
	"weekday",
	"with_files",
	"retain",
	"last_run",
	"last_job",
	"next_run",
]


def _serialized(row: dict[str, Any]) -> dict[str, Any]:
	return {
		"site": row["site"],
		"enabled": bool(row.get("enabled")),
		"frequency": row["frequency"],
		"hour": int(row.get("hour") or 0),
		"weekday": row.get("weekday") or "sun",
		"with_files": bool(row.get("with_files")),
		"retain": int(row.get("retain") or 0),
		"last_run": ser.iso_utc(row.get("last_run")),
		"last_job": row.get("last_job") or None,
		"next_run": ser.iso_utc(row.get("next_run")),
	}


def _require_site(site: Any) -> str:
	name = str_param("site", site, required=True) or ""
	if not frappe.db.exists("Site", name):
		raise NotFound("Site", name)
	return name


@api()
def policy(site: str | None = None) -> dict[str, Any]:
	name = _require_site(site)
	rows = frappe.get_all("Backup Policy", filters={"site": name}, fields=FIELDS, limit=1)
	return {"policy": _serialized(rows[0]) if rows else None}


@api(methods=("POST",), role=INFRA_OPERATOR)
def set_policy(
	site: str | None = None,
	enabled: Any = None,
	frequency: str | None = None,
	hour: Any = None,
	weekday: str | None = None,
	with_files: Any = None,
	retain: Any = None,
) -> dict[str, Any]:
	"""Create or replace the site's policy; `next_run` is recomputed from now."""
	name = _require_site(site)
	freq = enum_param("frequency", frequency, FREQUENCIES) or "daily"
	hour_value = int_param("hour", hour, default=2, minimum=0, maximum=23)
	weekday_value = enum_param("weekday", weekday, WEEKDAYS) or "sun"
	values: dict[str, Any] = {
		"enabled": bool_param("enabled", enabled, default=True),
		"frequency": freq,
		"hour": hour_value,
		"weekday": weekday_value,
		"with_files": bool_param("with_files", with_files, default=True),
		"retain": int_param("retain", retain, default=14, minimum=0, maximum=365),
		"next_run": next_run_after(freq, hour_value, weekday_value, now_datetime()),
	}
	existing = frappe.get_all("Backup Policy", filters={"site": name}, pluck="name", limit=1)
	if existing:
		doc: Any = frappe.get_doc("Backup Policy", existing[0])
		doc.update(values)
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": "Backup Policy", "site": name, **values})
		doc.insert()
	row = frappe.get_all("Backup Policy", filters={"site": name}, fields=FIELDS, limit=1)[0]
	return {"policy": _serialized(row)}


@api()
def list(
	site: str | None = None, kind: str | None = None, limit: Any = None, cursor: str | None = None
) -> dict[str, Any]:
	"""Every backup of a site (the site detail shows only the last 10), newest first by name."""
	name = _require_site(site)
	filters: dict[str, Any] = {"site": name}
	if k := enum_param("kind", kind, ("db", "files", "snapshot")):
		filters["kind"] = k
	fields: builtins.list[str] = [
		"name",
		"site",
		"kind",
		"location",
		"size_mb",
		"created_at",
		"creation",
		"last_restore_test",
		"restore_test_result",
	]
	return page_by_name(
		"Backup",
		filters=filters,
		fields=fields,
		limit=int_param("limit", limit, default=LIMIT_DEFAULT, minimum=1, maximum=LIMIT_MAX),
		cursor=cursor,
		serialize=ser.backup,
	)
