"""The job engine (plan section 9.1).

- `create_job()`  : validation, audit, Infra Job (Queued), enqueue on the `infra` RQ queue.
- `run_job()`     : worker entry point: lock, resolve provider, call, poll, steps, masking,
                    realtime, terminal state, lock release.
- `cancel_job()`  : flag the job; a Queued job is cancelled at once, a Running one when the
                    worker observes the flag.
- `retry_job()`   : new job linked to the failed one, resuming from its first failed step.
- `fail_stale_jobs()`: crash recovery; Running jobs without a heartbeat are failed and unlocked.

Nothing here talks to DigitalOcean, Press or SSH: every mutation goes through `Provider.call`.
"""

from __future__ import annotations

import contextlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import frappe
import jsonschema
from frappe.utils import add_to_date, get_datetime, get_system_timezone, now_datetime

from infra_control.core import audit
from infra_control.core.enums import (
	TERMINAL_JOB_STATUSES,
	AuditResult,
	JobStatus,
	Risk,
	StepStatus,
	TargetDoctype,
)
from infra_control.core.errors import (
	ConfirmationRequired,
	InternalError,
	InvalidState,
	NotFound,
	NotSupported,
	PermissionDenied,
	ValidationError,
)
from infra_control.core.permissions import require_risk
from infra_control.job_engine import locks, realtime
from infra_control.job_engine.masking import mask_params, mask_secrets, secret_values
from infra_control.providers import registry
from infra_control.providers.base import OpRef, OpState, OpStatus, Provider

QUEUE = "infra"
SCHEDULER_USER = "scheduler"
"""`Infra Job.triggered_by` for jobs the scheduler creates (contract: "User id, or `scheduler`")."""
POLL_INITIAL_SECONDS = 3.0
POLL_MAX_SECONDS = 15.0
LOCK_WAIT_SECONDS = 120.0
LOCK_WAIT_STEP_SECONDS = 3.0
OUTPUT_KEEP_BYTES = 64 * 1024
STALE_AFTER_MINUTES_DEFAULT = 5

# Which keyword the target document is passed under for each target doctype.
_TARGET_KWARG: dict[str, str] = {
	TargetDoctype.SERVER: "server",
	TargetDoctype.SITE: "site",
	TargetDoctype.BENCH: "bench",
	TargetDoctype.PROVIDER_ACCOUNT: "account",
}
# Playbook param -> provider method argument where the names differ (plan 4.1 signatures).
_METHOD_PARAM_MAP: dict[str, dict[str, str]] = {
	"create_site": {"domain": "site"},
	"restore_site": {"backup": "backup_ref"},
}
_OP_TO_JOB: dict[OpState, JobStatus] = {
	OpState.QUEUED: JobStatus.RUNNING,
	OpState.RUNNING: JobStatus.RUNNING,
	OpState.SUCCESS: JobStatus.SUCCESS,
	OpState.FAILED: JobStatus.FAILED,
	OpState.CANCELLED: JobStatus.CANCELLED,
}
_OP_TO_STEP: dict[OpState, StepStatus] = {
	OpState.QUEUED: StepStatus.QUEUED,
	OpState.RUNNING: StepStatus.RUNNING,
	OpState.SUCCESS: StepStatus.SUCCESS,
	OpState.FAILED: StepStatus.FAILED,
	OpState.CANCELLED: StepStatus.CANCELLED,
}

# Test seam: the engine's sleep.
sleep: Callable[[float], None] = time.sleep


@dataclass(frozen=True)
class Target:
	doctype: str
	name: str
	provider_account: str
	provider: str
	server: str | None
	"""Server the target lives on (None for Frappe Cloud and for Provider Account targets)."""


# ---------------------------------------------------------------------------------------
# Read-only playbooks run beside a mutating job instead of queueing behind it (A3.8): looking
# at a log while a migration runs is exactly when an operator needs it. They never change
# the server, so the one-job-per-server lock does not apply to them.
READ_ONLY_PLAYBOOKS: frozenset[str] = frozenset({"server.logs"})


