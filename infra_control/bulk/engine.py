"""Bulk-operation shell (A3.4, plan 9.3): the Frappe side of the pure planner in `plan.py`.

A bulk operation runs one playbook over many targets with a safety sequence: back up every
target, run a single canary, then the rest in batches, with health checks after each batch and a
`failure_policy` that can halt the rollout. It never touches a provider itself — every unit of
work is a child `Infra Job` run through the job engine, so the one-job-per-server lock, masking,
audit and realtime all apply unchanged.

The driver (`drive`) executes exactly one unit per invocation — all backups, the canary, or one
batch — then re-enqueues itself. Running one unit at a time keeps pause and cancel responsive and
means no single background task runs unbounded. `plan.next_action` decides what that unit is.
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe.utils import now_datetime

from infra_control.bulk import health, plan
from infra_control.bulk.plan import ActionKind
from infra_control.core import audit
from infra_control.core.enums import (
	TERMINAL_BULK_STATUSES,
	AuditResult,
	BulkPhase,
	BulkStatus,
	BulkTargetStatus,
	FailurePolicy,
	JobStatus,
	Risk,
	TargetDoctype,
)
from infra_control.core.errors import InvalidState, NotFound, ValidationError
from infra_control.core.permissions import require_risk
from infra_control.job_engine import engine as jobs
from infra_control.job_engine import realtime

BACKUP_PLAYBOOK = "site.backup"
TARGET_ROW_FIELDS = ["name", "target_doctype", "target_name", "status", "job", "batch", "idx"]

# Statuses from which the driver is not actively progressing the rollout.
_PAUSED_OR_TERMINAL: frozenset[BulkStatus] = TERMINAL_BULK_STATUSES | {BulkStatus.PAUSED, BulkStatus.HALTED}


# ---------------------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------------------
def create_bulk(
	playbook: str,
	targets: list[dict[str, str]],
	canary_target: dict[str, str],
	batch_size: int,
	failure_policy: str | FailurePolicy,
	params: dict[str, Any] | None = None,
	confirm: str | None = None,
	*,
	user: str | None = None,
) -> Any:
	"""Validate, create the Bulk Operation (Queued/backup), assign batches and enqueue the driver."""
	user = user or frappe.session.user
	params = dict(params or {})
	policy = FailurePolicy(failure_policy)
	if batch_size < 1:
		raise ValidationError("batch_size must be >= 1", {"field": "batch_size"})
	if not targets:
		raise ValidationError("At least one target is required", {"field": "targets"})

	if not frappe.db.exists("Playbook", playbook):
		raise NotFound("Playbook", playbook)
	pb: Any = frappe.get_doc("Playbook", playbook)
	if not pb.enabled:
		raise InvalidState(f"Playbook {playbook} is disabled", {"playbook": playbook})

	for target in targets:
		if target.get("target_doctype") != pb.target_doctype:
			raise ValidationError(
				f"Playbook {playbook} targets a {pb.target_doctype}, not a {target.get('target_doctype')}",
				{"field": "targets", "expected": pb.target_doctype},
			)
	if not any(_same(target, canary_target) for target in targets):
		raise ValidationError("canary_target must be one of targets", {"field": "canary_target"})

	# High-risk playbooks need Infra Admin and a typed confirmation (contract: "<key>:<count>").
	require_risk(pb.risk, user)
	expected = f"{playbook}:{len(targets)}"
	jobs.check_confirmation(pb.risk, expected, confirm)

	assignments, batches_total = plan.plan_batches(
		[(_s(t, "target_doctype"), _s(t, "target_name")) for t in targets],
		(_s(canary_target, "target_doctype"), _s(canary_target, "target_name")),
		batch_size,
	)
	rows = [
		{
			"target_doctype": _s(t, "target_doctype"),
			"target_name": _s(t, "target_name"),
			"status": str(BulkTargetStatus.PENDING),
			"batch": batch,
		}
		for t, batch in zip(targets, assignments, strict=True)
	]
	bulk: Any = frappe.get_doc(
		{
			"doctype": "Bulk Operation",
			"playbook": playbook,
			"playbook_title": pb.title,
			"status": str(BulkStatus.QUEUED),
			"phase": str(BulkPhase.BACKUP),
			"failure_policy": str(policy),
			"batch_size": batch_size,
			"triggered_by": user,
			"canary_doctype": _s(canary_target, "target_doctype"),
			"canary_name": _s(canary_target, "target_name"),
			"total": len(targets),
			"done": 0,
			"failed": 0,
			"current_batch": 0,
			"batches_total": batches_total,
			"params": json.dumps(params),
			"targets": rows,
		}
	)
	bulk.flags.ignore_permissions = True
	bulk.insert()
	audit.record(
		f"bulk.create:{playbook}",
		result=AuditResult.SUCCESS,
		target_doctype=_s(canary_target, "target_doctype"),
		target_name=_s(canary_target, "target_name"),
		params=params,
		user=user,
	)
	_emit(bulk)
	_enqueue_drive(bulk.name)
	return bulk


# ---------------------------------------------------------------------------------------
# drive: the RQ worker entry point (one unit per invocation)
# ---------------------------------------------------------------------------------------
def drive(bulk_name: str) -> None:
	doc = _get_bulk(bulk_name)
	status = BulkStatus(doc.status)
	if status in _PAUSED_OR_TERMINAL:
		return
	if status is BulkStatus.QUEUED:
		values: dict[str, Any] = {"status": str(BulkStatus.RUNNING)}
		if not doc.started_at:
			values["started_at"] = now_datetime()
		doc.db_set(values)
		_checkpoint()
		_emit(doc)
	action = plan.next_action(_state(doc))
	_dispatch(doc, action)


def _dispatch(doc: Any, action: plan.Action) -> None:
	if action.kind is ActionKind.RUN_BACKUPS:
		if not _run_backups(doc):
			return  # a failed backup halts the whole operation (updates back up first)
		doc.db_set("phase", str(BulkPhase.CANARY))
		_checkpoint()
		_enqueue_drive(doc.name)
	elif action.kind is ActionKind.RUN_CANARY:
		_run_canary(doc)
		_enqueue_drive(doc.name)
	elif action.kind is ActionKind.RUN_BATCH:
		assert action.batch is not None
		_run_batch(doc, action.batch)
		_enqueue_drive(doc.name)
	elif action.kind is ActionKind.FINISH:
		assert action.status is not None
		if action.status is BulkStatus.PAUSED:
			_set_paused(doc)
		else:
			_finish(doc, action.status)


# ---------------------------------------------------------------------------------------
# units of work
# ---------------------------------------------------------------------------------------
def _run_backups(doc: Any) -> bool:
	"""Back up every Site target before anything runs. A failed backup halts the operation."""
	for row in _rows(doc.name):
		if str(row["target_doctype"]) != TargetDoctype.SITE:
			continue
		if not _run_child(doc, BACKUP_PLAYBOOK, str(row["target_doctype"]), str(row["target_name"])):
			_finish(doc, BulkStatus.HALTED)
			return False
	return True


def _run_canary(doc: Any) -> None:
	doc.db_set({"phase": str(BulkPhase.CANARY), "current_batch": plan.CANARY_BATCH})
	_checkpoint()
	_emit(doc)
	canary = next((r for r in _rows(doc.name) if int(r["batch"]) == plan.CANARY_BATCH), None)
	if canary is not None:
		_run_target(doc, canary)


def _run_batch(doc: Any, batch: int) -> None:
	doc.db_set({"phase": str(BulkPhase.BATCHES), "current_batch": batch})
	_checkpoint()
	_emit(doc)
	pending = [
		r
		for r in _rows(doc.name)
		if int(r["batch"]) == batch and BulkTargetStatus(str(r["status"])) is BulkTargetStatus.PENDING
	]
	for row in _by_server(pending):
		_run_target(doc, row)
		doc.reload()
		if doc.cancel_requested:
			return  # stop after the current target; next_action turns this into Cancelled
	if not _skip_health(doc):
		_health_checks(doc, batch)


def _run_target(doc: Any, row: dict[str, Any]) -> None:
	"""Run one target's child job synchronously, record the result and emit after every target."""
	name = str(row["name"])
	frappe.db.set_value("Bulk Operation Target", name, "status", str(BulkTargetStatus.RUNNING))
	ok = _run_child(
		doc,
		str(doc.playbook),
		str(row["target_doctype"]),
		str(row["target_name"]),
		row_name=name,
	)
	frappe.db.set_value(
		"Bulk Operation Target",
		name,
		"status",
		str(BulkTargetStatus.SUCCESS if ok else BulkTargetStatus.FAILED),
	)
	_recount(doc)
	_checkpoint()
	_emit(doc)


