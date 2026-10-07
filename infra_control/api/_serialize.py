"""Document -> contract object. Only fields present in contracts/openapi.yaml, ever."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import get_datetime, get_system_timezone

from infra_control.providers.registry import capabilities_for


def system_timezone() -> str:
	tz: str = get_system_timezone()
	return tz


def iso_utc(value: Any) -> str | None:
	"""Naive system-timezone datetime (as Frappe stores it) -> RFC 3339 UTC with `Z`."""
	if value in (None, ""):
		return None
	dt: datetime | None = get_datetime(value)
	if dt is None:
		return None
	if dt.tzinfo is None:
		dt = dt.replace(tzinfo=ZoneInfo(system_timezone()))
	return dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json(value: Any) -> dict[str, Any]:
	if not value:
		return {}
	if isinstance(value, str):
		data = json.loads(value)
		return data if isinstance(data, dict) else {}
	return dict(value) if isinstance(value, dict) else {}


def _caps(provider: str) -> list[str]:
	return sorted(str(c) for c in capabilities_for(provider))


def target_ref(doctype: Any, name: Any) -> dict[str, str] | None:
	if not doctype or not name:
		return None
	return {"target_doctype": str(doctype), "target_name": str(name)}


# ----- inventory ---------------------------------------------------------------------------
SERVER_FIELDS = [
	"name",
	"hostname",
	"provider",
	"provider_account",
	"provider_ref",
	"public_ip",
	"private_ip",
	"role",
	"region",
	"size",
	"status",
	"last_heartbeat",
]


def server(row: dict[str, Any], *, tags: list[str], bench_count: int, site_count: int) -> dict[str, Any]:
	return {
		"name": row["name"],
		"hostname": row.get("hostname") or row["name"],
		"provider": row["provider"],
		"provider_account": row["provider_account"],
		"provider_ref": row.get("provider_ref") or "",
		"public_ip": row.get("public_ip") or None,
		"private_ip": row.get("private_ip") or None,
		"role": row.get("role") or "all",
		"region": row.get("region") or "",
		"size": row.get("size") or "",
		"tags": tags,
		"status": row["status"],
		"last_heartbeat": iso_utc(row.get("last_heartbeat")),
		"capabilities": _caps(row["provider"]),
		"bench_count": bench_count,
		"site_count": site_count,
	}


BENCH_FIELDS = [
	"name",
	"title",
	"provider",
	"provider_account",
	"provider_ref",
	"server",
	"path",
	"frappe_version",
]


def bench(row: dict[str, Any], *, apps: list[dict[str, Any]], site_count: int) -> dict[str, Any]:
	return {
		"name": row["name"],
		"title": row.get("title") or row["name"],
		"provider": row["provider"],
		"provider_account": row["provider_account"],
		"provider_ref": row.get("provider_ref") or "",
		"server": row.get("server") or None,
		"path": row.get("path") or None,
		"frappe_version": row.get("frappe_version") or None,
		"apps": [
			{"app": a["app"], "version": a.get("version") or None, "branch": a.get("branch") or None}
			for a in apps
		],
		"site_count": site_count,
		"capabilities": _caps(row["provider"]),
	}


SITE_FIELDS = [
	"name",
	"domain",
	"provider",
	"provider_account",
	"provider_ref",
	"bench",
	"server",
	"status",
	"plan",
	"ssl_expiry",
	"db_size_mb",
	"last_backup",
]


def site(row: dict[str, Any], *, custom_domains: list[str]) -> dict[str, Any]:
	return {
		"name": row["name"],
		"domain": row.get("domain") or row["name"],
		"provider": row["provider"],
		"provider_account": row["provider_account"],
		"provider_ref": row.get("provider_ref") or "",
		"bench": row["bench"],
		"server": row.get("server") or None,
		"status": row["status"],
		"plan": row.get("plan") or None,
		"ssl_expiry": iso_utc(row.get("ssl_expiry")),
		"db_size_mb": float(row["db_size_mb"]) if row.get("db_size_mb") not in (None, "") else None,
		"last_backup": iso_utc(row.get("last_backup")),
		"custom_domains": custom_domains,
		"capabilities": _caps(row["provider"]),
	}


def backup(row: dict[str, Any]) -> dict[str, Any]:
	result = row.get("restore_test_result") or ""
	return {
		"name": row["name"],
		"site": row["site"],
		"kind": row["kind"],
		"location": row.get("location") or "",
		"size_mb": float(row.get("size_mb") or 0),
		"created_at": iso_utc(row.get("created_at")) or iso_utc(row.get("creation")) or "",
		"last_restore_test": iso_utc(row.get("last_restore_test")),
		"restore_test_ok": None if not result else result == "ok",
	}


# ----- playbooks / jobs ----------------------------------------------------------------------
PLAYBOOK_FIELDS = [
	"name",
	"key",
	"title",
	"description",
	"target_doctype",
	"creates",
	"risk",
	"required_capability",
	"params_schema",
	"enabled",
]


def playbook(row: dict[str, Any]) -> dict[str, Any]:
	return {
		"key": row.get("key") or row["name"],
		"title": row["title"],
		"description": row.get("description") or "",
		"target_doctype": row["target_doctype"],
		"creates": row.get("creates") or None,
		"risk": row["risk"],
		"required_capability": row.get("required_capability") or None,
		"params_schema": _json(row.get("params_schema"))
		or {"type": "object", "additionalProperties": False, "properties": {}},
	}


JOB_FIELDS = [
	"name",
	"playbook",
	"playbook_title",
	"target_doctype",
	"target_name",
	"params",
	"status",
	"progress",
	"steps_done",
	"steps_total",
	"triggered_by",
	"bulk_operation",
	"retry_of",
	"created_doctype",
	"created_name",
	"cancel_requested",
	"creation",
	"started_at",
	"ended_at",
	"error",
]


def job(row: dict[str, Any]) -> dict[str, Any]:
	return {
		"name": row["name"],
		"playbook": row["playbook"],
		"playbook_title": row.get("playbook_title")
		or frappe.db.get_value("Playbook", row["playbook"], "title")
		or row["playbook"],
		"target_doctype": row["target_doctype"],
		"target_name": row["target_name"],
		"params": {k: v for k, v in _json(row.get("params")).items() if not k.startswith("_")},
		"status": row["status"],
		"progress": int(row.get("progress") or 0),
		"steps_done": int(row.get("steps_done") or 0),
		"steps_total": int(row.get("steps_total") or 0),
		"triggered_by": row.get("triggered_by") or "scheduler",
		"bulk_operation": row.get("bulk_operation") or None,
		"retry_of": row.get("retry_of") or None,
		"created": target_ref(row.get("created_doctype"), row.get("created_name")),
		"cancel_requested": bool(row.get("cancel_requested")),
		"created_at": iso_utc(row.get("creation")) or "",
		"started_at": iso_utc(row.get("started_at")),
		"ended_at": iso_utc(row.get("ended_at")),
		"error": row.get("error") or None,
	}


STEP_FIELDS = ["name", "step_index", "title", "status", "output", "started_at", "ended_at"]


def step(row: dict[str, Any]) -> dict[str, Any]:
	return {
		"idx": int(row["step_index"]),
		"title": row["title"],
		"status": row["status"],
		"output": row.get("output") or "",
		"started_at": iso_utc(row.get("started_at")),
		"ended_at": iso_utc(row.get("ended_at")),
	}


# ----- alerts --------------------------------------------------------------------------------
ALERT_FIELDS = [
	"name",
	"rule",
	"rule_title",
	"kind",
	"severity",
	"status",
	"target_doctype",
	"target_name",
	"metric",
	"value",
	"message",
	"fired_at",
	"acknowledged_by",
	"acknowledged_at",
	"resolved_at",
]


def alert(row: dict[str, Any]) -> dict[str, Any]:
	return {
		"name": row["name"],
		"rule": row["rule"],
		"rule_title": row.get("rule_title") or row["rule"],
		"kind": row.get("kind") or "metric",
		"severity": row["severity"],
		"status": row["status"],
		"target": target_ref(row.get("target_doctype"), row.get("target_name"))
		or {"target_doctype": "Server", "target_name": ""},
		"metric": row.get("metric") or None,
		"value": float(row["value"]) if row.get("value") not in (None, "") else None,
		"message": row.get("message") or "",
		"fired_at": iso_utc(row.get("fired_at")) or "",
		"acknowledged_by": row.get("acknowledged_by") or None,
		"acknowledged_at": iso_utc(row.get("acknowledged_at")),
		"resolved_at": iso_utc(row.get("resolved_at")),
	}
