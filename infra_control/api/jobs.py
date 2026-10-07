"""jobs.list / jobs.get (A1.4) and the thin jobs.run / cancel / retry wrappers over the engine."""

from __future__ import annotations

from typing import Any

import frappe

from infra_control.api import _serialize as ser
from infra_control.api import api, dict_param, enum_param, int_param, str_param
from infra_control.api._pagination import LIMIT_DEFAULT, LIMIT_MAX, page_newest_first
from infra_control.core.enums import JobStatus, TargetDoctype
from infra_control.core.errors import NotFound
from infra_control.core.permissions import INFRA_OPERATOR
from infra_control.job_engine import engine


@api()
def list(
	status: str | None = None,
	playbook: str | None = None,
	target_doctype: str | None = None,
	target_name: str | None = None,
	bulk_operation: str | None = None,
	limit: Any = None,
	cursor: str | None = None,
) -> dict[str, Any]:
	filters: dict[str, Any] = {}
	if s := enum_param("status", status, JobStatus):
		filters["status"] = s
	if dt := enum_param("target_doctype", target_doctype, TargetDoctype):
		filters["target_doctype"] = dt
	for key, value in (
		("playbook", playbook),
		("target_name", target_name),
		("bulk_operation", bulk_operation),
	):
		if value:
			filters[key] = value
	return page_newest_first(
		"Infra Job",
		filters=filters,
		fields=ser.JOB_FIELDS,
		limit=int_param("limit", limit, default=LIMIT_DEFAULT, minimum=1, maximum=LIMIT_MAX),
		cursor=cursor,
		serialize=ser.job,
	)


def _job_row(name: str) -> dict[str, Any]:
	rows = frappe.get_all("Infra Job", filters={"name": name}, fields=ser.JOB_FIELDS, limit=1)
	if not rows:
		raise NotFound("Infra Job", name)
	return dict(rows[0])


@api()
def get(job: str | None = None) -> dict[str, Any]:
	name = str_param("job", job, required=True)
	assert name is not None
	out = ser.job(_job_row(name))
	steps = frappe.get_all(
		"Infra Job Step", filters={"job": name}, fields=ser.STEP_FIELDS, order_by="step_index asc"
	)
	out["steps"] = [ser.step(s) for s in steps]
	return out


@api(methods=("POST",), role=INFRA_OPERATOR)
def run(
	playbook: str | None = None,
	target_doctype: str | None = None,
	target_name: str | None = None,
	params: Any = None,
	confirm: str | None = None,
) -> dict[str, Any]:
	key = str_param("playbook", playbook, required=True)
	dt = str_param("target_doctype", target_doctype, required=True)
	name = str_param("target_name", target_name, required=True)
	assert key and dt and name
	job = engine.create_job(key, dt, name, dict_param("params", params), str_param("confirm", confirm))
	return {"job": ser.job(_job_row(job.name))}


@api(methods=("POST",), role=INFRA_OPERATOR)
def cancel(job: str | None = None) -> dict[str, Any]:
	name = str_param("job", job, required=True)
	assert name is not None
	engine.cancel_job(name)
	return {"job": ser.job(_job_row(name))}


@api(methods=("POST",), role=INFRA_OPERATOR)
def retry(job: str | None = None) -> dict[str, Any]:
	name = str_param("job", job, required=True)
	assert name is not None
	new = engine.retry_job(name)
	return {"job": ser.job(_job_row(new.name))}