def _run_child(
	doc: Any, playbook: str, target_doctype: str, target_name: str, *, row_name: str | None = None
) -> bool:
	"""Create and run a child Infra Job linked back to this bulk; return whether it succeeded."""
	try:
		risk = frappe.db.get_value("Playbook", playbook, "risk")
		confirm = target_name if risk and Risk(risk) is Risk.HIGH else None
		child: Any = jobs.create_job(
			playbook,
			target_doctype,
			target_name,
			params=_params(doc),
			confirm=confirm,
			user=str(doc.triggered_by),
			enqueue=False,
			bulk_operation=str(doc.name),
		)
		if row_name is not None:
			frappe.db.set_value("Bulk Operation Target", row_name, "job", child.name)
		jobs.run_job(child.name)
		status = frappe.db.get_value("Infra Job", child.name, "status")
		return bool(status) and JobStatus(str(status)) is JobStatus.SUCCESS
	except Exception as exc:
		frappe.log_error(
			title=f"Bulk {doc.name} child job failed", message=f"{playbook} {target_name}: {exc}"
		)
		return False


def _health_checks(doc: Any, batch: int) -> None:
	"""After a batch, probe each successful target; a failed probe folds into the failure policy."""
	degraded = False
	for row in _rows(doc.name):
		if int(row["batch"]) != batch:
			continue
		if BulkTargetStatus(str(row["status"])) is not BulkTargetStatus.SUCCESS:
			continue
		ok, detail = health.check_target(str(row["target_doctype"]), str(row["target_name"]))
		if not ok:
			frappe.log_error(
				title=f"Bulk {doc.name} health check failed",
				message=f"{row['target_name']}: {detail}",
			)
			frappe.db.set_value(
				"Bulk Operation Target", str(row["name"]), "status", str(BulkTargetStatus.FAILED)
			)
			degraded = True
	if degraded:
		_recount(doc)
		_checkpoint()
		_emit(doc)


