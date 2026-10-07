"""Cursor pagination: `?limit=50&cursor=...` -> `{ items, next_cursor }` (contracts/README.md).

The cursor is opaque to clients: base64url of a small JSON object with the sort key of the last
row. Lists ordered by `name` use `{"n": name}`; newest-first lists use `{"c": creation, "n": name}`.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from typing import Any

import frappe
from frappe.utils import get_datetime

from infra_control.core.errors import InvalidCursor

LIMIT_DEFAULT = 50
LIMIT_MAX = 200


def encode_cursor(data: dict[str, Any]) -> str:
	raw = json.dumps(data, separators=(",", ":"), default=str).encode()
	return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> dict[str, Any] | None:
	if not cursor:
		return None
	try:
		padded = cursor + "=" * (-len(cursor) % 4)
		data = json.loads(base64.urlsafe_b64decode(padded.encode()))
	except (ValueError, TypeError):
		raise InvalidCursor("cursor is not valid", {"field": "cursor"}) from None
	if not isinstance(data, dict):
		raise InvalidCursor("cursor is not valid", {"field": "cursor"})
	return data


def _boundary_value(value: Any) -> Any:
	"""Cursor values are strings; timestamps are parsed back so the DB compares like with like."""
	if isinstance(value, str):
		try:
			parsed = get_datetime(value)
		except Exception:  # not a timestamp: compare as-is
			return value
		return parsed or value
	return value


def page_by_name(
	doctype: str,
	*,
	filters: dict[str, Any],
	fields: list[str],
	limit: int,
	cursor: str | None,
	serialize: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
	"""Rows ordered by `name` ascending; cursor = last name."""
	after = decode_cursor(cursor)
	query = dict(filters)
	if after:
		if "n" not in after:
			raise InvalidCursor("cursor does not belong to this list", {"field": "cursor"})
		query["name"] = [">", after["n"]]
	rows = frappe.get_all(doctype, filters=query, fields=fields, order_by="name asc", limit=limit + 1)
	has_more = len(rows) > limit
	rows = rows[:limit]
	return {
		"items": [serialize(r) for r in rows],
		"next_cursor": encode_cursor({"n": rows[-1]["name"]}) if has_more and rows else None,
	}


def page_newest_first(
	doctype: str,
	*,
	filters: dict[str, Any],
	fields: list[str],
	limit: int,
	cursor: str | None,
	serialize: Callable[[dict[str, Any]], dict[str, Any]],
	sort_field: str = "creation",
) -> dict[str, Any]:
	"""Rows ordered by (`sort_field` desc, name desc); cursor = last (sort value, name)."""
	after = decode_cursor(cursor)
	query = dict(filters)
	if after:
		if "c" not in after or "n" not in after:
			raise InvalidCursor("cursor does not belong to this list", {"field": "cursor"})
		query[sort_field] = ["<=", _boundary_value(after["c"])]
	if "name" not in fields:
		fields = [*fields, "name"]
	if sort_field not in fields:
		fields = [*fields, sort_field]
	# Rows sharing the boundary timestamp are re-fetched and skipped below (microsecond ties are rare).
	rows = frappe.get_all(
		doctype, filters=query, fields=fields, order_by=f"{sort_field} desc, name desc", limit=limit + 51
	)
	if after:
		boundary = (str(after["c"]), str(after["n"]))
		rows = [r for r in rows if (str(r[sort_field]), str(r["name"])) < boundary]
	has_more = len(rows) > limit
	rows = rows[:limit]
	return {
		"items": [serialize(r) for r in rows],
		"next_cursor": encode_cursor({"c": rows[-1][sort_field], "n": rows[-1]["name"]})
		if has_more and rows
		else None,
	}
