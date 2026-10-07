"""Immutable audit log (plan section 5, security requirement 8).

`record()` is the only writer. Params are hashed, never stored. Rows can be created but never
updated or deleted, enforced by the DocType permissions (no role has write/delete) and by the
controller in `infra_control/infra_control/doctype/infra_audit_log/`.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import frappe
from frappe.utils import now_datetime

from infra_control.core.enums import AuditResult


def params_hash(params: dict[str, Any] | None) -> str:
	"""SHA-256 of the canonical JSON (sorted keys, no whitespace, UTF-8) of `params` (`{}` if None)."""
	canonical = json.dumps(params or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
	return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def record(
	action: str,
	*,
	result: AuditResult | str,
	target_doctype: str | None = None,
	target_name: str | None = None,
	params: dict[str, Any] | None = None,
	job: str | None = None,
	user: str | None = None,
) -> str:
	"""Insert one `Infra Audit Log` row and return its name. Commits nothing; the caller's request does."""
	doc = frappe.get_doc(
		{
			"doctype": "Infra Audit Log",
			"ts": now_datetime(),
			"user": user or frappe.session.user,
			"action": action,
			"result": str(AuditResult(result)),
			"target_doctype": target_doctype,
			"target_name": target_name,
			"job": job,
			"params_hash": params_hash(params),
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	name: str = doc.name
	return name
