"""audit.list: the immutable audit log, newest first (plan section 6.1; security requirement 8).
Every mutation an operator makes lands here with the user, the action, the target, a hash of
the parameters (never the parameters themselves) and the job it produced."""

from __future__ import annotations

from typing import Any

from frappe.utils import get_datetime

from infra_control.api import _serialize as ser
from infra_control.api import api, enum_param, int_param, str_param
from infra_control.api._pagination import LIMIT_DEFAULT, LIMIT_MAX, page_newest_first
from infra_control.core.enums import TargetDoctype
from infra_control.core.errors import ValidationError

FIELDS = ["name", "ts", "user", "action", "result", "target_doctype", "target_name", "job", "params_hash"]


def entry(row: dict[str, Any]) -> dict[str, Any]:
	return {
		"name": row["name"],
		"ts": ser.iso_utc(row.get("ts")) or ser.iso_utc(row.get("creation")) or "",
		"user": row.get("user") or "",
		"action": row.get("action") or "",
		"target": ser.target_ref(row.get("target_doctype"), row.get("target_name")),
		"params_hash": row.get("params_hash") or "",
		"job": row.get("job") or None,
		"result": row.get("result") or "success",
	}


def _datetime_param(name: str, value: Any) -> Any:
	if value in (None, ""):
		return None
	try:
		return get_datetime(str(value))
	except Exception:
		raise ValidationError(f"{name} must be a date-time", {"field": name}) from None


@api()
def list(
	user: str | None = None,
	action: str | None = None,
	target_doctype: str | None = None,
	target_name: str | None = None,
	limit: Any = None,
	cursor: str | None = None,
	**window: Any,
) -> dict[str, Any]:
	filters: dict[str, Any] = {}
	if u := str_param("user", user):
		filters["user"] = u
	if a := str_param("action", action):
		filters["action"] = ["like", f"{a}%"]
	if dt := enum_param("target_doctype", target_doctype, TargetDoctype):
		filters["target_doctype"] = dt
	if tn := str_param("target_name", target_name):
		filters["target_name"] = tn
	# `from`/`to` are reserved words in Python signatures; Frappe passes them in **window.
	since = _datetime_param("from", window.get("from"))
	until = _datetime_param("to", window.get("to"))
	if since and until:
		filters["ts"] = ["between", [since, until]]
	elif since:
		filters["ts"] = [">=", since]
	elif until:
		filters["ts"] = ["<=", until]
	return page_newest_first(
		"Infra Audit Log",
		filters=filters,
		fields=FIELDS,
		limit=int_param("limit", limit, default=LIMIT_DEFAULT, minimum=1, maximum=LIMIT_MAX),
		cursor=cursor,
		serialize=entry,
		sort_field="ts",
	)