# ---------------------------------------------------------------------------------------
# pause / resume / cancel
# ---------------------------------------------------------------------------------------
def pause(bulk_name: str, *, user: str | None = None) -> Any:
	"""Request a pause; the driver stops at the next batch boundary (status becomes Paused)."""
	doc = _get_bulk(bulk_name)
	if BulkStatus(doc.status) not in (BulkStatus.QUEUED, BulkStatus.RUNNING):
		raise InvalidState(f"Cannot pause a {doc.status} bulk operation", {"status": doc.status})
	doc.db_set("pause_requested", 1)
	_checkpoint()
	return doc


def resume(bulk_name: str, *, user: str | None = None) -> Any:
	"""Resume a paused or halted bulk operation with its remaining targets."""
	doc = _get_bulk(bulk_name)
	if BulkStatus(doc.status) not in (BulkStatus.PAUSED, BulkStatus.HALTED):
		raise InvalidState(f"Cannot resume a {doc.status} bulk operation", {"status": doc.status})
	for row in _rows(doc.name):
		if BulkTargetStatus(str(row["status"])) is BulkTargetStatus.SKIPPED:
			frappe.db.set_value(
				"Bulk Operation Target", str(row["name"]), "status", str(BulkTargetStatus.PENDING)
			)
	_recount(doc)
	doc.db_set({"status": str(BulkStatus.RUNNING), "pause_requested": 0, "ended_at": None})
	_checkpoint()
	_emit(doc)
	_enqueue_drive(doc.name)
	return doc


def cancel(bulk_name: str, *, user: str | None = None) -> Any:
	"""Cancel: the running target finishes, the rest are skipped and the operation ends Cancelled."""
	doc = _get_bulk(bulk_name)
	status = BulkStatus(doc.status)
	if status not in (BulkStatus.QUEUED, BulkStatus.RUNNING, BulkStatus.PAUSED, BulkStatus.HALTED):
		raise InvalidState(f"Cannot cancel a {doc.status} bulk operation", {"status": doc.status})
	doc.db_set("cancel_requested", 1)
	audit.record(
		f"bulk.cancel:{doc.playbook}",
		result=AuditResult.SUCCESS,
		target_doctype=str(doc.canary_doctype),
		target_name=str(doc.canary_name),
		user=user,
	)
	if status is BulkStatus.RUNNING:
		_checkpoint()
		return doc  # a live driver observes the flag and finalises after the current target
	_finish(doc, BulkStatus.CANCELLED)
	return doc


# ---------------------------------------------------------------------------------------
# crash recovery (wired into job_engine.recovery.run)
# ---------------------------------------------------------------------------------------
def requeue_running() -> list[str]:
	"""Re-enqueue the driver for every Running bulk whose worker may have died. Idempotent: the
	driver re-reads state, and the shared `job_name` dedups a driver still queued."""
	names = [
		str(n)
		for n in frappe.get_all("Bulk Operation", filters={"status": str(BulkStatus.RUNNING)}, pluck="name")
	]
	for name in names:
		_enqueue_drive(name)
	return names


