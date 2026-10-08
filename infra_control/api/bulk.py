"""bulk.create / pause / resume / cancel / get / list (A3.4): thin wrappers over `bulk.engine`.

The handlers validate and shape; all orchestration and provider work happens in the job engine
through the bulk driver. Bodies match `contracts/openapi.yaml`: `{ "bulk": BulkOperation }` for
the mutating endpoints and `BulkOperationDetail` (with `targets`) for `get`.
"""

from __future__ import annotations

import builtins
import json
from typing import Any

import frappe

from infra_control.api import _serialize as ser
from infra_control.api import api, dict_param, enum_param, int_param, str_param
from infra_control.api._pagination import LIMIT_DEFAULT, LIMIT_MAX, page_newest_first
from infra_control.bulk import engine as bulk_engine
from infra_control.core.enums import BulkStatus, FailurePolicy, TargetDoctype
from infra_control.core.errors import NotFound, ValidationError
from infra_control.core.permissions import INFRA_OPERATOR


def _bulk_row(name: str) -> dict[str, Any]:
	rows = frappe.get_all("Bulk Operation", filters={"name": name}, fields=ser.BULK_FIELDS, limit=1)
	if not rows:
		raise NotFound("Bulk Operation", name)
	return dict(rows[0])


def _target_ref(name: str, value: Any, *, required: bool = False) -> dict[str, str] | None:
	"""Parse one TargetRef ({target_doctype, target_name}); validates the doctype enum."""
	if value in (None, ""):
		if required:
			raise ValidationError(f"{name} is required", {"field": name})
		return None
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except ValueError:
			raise ValidationError(f"{name} must be a TargetRef object", {"field": name}) from None
	if not isinstance(value, dict):
		raise ValidationError(f"{name} must be an object", {"field": name})
	doctype = enum_param(f"{name}.target_doctype", value.get("target_doctype"), TargetDoctype)
	target_name = str_param(f"{name}.target_name", value.get("target_name"), required=True)
	if not doctype:
		raise ValidationError(f"{name}.target_doctype is required", {"field": f"{name}.target_doctype"})
	assert target_name is not None
	return {"target_doctype": doctype, "target_name": target_name}


def _target_list(name: str, value: Any) -> builtins.list[dict[str, str]]:
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except ValueError:
			raise ValidationError(f"{name} must be a list of TargetRef", {"field": name}) from None
	if not isinstance(value, builtins.list) or not value:
		raise ValidationError(f"{name} must be a non-empty list", {"field": name})
	refs: builtins.list[dict[str, str]] = []
	for item in value:
		ref = _target_ref(name, item, required=True)
		assert ref is not None
		refs.append(ref)
	return refs


@api(methods=("POST",), role=INFRA_OPERATOR)
def create(
	playbook: str | None = None,
	targets: Any = None,
	canary_target: Any = None,
	batch_size: Any = None,
	failure_policy: str | None = None,
	params: Any = None,
	confirm: str | None = None,
) -> dict[str, Any]:
	key = str_param("playbook", playbook, required=True)
	assert key is not None
	refs = _target_list("targets", targets)
	canary = _target_ref("canary_target", canary_target, required=True)
	assert canary is not None
	size = int_param("batch_size", batch_size, default=5, minimum=1, maximum=50)
	policy = enum_param("failure_policy", failure_policy, FailurePolicy) or str(FailurePolicy.HALT)
	bulk = bulk_engine.create_bulk(
		key, refs, canary, size, policy, dict_param("params", params), str_param("confirm", confirm)
	)
	return {"bulk": ser.bulk(_bulk_row(bulk.name))}


@api(methods=("POST",), role=INFRA_OPERATOR)
def pause(bulk: str | None = None) -> dict[str, Any]:
	name = str_param("bulk", bulk, required=True)
	assert name is not None
	bulk_engine.pause(name)
	return {"bulk": ser.bulk(_bulk_row(name))}


@api(methods=("POST",), role=INFRA_OPERATOR)
def resume(bulk: str | None = None) -> dict[str, Any]:
	name = str_param("bulk", bulk, required=True)
	assert name is not None
	bulk_engine.resume(name)
	return {"bulk": ser.bulk(_bulk_row(name))}


@api(methods=("POST",), role=INFRA_OPERATOR)
def cancel(bulk: str | None = None) -> dict[str, Any]:
	name = str_param("bulk", bulk, required=True)
	assert name is not None
	bulk_engine.cancel(name)
	return {"bulk": ser.bulk(_bulk_row(name))}


@api()
def get(bulk: str | None = None) -> dict[str, Any]:
	name = str_param("bulk", bulk, required=True)
	assert name is not None
	out = ser.bulk(_bulk_row(name))
	targets = frappe.get_all(
		"Bulk Operation Target",
		filters={"parent": name},
		fields=ser.BULK_TARGET_FIELDS,
		order_by="batch asc, idx asc",
	)
	out["targets"] = [ser.bulk_target(dict(t)) for t in targets]
	return out


@api()
def list(
	status: str | None = None,
	playbook: str | None = None,
	limit: Any = None,
	cursor: str | None = None,
) -> dict[str, Any]:
	"""Summary rows newest first (no targets); the detail is `bulk.get`."""
	filters: dict[str, Any] = {}
	if s := enum_param("status", status, BulkStatus):
		filters["status"] = s
	if key := str_param("playbook", playbook):
		filters["playbook"] = key
	return page_newest_first(
		"Bulk Operation",
		filters=filters,
		fields=ser.BULK_FIELDS,
		limit=int_param("limit", limit, default=LIMIT_DEFAULT, minimum=1, maximum=LIMIT_MAX),
		cursor=cursor,
		serialize=ser.bulk,
	)