# Target resolution and lock keys (pure given a target)
# ---------------------------------------------------------------------------------------
def resolve_target(doctype: str, name: str) -> Target:
	if doctype not in set(TargetDoctype):
		raise ValidationError(f"Unsupported target_doctype {doctype}", {"field": "target_doctype"})
	if not frappe.db.exists(doctype, name):
		raise NotFound(doctype, name)
	doc: Any = frappe.get_doc(doctype, name)
	if doctype == TargetDoctype.PROVIDER_ACCOUNT:
		return Target(doctype, name, name, str(doc.provider), None)
	if doctype == TargetDoctype.SERVER:
		return Target(doctype, name, str(doc.provider_account), str(doc.provider), name)
	return Target(doctype, name, str(doc.provider_account), str(doc.provider), doc.server or None)


def lock_key_for(target: Target) -> str:
	"""One running job per server; per site/bench on providers without a server; per account."""
	if target.server:
		return locks.lock_key("server", target.server)
	if target.doctype == TargetDoctype.SITE:
		return locks.lock_key("site", target.name)
	if target.doctype == TargetDoctype.BENCH:
		return locks.lock_key("bench", target.name)
	return locks.lock_key("provider", target.name)


def redis_client() -> Any:
	return frappe.cache()


# ---------------------------------------------------------------------------------------
# create_job: plan 9.1 step 1
# ---------------------------------------------------------------------------------------
def validate_params(params: dict[str, Any], schema: dict[str, Any] | None) -> None:
	schema = schema or {"type": "object"}
	validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
	errors = sorted(validator.iter_errors(params), key=lambda e: list(e.path))
	if errors:
		first = errors[0]
		path = "params" + "".join(f".{p}" if isinstance(p, str) else f"[{p}]" for p in first.path)
		raise ValidationError(f"{path}: {first.message}", {"field": path})


def check_confirmation(risk: Risk | str, expected: str, confirm: str | None) -> None:
	"""High-risk playbooks need `confirm == expected` (the target name, or `<playbook>:<n>` for bulk)."""
	if Risk(risk) is Risk.HIGH and confirm != expected:
		raise ConfirmationRequired(expected, "Type the target name to confirm")


def _load_schema(playbook: Any) -> dict[str, Any] | None:
	raw = playbook.get("params_schema")
	if not raw:
		return None
	data: Any = json.loads(raw) if isinstance(raw, str) else raw
	return data if isinstance(data, dict) else None


def create_job(
	playbook_key: str,
	target_doctype: str,
	target_name: str,
	params: dict[str, Any] | None = None,
	confirm: str | None = None,
	*,
	user: str | None = None,
	bulk_operation: str | None = None,
	retry_of: str | None = None,
	enqueue: bool = True,
) -> Any:
	"""Validate role, risk, capability, params and confirmation; audit; create and enqueue the job."""
	user = user or frappe.session.user
	params = dict(params or {})
	action = f"jobs.run:{playbook_key}"
	try:
		if not frappe.db.exists("Playbook", playbook_key):
			raise NotFound("Playbook", playbook_key)
		playbook: Any = frappe.get_doc("Playbook", playbook_key)
		if not playbook.enabled:
			raise InvalidState(f"Playbook {playbook_key} is disabled", {"playbook": playbook_key})
		if user == SCHEDULER_USER:
			# System-initiated (hooks.scheduler_events). Only low-risk playbooks, no human roles.
			if Risk(playbook.risk) is not Risk.LOW:
				raise PermissionDenied(
					f"The scheduler may not run {playbook.risk}-risk playbooks", {"playbook": playbook_key}
				)
		else:
			require_risk(playbook.risk, user)
		if target_doctype != playbook.target_doctype:
			raise ValidationError(
				f"Playbook {playbook_key} targets a {playbook.target_doctype}, not a {target_doctype}",
				{"field": "target_doctype", "expected": playbook.target_doctype},
			)
		target = resolve_target(target_doctype, target_name)
		if playbook.required_capability:
			caps = registry.capabilities_for(target.provider)
			if playbook.required_capability not in {str(c) for c in caps}:
				raise NotSupported(playbook.required_capability, target.provider)
		schema = _load_schema(playbook)
		# Keys starting with "_" are engine-internal (e.g. `_resume_from` on a retry), not user params.
		validate_params({k: v for k, v in params.items() if not k.startswith("_")}, schema)
		check_confirmation(playbook.risk, target_name, confirm)
	except Exception as exc:
		result = (
			AuditResult.DENIED
			if isinstance(exc, ConfirmationRequired | NotSupported)
			or getattr(exc, "code", "") == "permission_denied"
			else AuditResult.FAILED
		)
		audit.record(
			action,
			result=result,
			target_doctype=target_doctype,
			target_name=target_name,
			params=params,
			user=user,
		)
		raise

	job: Any = frappe.get_doc(
		{
			"doctype": "Infra Job",
			"playbook": playbook_key,
			"target_doctype": target_doctype,
			"target_name": target_name,
			"params": json.dumps(mask_params(params, schema)),
			"status": JobStatus.QUEUED,
			"progress": 0,
			"triggered_by": user,
			"bulk_operation": bulk_operation,
			"retry_of": retry_of,
		}
	)
	job.flags.ignore_permissions = True
	job.insert()
	# The real (unmasked) params travel to the worker through the job record's private store,
	# never through the stored document: keep them in Redis under the job name for the worker.
	_stash_params(job.name, params)
	audit.record(
		action,
		result=AuditResult.SUCCESS,
		target_doctype=target_doctype,
		target_name=target_name,
		params=params,
		job=job.name,
		user=user,
	)
	realtime.emit(*realtime.job_updated(job.name, JobStatus.QUEUED, 0))
	if enqueue:
		enqueue_job(job.name)
	return job