# ---------------------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------------------
def _finish(doc: Any, status: BulkStatus) -> None:
	"""Terminal/halted finish: skip anything still pending, set counters, status and ended_at."""
	if status in (BulkStatus.HALTED, BulkStatus.CANCELLED):
		for row in _rows(doc.name):
			if BulkTargetStatus(str(row["status"])) in (BulkTargetStatus.PENDING, BulkTargetStatus.RUNNING):
				frappe.db.set_value(
					"Bulk Operation Target", str(row["name"]), "status", str(BulkTargetStatus.SKIPPED)
				)
	_recount(doc)
	doc.db_set({"status": str(status), "phase": str(BulkPhase.DONE), "ended_at": now_datetime()})
	_checkpoint()
	_emit(doc)


def _set_paused(doc: Any) -> None:
	doc.db_set({"status": str(BulkStatus.PAUSED), "pause_requested": 0})
	_checkpoint()
	_emit(doc)


def _state(doc: Any) -> plan.BulkState:
	rows = _rows(doc.name)
	snapshots = tuple(
		plan.TargetSnapshot(batch=int(r["batch"]), status=BulkTargetStatus(str(r["status"]))) for r in rows
	)
	return plan.BulkState(
		failure_policy=FailurePolicy(doc.failure_policy),
		targets=snapshots,
		cancel_requested=bool(doc.cancel_requested),
		pause_requested=bool(doc.pause_requested),
		backup_needed=_backup_needed(doc, rows),
		backup_done=BulkPhase(doc.phase) is not BulkPhase.BACKUP,
	)


def _backup_needed(doc: Any, rows: list[dict[str, Any]]) -> bool:
	"""Back up first unless the playbook is itself a backup; only Site targets can be backed up."""
	if "backup" in str(doc.playbook).lower():
		return False
	return any(str(r["target_doctype"]) == TargetDoctype.SITE for r in rows)


def _recount(doc: Any) -> None:
	rows = _rows(doc.name)
	terminal = (BulkTargetStatus.SUCCESS, BulkTargetStatus.FAILED, BulkTargetStatus.SKIPPED)
	done = sum(1 for r in rows if BulkTargetStatus(str(r["status"])) in terminal)
	failed = sum(1 for r in rows if BulkTargetStatus(str(r["status"])) is BulkTargetStatus.FAILED)
	doc.db_set({"done": done, "failed": failed})


def _by_server(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""Order a batch so same-server targets are adjacent (sequential within a server, per plan 9.3)."""

	def key(row: dict[str, Any]) -> str:
		try:
			return jobs.lock_key_for(jobs.resolve_target(str(row["target_doctype"]), str(row["target_name"])))
		except Exception:
			return str(row["target_name"])

	return sorted(rows, key=key)


def _rows(bulk_name: str) -> list[dict[str, Any]]:
	return [
		dict(r)
		for r in frappe.get_all(
			"Bulk Operation Target",
			filters={"parent": bulk_name},
			fields=TARGET_ROW_FIELDS,
			order_by="batch asc, idx asc",
		)
	]


def _params(doc: Any) -> dict[str, Any]:
	raw = doc.params
	if not raw:
		return {}
	data: Any = json.loads(raw) if isinstance(raw, str) else raw
	return dict(data) if isinstance(data, dict) else {}


def _skip_health(doc: Any) -> bool:
	return bool(_params(doc).get("_skip_health"))


def _emit(doc: Any) -> None:
	realtime.emit(
		*realtime.bulk_updated(
			str(doc.name),
			str(doc.status),
			int(doc.done or 0),
			int(doc.total or 0),
			int(doc.current_batch or 0),
		)
	)


def _enqueue_drive(bulk_name: str) -> None:
	frappe.enqueue(
		"infra_control.bulk.engine.drive",
		queue=jobs.QUEUE,
		job_name=f"infra_bulk:{bulk_name}",
		enqueue_after_commit=True,
		bulk_name=bulk_name,
	)


def _checkpoint() -> None:
	frappe.db.commit()


def _get_bulk(bulk_name: str) -> Any:
	if not frappe.db.exists("Bulk Operation", bulk_name):
		raise NotFound("Bulk Operation", bulk_name)
	return frappe.get_doc("Bulk Operation", bulk_name)


def _same(a: dict[str, str], b: dict[str, str]) -> bool:
	return _s(a, "target_doctype") == _s(b, "target_doctype") and _s(a, "target_name") == _s(b, "target_name")


def _s(ref: dict[str, Any], key: str) -> str:
	return str(ref.get(key) or "")


__all__ = ["cancel", "create_bulk", "drive", "pause", "requeue_running", "resume"]
