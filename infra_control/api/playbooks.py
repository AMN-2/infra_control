"""playbooks.list: the catalogue filtered by target type and the target's capabilities."""

from __future__ import annotations

from typing import Any

import frappe

from infra_control.api import _serialize as ser
from infra_control.api import api, enum_param
from infra_control.core.enums import TargetDoctype
from infra_control.job_engine.engine import resolve_target
from infra_control.providers.registry import capabilities_for


@api()
def list(target_doctype: str | None = None, target_name: str | None = None) -> dict[str, Any]:
	filters: dict[str, Any] = {"enabled": 1}
	if dt := enum_param("target_doctype", target_doctype, TargetDoctype):
		filters["target_doctype"] = dt
	rows = frappe.get_all("Playbook", filters=filters, fields=ser.PLAYBOOK_FIELDS, order_by="name asc")
	if target_name:
		if not dt:
			from infra_control.core.errors import ValidationError

			raise ValidationError("target_doctype is required with target_name", {"field": "target_doctype"})
		caps = {str(c) for c in capabilities_for(resolve_target(dt, target_name).provider)}
		rows = [r for r in rows if not r.get("required_capability") or r["required_capability"] in caps]
	return {"items": [ser.playbook(r) for r in rows]}