def _stash_key(job: str) -> str:
	return f"infra:job:params:{job}"


def _stash_params(job: str, params: dict[str, Any]) -> None:
	redis_client().set(_stash_key(job), json.dumps(params), ex=7 * 24 * 3600)


def _unstash_params(job: str) -> dict[str, Any]:
	raw = redis_client().get(_stash_key(job))
	if raw is None:
		return {}
	data: dict[str, Any] = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
	return data


def enqueue_job(job: str) -> None:
	frappe.enqueue(
		"infra_control.job_engine.engine.run_job",
		queue=QUEUE,
		job_name=f"infra_job:{job}",
		timeout=locks.DEFAULT_TTL_SECONDS,
		enqueue_after_commit=True,
		job=job,
	)


# ---------------------------------------------------------------------------------------
# cancel / retry
# ---------------------------------------------------------------------------------------
def cancel_job(job_name: str, *, user: str | None = None) -> Any:
	job: Any = _get_job(job_name)
	if job.status in TERMINAL_JOB_STATUSES:
		raise InvalidState(f"Job {job_name} is already {job.status}", {"status": job.status})
	job.db_set("cancel_requested", 1)
	if job.status == JobStatus.QUEUED:
		_finish(job, JobStatus.CANCELLED, error=None)
	audit.record(
		"jobs.cancel",
		result=AuditResult.SUCCESS,
		target_doctype=job.target_doctype,
		target_name=job.target_name,
		job=job_name,
		user=user,
	)
	return job


def first_failed_step(job_name: str) -> int | None:
	failed = _first_failed_row(job_name)
	return int(failed["step_index"]) if failed else None


def _first_failed_row(job_name: str) -> dict[str, Any] | None:
	rows = frappe.get_all(
		"Infra Job Step",
		filters={"job": job_name, "status": StepStatus.FAILED},
		fields=["step_index", "title"],
		order_by="step_index asc",
		limit=1,
	)
	return dict(rows[0]) if rows else None


def retry_job(job_name: str, *, user: str | None = None) -> Any:
	job: Any = _get_job(job_name)
	if job.status != JobStatus.FAILED:
		raise InvalidState(
			f"Only Failed jobs can be retried; {job_name} is {job.status}", {"status": job.status}
		)
	params = _unstash_params(job_name)
	failed = _first_failed_row(job_name)
	if failed is not None:
		params["_resume_from"] = int(failed["step_index"])
		# Ansible steps are tasks; the task name is what `--start-at-task` needs (plan 9.1 step 6).
		params["_resume_task"] = str(failed.get("title") or "")
	playbook: Any = frappe.get_doc("Playbook", job.playbook)
	confirm = job.target_name if Risk(playbook.risk) is Risk.HIGH else None
	return create_job(
		job.playbook, job.target_doctype, job.target_name, params, confirm, user=user, retry_of=job_name
	)


