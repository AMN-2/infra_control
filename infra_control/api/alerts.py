"""alerts.list / alerts.ack (contracts/openapi.yaml) over the A3.2 alert engine."""

from __future__ import annotations

import builtins
from typing import Any

import frappe
from frappe.utils import now_datetime

from infra_control.api import _serialize as ser
from infra_control.api import api, enum_param, int_param, str_param
from infra_control.api._pagination import (
	LIMIT_DEFAULT,
	LIMIT_MAX,
	_boundary_value,
	decode_cursor,
	encode_cursor,
)
from infra_control.core import audit
from infra_control.core.enums import AlertStatus, Severity, TargetDoctype
from infra_control.core.errors import InvalidCursor, InvalidState, NotFound
from infra_control.core.permissions import INFRA_OPERATOR

# Firing-first ordering (contract: "firing first then newest").
#
# A total order over alerts: rank(firing)=0 before rank(acknowledged|resolved)=1, then `fired_at`
# descending (newest first), then `name` descending as a stable tie-break. The shared
# `page_newest_first` helper can only order by one timestamp, so this module paginates the two
# rank buckets in sequence and carries the rank in the cursor. Within a bucket the cursor and the
# `<=` + Python boundary filter are the same technique `page_newest_first` uses, so the shared
# overfetch/tie handling is preserved.
_REST_STATUSES = [str(AlertStatus.ACKNOWLEDGED), str(AlertStatus.RESOLVED)]


def _segments(status: str | None) -> builtins.list[tuple[int, Any]]:
	"""(rank, status filter clause) buckets to scan, in output order, honouring a status filter."""
	if status == str(AlertStatus.FIRING):
		return [(0, str(AlertStatus.FIRING))]
	if status in _REST_STATUSES:
		return [(1, status)]
	return [(0, str(AlertStatus.FIRING)), (1, ["in", _REST_STATUSES])]


def _page_alerts(
	base_filters: dict[str, Any], status: str | None, limit: int, cursor: str | None
) -> dict[str, Any]:
	after = decode_cursor(cursor)
	if after is not None and ("rk" not in after or "f" not in after or "n" not in after):
		raise InvalidCursor("cursor does not belong to this list", {"field": "cursor"})
	fields = [*ser.ALERT_FIELDS, "fired_at", "name"]
	collected: builtins.list[tuple[int, dict[str, Any]]] = []
	for rank, clause in _segments(status):
		if after is not None and rank < after["rk"]:
			continue
		need = (limit + 1) - len(collected)
		if need <= 0:
			break
		filters = dict(base_filters)
		filters["status"] = clause
		if after is not None and rank == after["rk"]:
			filters["fired_at"] = ["<=", _boundary_value(after["f"])]
		rows = frappe.get_all(
			"Alert", filters=filters, fields=fields, order_by="fired_at desc, name desc", limit=need + 50
		)
		if after is not None and rank == after["rk"]:
			boundary = (str(after["f"]), str(after["n"]))
			rows = [r for r in rows if (str(r["fired_at"]), str(r["name"])) < boundary]
		collected.extend((rank, r) for r in rows)
		if len(collected) > limit:
			break
	has_more = len(collected) > limit
	collected = collected[:limit]
	next_cursor = None
	if has_more and collected:
		rank, last = collected[-1]
		next_cursor = encode_cursor({"rk": rank, "f": last["fired_at"], "n": last["name"]})
	return {"items": [ser.alert(r) for _, r in collected], "next_cursor": next_cursor}


@api()
def list(
	status: str | None = None,
	severity: str | None = None,
	target_doctype: str | None = None,
	target_name: str | None = None,
	limit: Any = None,
	cursor: str | None = None,
) -> dict[str, Any]:
	filters: dict[str, Any] = {}
	status_value = enum_param("status", status, AlertStatus)
	if sev := enum_param("severity", severity, Severity):
		filters["severity"] = sev
	if dt := enum_param("target_doctype", target_doctype, TargetDoctype):
		filters["target_doctype"] = dt
	if tn := str_param("target_name", target_name):
		filters["target_name"] = tn
	return _page_alerts(
		filters,
		status_value,
		int_param("limit", limit, default=LIMIT_DEFAULT, minimum=1, maximum=LIMIT_MAX),
		cursor,
	)


def _alert_row(name: str) -> dict[str, Any]:
	rows = frappe.get_all("Alert", filters={"name": name}, fields=ser.ALERT_FIELDS, limit=1)
	if not rows:
		raise NotFound("Alert", name)
	return dict(rows[0])


@api(methods=("POST",), role=INFRA_OPERATOR)
def ack(alert: str | None = None) -> dict[str, Any]:
	name = str_param("alert", alert, required=True)
	assert name is not None
	row = _alert_row(name)
	if row["status"] != str(AlertStatus.FIRING):
		raise InvalidState(
			f"Alert {name} is {row['status']}; only a firing alert can be acknowledged",
			{"status": row["status"]},
		)
	doc: Any = frappe.get_doc("Alert", name)
	doc.status = str(AlertStatus.ACKNOWLEDGED)
	doc.acknowledged_by = frappe.session.user
	doc.acknowledged_at = now_datetime()
	doc.save(ignore_permissions=True)
	audit.record(
		"alerts.ack",
		result="success",
		target_doctype=row.get("target_doctype"),
		target_name=row.get("target_name"),
		params={"alert": name},
	)
	return {"alert": ser.alert(_alert_row(name))}
