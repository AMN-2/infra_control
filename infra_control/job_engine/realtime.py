"""Builders for the `infra:*` realtime payloads (contracts/events) and the single emit point.

A contract test validates every builder's output against its JSON schema, so the backend can
never emit a shape the frontend was not generated for.
"""

from __future__ import annotations

from typing import Any

import frappe

from infra_control.core.enums import JobStatus, StepStatus

LOG_CHUNK_MAX = 4096


def job_updated(job: str, status: JobStatus | str, progress: int) -> tuple[str, dict[str, Any]]:
	return "infra:job.updated", {
		"job": job,
		"status": str(JobStatus(status)),
		"progress": max(0, min(100, int(progress))),
	}


def job_step(job: str, idx: int, title: str, status: StepStatus | str) -> tuple[str, dict[str, Any]]:
	return "infra:job.step", {"job": job, "idx": int(idx), "title": title, "status": str(StepStatus(status))}


def job_log(job: str, idx: int, chunk: str) -> tuple[str, dict[str, Any]]:
	"""`chunk` must already be masked; it is cut to the last 4 KB (contract maxLength)."""
	return "infra:job.log", {"job": job, "idx": int(idx), "chunk": chunk[-LOG_CHUNK_MAX:]}


def bulk_updated(
	bulk: str, status: str, done: int, total: int, current_batch: int
) -> tuple[str, dict[str, Any]]:
	return "infra:bulk.updated", {
		"bulk": bulk,
		"status": status,
		"done": done,
		"total": total,
		"current_batch": current_batch,
	}


def inventory_changed(doctype: str, name: str, change: str) -> tuple[str, dict[str, Any]]:
	return "infra:inventory.changed", {"doctype": doctype, "name": name, "change": change}


def emit(event: str, payload: dict[str, Any]) -> None:
	"""Publish to the site room (docs/QUESTIONS.md Q3): every System User on the control plane."""
	frappe.publish_realtime(event, payload)