# ---------------------------------------------------------------------------------------
# run_job: worker entry point (plan 9.1 steps 2-5)
# ---------------------------------------------------------------------------------------
def _checkpoint() -> None:
	"""Commit what the worker wrote so far.

	Frappe commits a background job's writes only when the job returns. Without checkpoints a
	long job shows `Queued` with no steps until it ends (live gate, JOB-00012), crash recovery
	cannot see its heartbeat, and the poll loop never sees `cancel_requested` set by the API in
	another transaction. Each commit also starts a fresh transaction, so the next read is current.
	"""
	frappe.db.commit()


def run_job(job: str) -> None:
	doc: Any = _get_job(job)
	if doc.status in TERMINAL_JOB_STATUSES:
		return
	if doc.cancel_requested:
		_finish(doc, JobStatus.CANCELLED)
		return
	target = resolve_target(doc.target_doctype, doc.target_name)
	if str(doc.playbook) in READ_ONLY_PLAYBOOKS:
		try:
			_execute(doc, target)
		except Exception as exc:
			frappe.log_error(title=f"Infra Job {job} crashed", message=frappe.get_traceback())
			_finish(doc, JobStatus.FAILED, error=mask_secrets(str(exc), _secrets_for(doc)))
		return
	key = lock_key_for(target)
	client = redis_client()
	if not _wait_for_lock(client, key, job, doc):
		# Still held by another job: give it back to the queue (plan 9.1 step 2).
		enqueue_job(job)
		return
	doc.db_set("lock_key", key)
	_checkpoint()
	try:
		_execute(doc, target)
	except Exception as exc:
		frappe.log_error(title=f"Infra Job {job} crashed", message=frappe.get_traceback())
		_finish(doc, JobStatus.FAILED, error=mask_secrets(str(exc), _secrets_for(doc)))
	finally:
		locks.release(client, key, job)


def _wait_for_lock(client: Any, key: str, token: str, doc: Any) -> bool:
	deadline = time.monotonic() + LOCK_WAIT_SECONDS
	while True:
		if locks.acquire(client, key, token):
			return True
		if time.monotonic() >= deadline:
			return False
		doc.db_set("worker_heartbeat", now_datetime())
		_checkpoint()
		sleep(LOCK_WAIT_STEP_SECONDS)


def _secrets_for(doc: Any) -> list[str]:
	out: list[str] = []
	# Masking must never fail the job: an unreadable account simply contributes no known value.
	with contextlib.suppress(Exception):
		account = resolve_target(doc.target_doctype, doc.target_name).provider_account
		out.append(registry.config_from_account(account).api_token)
	playbook: Any = frappe.get_doc("Playbook", doc.playbook)
	params = _unstash_params(doc.name)
	out.extend(secret_values(params, _load_schema(playbook)))
	with contextlib.suppress(Exception):
		if params.get("connection"):
			from infra_control.api.git import token_for

			out.append(token_for(str(params["connection"])))
	return out


def _provider_for(target: Target) -> Provider:
	"""Site config `infra_use_dummy_provider: 1` swaps in the in-memory provider (Phase 1 dummy runs)."""
	if frappe.conf.get("infra_use_dummy_provider"):
		import infra_control.providers.dummy.adapter as dummy

		return dummy.DummyProvider(registry.config_from_account(target.provider_account))
	return registry.get_provider(target.provider_account)


