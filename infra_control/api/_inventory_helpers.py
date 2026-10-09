"""Shared queries for inventory endpoints: counts, child tables, running jobs."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe

from infra_control.core.enums import JobStatus
from infra_control.job_engine.engine import READ_ONLY_PLAYBOOKS


def count_by(doctype: str, field: str, filters: dict[str, Any] | None = None) -> dict[str, int]:
	out: dict[str, int] = defaultdict(int)
	for row in frappe.get_all(doctype, filters=filters or {}, fields=[field]):
		out[str(row.get(field))] += 1
	return dict(out)


def child_values(
	parent_doctype: str, child_doctype: str, field: str, parents: list[str]
) -> dict[str, list[Any]]:
	out: dict[str, list[Any]] = defaultdict(list)
	if not parents:
		return {}
	for row in frappe.get_all(
		child_doctype,
		filters={"parenttype": parent_doctype, "parent": ["in", parents]},
		fields=["parent", field],
		order_by="idx asc",
	):
		out[str(row["parent"])].append(row[field])
	return dict(out)


def child_rows(
	parent_doctype: str, child_doctype: str, fields: list[str], parents: list[str]
) -> dict[str, list[dict[str, Any]]]:
	out: dict[str, list[dict[str, Any]]] = defaultdict(list)
	if not parents:
		return {}
	for row in frappe.get_all(
		child_doctype,
		filters={"parenttype": parent_doctype, "parent": ["in", parents]},
		fields=["parent", *fields],
		order_by="idx asc",
	):
		out[str(row["parent"])].append(dict(row))
	return dict(out)


def running_jobs() -> list[dict[str, Any]]:
	"""Running jobs with their target and the server lock they hold."""
	rows: list[dict[str, Any]] = frappe.get_all(
		"Infra Job",
		filters={"status": JobStatus.RUNNING, "playbook": ["not in", sorted(READ_ONLY_PLAYBOOKS)]},
		fields=["name", "target_doctype", "target_name", "lock_key"],
	)
	return rows


def running_job_for(
	target_doctype: str, target_name: str, server: str | None, jobs: list[dict[str, Any]] | None = None
) -> str | None:
	"""The running job on this target; for servers and benches also a job holding the server lock.

	Sites only report jobs that target them, so one migrate on a server does not light up every
	site on it in the topology.
	"""
	jobs = running_jobs() if jobs is None else jobs
	lock = f"infra:lock:server:{server}" if server and target_doctype in ("Server", "Bench") else None
	for j in jobs:
		if (j["target_doctype"], j["target_name"]) == (target_doctype, target_name):
			return str(j["name"])
		if lock and j.get("lock_key") == lock:
			return str(j["name"])
	return None
