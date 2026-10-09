"""Preflight for a bulk rollout (ADR 0009): per target, is the playbook going to run?

Pure reads: the document exists and is the playbook's target type, the provider has the
capability, the target's status allows work, nothing holds its lock, a Site has a recent
backup, and (on request) the target answers a ping. Every check is `pass`, `warn` or `fail`;
a target with any `fail` is reported `ok = false`. The engine re-validates on create anyway;
this is the operator's view before committing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import frappe

from infra_control.api._inventory_helpers import running_job_for
from infra_control.bulk import health
from infra_control.core.enums import TargetDoctype
from infra_control.core.errors import NotFound, ValidationError
from infra_control.job_engine.engine import resolve_target
from infra_control.providers.registry import capabilities_for

STALE_BACKUP_HOURS = 36
BLOCKED_STATUS: dict[str, set[str]] = {
	TargetDoctype.SITE: {"Archived", "Broken", "Pending"},
	TargetDoctype.SERVER: {"Archived", "Down", "Provisioning"},
}


def _check(id_: str, status: str, detail: str) -> dict[str, str]:
	return {"id": id_, "status": status, "detail": detail}


def _age_hours(value: Any, now: datetime) -> float | None:
	if not value:
		return None
	ts = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
	if ts.tzinfo is not None:
		ts = ts.astimezone(UTC).replace(tzinfo=None)
	return (now - ts).total_seconds() / 3600


def check_target(pb: Any, doctype: str, name: str, *, ping: bool, now: datetime) -> dict[str, Any]:
	checks: list[dict[str, str]] = []
	try:
		target = resolve_target(doctype, name)
	except (NotFound, ValidationError) as exc:
		checks.append(_check("exists", "fail", exc.message))
		return {"target_doctype": doctype, "target_name": name, "ok": False, "checks": checks}
	checks.append(_check("exists", "pass", f"{doctype} {name} on {target.provider}"))

	if str(pb.target_doctype) != doctype:
		checks.append(_check("playbook_target", "fail", f"{pb.name} targets a {pb.target_doctype}"))
	else:
		checks.append(_check("playbook_target", "pass", f"{pb.name} runs on a {doctype}"))

	caps = {str(c) for c in capabilities_for(target.provider)}
	if pb.required_capability and str(pb.required_capability) not in caps:
		checks.append(_check("capability", "fail", f"{target.provider} lacks {pb.required_capability}"))
	else:
		checks.append(_check("capability", "pass", pb.required_capability or "no capability needed"))

	doc: Any = frappe.get_doc(doctype, name)
	status = str(doc.get("status") or "")
	if doctype in BLOCKED_STATUS and status in BLOCKED_STATUS[doctype]:
		checks.append(_check("status", "fail", f"status is {status}"))
	elif doctype == TargetDoctype.BENCH and target.server:
		server_status = str(frappe.db.get_value("Server", target.server, "status") or "")
		if server_status in BLOCKED_STATUS[TargetDoctype.SERVER]:
			checks.append(_check("status", "fail", f"server {target.server} is {server_status}"))
		else:
			checks.append(_check("status", "pass", f"server {target.server} is {server_status or 'unknown'}"))
	else:
		checks.append(_check("status", "pass", status or "n/a"))

	job = running_job_for(doctype, name, target.server)
	if job:
		checks.append(_check("lock", "warn", f"{job} holds the lock; the rollout waits for it"))
	else:
		checks.append(_check("lock", "pass", "no running job"))

	if doctype == TargetDoctype.SITE:
		age = _age_hours(doc.get("last_backup"), now)
		if age is None:
			checks.append(_check("backup", "warn", "never backed up; the rollout backs up first"))
		elif age > STALE_BACKUP_HOURS:
			checks.append(
				_check("backup", "warn", f"last backup {age / 24:.1f} days ago; the rollout backs up first")
			)
		else:
			checks.append(_check("backup", "pass", f"last backup {age:.0f} h ago"))

	if ping and doctype in (TargetDoctype.SITE, TargetDoctype.SERVER):
		ok, detail = health.check_target(doctype, name)
		checks.append(_check("health", "pass" if ok else "fail", detail))

	return {
		"target_doctype": doctype,
		"target_name": name,
		"ok": all(c["status"] != "fail" for c in checks),
		"checks": checks,
	}


def preflight(playbook: str, targets: list[dict[str, str]], *, ping: bool = False) -> dict[str, Any]:
	if not frappe.db.exists("Playbook", playbook):
		raise NotFound("Playbook", playbook)
	pb: Any = frappe.get_doc("Playbook", playbook)
	now = datetime.now(UTC).replace(tzinfo=None)
	items = [check_target(pb, t["target_doctype"], t["target_name"], ping=ping, now=now) for t in targets]
	return {
		"playbook": playbook,
		"items": items,
		"summary": {
			"ok": sum(1 for i in items if i["ok"]),
			"warn": sum(1 for i in items if i["ok"] and any(c["status"] == "warn" for c in i["checks"])),
			"fail": sum(1 for i in items if not i["ok"]),
		},
	}