def _build_call(playbook: Any, target: Target, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
	kwargs = {k: v for k, v in params.items() if not k.startswith("_")}
	if playbook.ansible_file and not playbook.provider_method:
		if not target.server:
			raise NotSupported("ssh", target.provider)
		call: dict[str, Any] = {
			"server": target.server,
			"playbook_file": playbook.ansible_file,
			"extra_vars": kwargs,
		}
		if params.get("_resume_task"):
			call["resume_task"] = params["_resume_task"]
		return "run_playbook", call
	method = str(playbook.provider_method)
	for param, arg in _METHOD_PARAM_MAP.get(method, {}).items():
		if param in kwargs:
			kwargs[arg] = kwargs.pop(param)
	if target.doctype != TargetDoctype.PROVIDER_ACCOUNT:
		kwargs[_TARGET_KWARG[target.doctype]] = target.name
	if method in ("get_status",):
		raise ValidationError(f"Playbook method {method} is not runnable", {"method": method})
	return method, kwargs


def _execute(doc: Any, target: Target) -> None:
	playbook: Any = frappe.get_doc("Playbook", doc.playbook)
	params = _unstash_params(doc.name)
	secrets = _secrets_for(doc)
	provider = _provider_for(target)
	if playbook.required_capability:
		provider.require(playbook.required_capability)

	doc.db_set(
		{"status": JobStatus.RUNNING, "started_at": now_datetime(), "worker_heartbeat": now_datetime()}
	)
	_checkpoint()
	realtime.emit(*realtime.job_updated(doc.name, JobStatus.RUNNING, 0))

	method, kwargs = _build_call(playbook, target, params)
	result = provider.call(method, **kwargs)
	if not isinstance(result, OpRef):
		# Query-style methods (get_metrics, sync_inventory) finish synchronously.
		_write_step(
			doc,
			0,
			playbook.title,
			StepStatus.SUCCESS,
			mask_secrets(json.dumps(result, default=str), secrets),
			secrets,
			emit_log=True,
		)
		doc.db_set({"steps_total": 1, "steps_done": 1})
		_finish(doc, JobStatus.SUCCESS)
		return
	doc.db_set("op_ref", json.dumps(result.to_dict()))
	_checkpoint()

	delay = POLL_INITIAL_SECONDS
	while True:
		status = provider.get_status(result)
		_sync_steps(doc, status, secrets)
		doc.db_set("worker_heartbeat", now_datetime())
		_checkpoint()
		if status.state.terminal:
			break
		doc.reload()
		if doc.cancel_requested:
			provider.cancel(result)
		sleep(delay)
		delay = min(delay * 1.5, POLL_MAX_SECONDS)

	created = _link_created(doc, status, playbook)
	_finish(
		doc,
		_OP_TO_JOB[status.state],
		error=mask_secrets(status.error or "", secrets) or None,
		created=created,
	)


def _sync_steps(doc: Any, status: OpStatus, secrets: list[str]) -> None:
	total = len(status.steps)
	done = 0
	for idx, step in enumerate(status.steps):
		state = _OP_TO_STEP[step.state]
		if state in (StepStatus.SUCCESS, StepStatus.FAILED, StepStatus.CANCELLED, StepStatus.SKIPPED):
			done += 1
		_write_step(
			doc,
			idx,
			step.name,
			state,
			mask_secrets(step.output or "", secrets),
			secrets,
			started_at=step.started_at,
			ended_at=step.ended_at,
		)
	progress = int(done * 100 / total) if total else 0
	if (doc.steps_done, doc.steps_total, doc.progress) != (done, total, progress):
		doc.db_set({"steps_done": done, "steps_total": total, "progress": progress})
		realtime.emit(*realtime.job_updated(doc.name, JobStatus.RUNNING, progress))


def _db_datetime(value: datetime | None) -> datetime | None:
	"""Normalise a provider timestamp for storage.

	Adapters return timezone-aware datetimes (UTC). Frappe stores naive datetimes in the system
	timezone, and MariaDB in strict mode rejects an ISO string carrying an offset, so every
	provider timestamp crosses this boundary before it reaches a Datetime column.
	"""
	if value is None or value.tzinfo is None:
		return value
	return value.astimezone(ZoneInfo(get_system_timezone())).replace(tzinfo=None)


def _write_step(
	doc: Any,
	idx: int,
	title: str,
	status: StepStatus,
	output: str,
	secrets: list[str],
	*,
	started_at: datetime | None = None,
	ended_at: datetime | None = None,
	emit_log: bool = False,
) -> None:
	"""Upsert the Infra Job Step, emit `job.step` on status change and `job.log` for new output."""
	name = f"{doc.name}-{idx}"
	if frappe.db.exists("Infra Job Step", name):
		step: Any = frappe.get_doc("Infra Job Step", name)
		previous_status, previous_output = step.status, step.output or ""
	else:
		step = frappe.get_doc(
			{
				"doctype": "Infra Job Step",
				"job": doc.name,
				"step_index": idx,
				"title": title,
				"status": StepStatus.QUEUED,
				"output": "",
			}
		)
		step.flags.ignore_permissions = True
		step.insert()
		previous_status, previous_output = None, ""
		realtime.emit(*realtime.job_step(doc.name, idx, title, StepStatus.QUEUED))
	new_chunk = output[len(previous_output) :] if output.startswith(previous_output) else output
	changed: dict[str, Any] = {}
	if status != previous_status:
		changed["status"] = status
	if output != previous_output:
		changed["output"] = output[-OUTPUT_KEEP_BYTES:]
	if started_at and not step.started_at:
		changed["started_at"] = _db_datetime(started_at)
	if ended_at and not step.ended_at:
		changed["ended_at"] = _db_datetime(ended_at)
	if changed:
		step.db_set(changed)
	if new_chunk and (emit_log or output != previous_output):
		realtime.emit(*realtime.job_log(doc.name, idx, new_chunk))
	if status != previous_status:
		realtime.emit(*realtime.job_step(doc.name, idx, title, status))


def _link_created(doc: Any, status: OpStatus, playbook: Any) -> tuple[str, str] | None:
	"""ADR 0001: a creation playbook's job links to the created document once it exists."""
	if status.state is not OpState.SUCCESS or not playbook.creates or not status.created:
		return None
	doctype, ref = status.created
	name = (
		ref if frappe.db.exists(doctype, ref) else frappe.db.get_value(doctype, {"provider_ref": ref}, "name")
	)
	if not name:
		return None
	doc.db_set({"created_doctype": doctype, "created_name": name})
	realtime.emit(*realtime.inventory_changed(doctype, str(name), "created"))
	return doctype, str(name)


def _finish(
	doc: Any, status: JobStatus, *, error: str | None = None, created: tuple[str, str] | None = None
) -> None:
	values: dict[str, Any] = {"status": status, "ended_at": now_datetime()}
	if error:
		values["error"] = error[:1000]
	if status is JobStatus.SUCCESS:
		values["progress"] = 100
	doc.db_set(values)
	_checkpoint()
	redis_client().delete(_stash_key(doc.name))
	realtime.emit(
		*realtime.job_updated(doc.name, status, doc.progress if status is not JobStatus.SUCCESS else 100)
	)
	if status is JobStatus.SUCCESS and doc.target_doctype in (
		TargetDoctype.SERVER,
		TargetDoctype.SITE,
		TargetDoctype.BENCH,
	):
		realtime.emit(*realtime.inventory_changed(doc.target_doctype, doc.target_name, "updated"))


def _get_job(job: str) -> Any:
	if not frappe.db.exists("Infra Job", job):
		raise NotFound("Infra Job", job)
	return frappe.get_doc("Infra Job", job)


# ---------------------------------------------------------------------------------------
# crash recovery (plan 9.1 step 7)
# ---------------------------------------------------------------------------------------
def fail_stale_jobs(*, stale_after_minutes: int | None = None) -> list[str]:
	"""Scheduler, every minute: Running jobs with no heartbeat for N minutes are failed and unlocked."""
	minutes = stale_after_minutes
	if minutes is None:
		configured = frappe.db.get_single_value("Infra Settings", "job_heartbeat_timeout_minutes")
		minutes = int(configured or STALE_AFTER_MINUTES_DEFAULT)
	cutoff = add_to_date(now_datetime(), minutes=-minutes)
	failed: list[str] = []
	client = redis_client()
	for row in frappe.get_all(
		"Infra Job",
		filters={"status": JobStatus.RUNNING},
		fields=["name", "worker_heartbeat", "started_at", "lock_key"],
	):
		last = get_datetime(row.get("worker_heartbeat") or row.get("started_at"))
		if last is None or last > cutoff:
			continue
		doc: Any = frappe.get_doc("Infra Job", row["name"])
		_finish(
			doc,
			JobStatus.FAILED,
			error=f"Worker heartbeat lost for {minutes} minutes; job marked failed by crash recovery",
		)
		if row.get("lock_key"):
			locks.force_release(client, str(row["lock_key"]))
		failed.append(str(row["name"]))
	return failed


def heartbeat_timeout() -> timedelta:
	return timedelta(minutes=STALE_AFTER_MINUTES_DEFAULT)


__all__ = [
	"QUEUE",
	"InternalError",
	"Target",
	"cancel_job",
	"check_confirmation",
	"create_job",
	"enqueue_job",
	"fail_stale_jobs",
	"lock_key_for",
	"resolve_target",
	"retry_job",
	"run_job",
	"validate_params",
]
