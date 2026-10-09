"""search.query: the command palette's search across servers, sites, benches, playbooks,
jobs and alert rules (plan section 10.2). Substring match, a handful of rows per type."""

from __future__ import annotations

from typing import Any

import frappe

from infra_control.api import api, int_param, str_param
from infra_control.core.errors import ValidationError


def _like(value: str) -> list[Any]:
	return ["like", f"%{value}%"]


def _rows(
	doctype: str, fields: list[str], or_filters: dict[str, Any], limit: int, order_by: str
) -> list[dict[str, Any]]:
	rows: list[dict[str, Any]] = frappe.get_all(
		doctype, or_filters=or_filters, fields=fields, limit=limit, order_by=order_by
	)
	return rows


@api()
def query(q: str | None = None, limit: Any = None) -> dict[str, Any]:
	text = (str_param("q", q, required=True) or "").strip()
	if not text or len(text) > 200:
		raise ValidationError("q must be 1 to 200 characters", {"field": "q"})
	n = int_param("limit", limit, default=20, minimum=1, maximum=50)
	per_type = max(2, n // 4)
	items: list[dict[str, Any]] = []
	for r in _rows(
		"Server",
		["name", "hostname", "status", "provider", "public_ip", "region"],
		{"name": _like(text), "hostname": _like(text)},
		per_type,
		"hostname asc",
	):
		items.append(
			{
				"type": "server",
				"id": r["name"],
				"title": r.get("hostname") or r["name"],
				"subtitle": " · ".join(x for x in (r.get("public_ip"), r.get("region")) if x) or None,
				"status": r.get("status"),
				"provider": r.get("provider"),
			}
		)
	for r in _rows(
		"Site",
		["name", "domain", "status", "provider", "bench", "server"],
		{"name": _like(text), "domain": _like(text)},
		per_type,
		"domain asc",
	):
		items.append(
			{
				"type": "site",
				"id": r["name"],
				"title": r.get("domain") or r["name"],
				"subtitle": f"{r.get('bench') or '?'} on {r.get('server') or '?'}",
				"status": r.get("status"),
				"provider": r.get("provider"),
			}
		)
	for r in _rows(
		"Bench",
		["name", "title", "provider", "server", "frappe_version"],
		{"name": _like(text), "title": _like(text)},
		per_type,
		"title asc",
	):
		items.append(
			{
				"type": "bench",
				"id": r["name"],
				"title": r.get("title") or r["name"],
				"subtitle": " · ".join(x for x in (r.get("server"), r.get("frappe_version")) if x) or None,
				"status": None,
				"provider": r.get("provider"),
			}
		)
	for r in _rows(
		"Playbook",
		["name", "key", "title", "target_doctype", "risk"],
		{"key": _like(text), "title": _like(text)},
		per_type,
		"key asc",
	):
		items.append(
			{
				"type": "playbook",
				"id": r.get("key") or r["name"],
				"title": r.get("title") or r["name"],
				"subtitle": f"{r.get('target_doctype')} · {r.get('risk')} risk",
				"status": None,
				"provider": None,
			}
		)
	for r in _rows(
		"Infra Job",
		["name", "playbook_title", "target_name", "status", "progress"],
		{"name": _like(text), "target_name": _like(text), "playbook_title": _like(text)},
		per_type,
		"creation desc",
	):
		items.append(
			{
				"type": "job",
				"id": r["name"],
				"title": f"{r.get('playbook_title')} · {r.get('target_name')}",
				"subtitle": f"{r.get('status')} · {int(r.get('progress') or 0)}%",
				"status": r.get("status"),
				"provider": None,
			}
		)
	for r in _rows(
		"Alert Rule",
		["name", "title", "kind", "severity", "enabled"],
		{"name": _like(text), "title": _like(text)},
		per_type,
		"title asc",
	):
		items.append(
			{
				"type": "alert",
				"id": r["name"],
				"title": r.get("title") or r["name"],
				"subtitle": f"{r.get('kind')} · {r.get('severity')}",
				"status": "enabled" if r.get("enabled") else "disabled",
				"provider": None,
			}
		)
	return {"items": items[:n]}
