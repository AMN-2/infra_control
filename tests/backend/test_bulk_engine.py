"""A3.4 bulk shell lifecycle on the in-memory fake: backup-first, canary, batches, policy,
pause/resume and cancel. Child jobs are stubbed so no real job engine or provider is touched."""

from __future__ import annotations

from typing import Any

import pytest
from fake_frappe import FakeFrappe

from infra_control.bulk import engine as bulk_engine
from infra_control.bulk import health
from infra_control.core import audit, permissions
from infra_control.core.enums import BulkStatus
from infra_control.job_engine import engine as jobs
from infra_control.job_engine import realtime

REST = {BulkStatus.SUCCESS, BulkStatus.FAILED, BulkStatus.CANCELLED, BulkStatus.PAUSED, BulkStatus.HALTED}


@pytest.fixture
def ff(monkeypatch: pytest.MonkeyPatch) -> FakeFrappe:
	f = FakeFrappe()
	for module in (bulk_engine, jobs, realtime, audit, permissions, health):
		monkeypatch.setattr(module, "frappe", f, raising=False)
	monkeypatch.setattr(bulk_engine, "now_datetime", f.now)
	monkeypatch.setattr(audit, "now_datetime", f.now)

	# How each child job resolves, keyed by (playbook, target_name); default is success.
	f.outcomes = {}  # type: ignore[attr-defined]

	def fake_create_job(
		playbook: str,
		target_doctype: str,
		target_name: str,
		params: dict[str, Any] | None = None,
		confirm: str | None = None,
		*,
		user: str | None = None,
		bulk_operation: str | None = None,
		enqueue: bool = True,
		retry_of: str | None = None,
	) -> Any:
		return f.add(
			"Infra Job",
			playbook=playbook,
			target_doctype=target_doctype,
			target_name=target_name,
			status="Queued",
			triggered_by=user,
			bulk_operation=bulk_operation,
		)

	def fake_run_job(job_name: str) -> None:
		job = f.get_doc("Infra Job", job_name)
		ok = f.outcomes.get((job.playbook, job.target_name), True)  # type: ignore[attr-defined]
		job.db_set("status", "Success" if ok else "Failed")

	monkeypatch.setattr(jobs, "create_job", fake_create_job)
	monkeypatch.setattr(jobs, "run_job", fake_run_job)

	for key, risk in (("site.migrate", "medium"), ("site.backup", "low")):
		f.add("Playbook", name=key, key=key, title=key, target_doctype="Site", risk=risk, enabled=1)
	f.add("Provider Account", name="DO", provider="digitalocean")
	f.add("Server", name="SRV-1", provider_account="DO", provider="digitalocean")
	for i in range(1, 6):
		f.add(
			"Site",
			name=f"s{i}.iq",
			domain=f"s{i}.iq",
			provider_account="DO",
			provider="digitalocean",
			server="SRV-1",
		)
	return f


def _ref(name: str) -> dict[str, str]:
	return {"target_doctype": "Site", "target_name": name}


def _create(ff: FakeFrappe, sites: list[str], canary: str, **kw: Any) -> Any:
	params = {"_skip_health": 1, **kw.pop("params", {})}
	return bulk_engine.create_bulk(
		"site.migrate",
		[_ref(s) for s in sites],
		_ref(canary),
		params=params,
		**{"batch_size": 5, "failure_policy": "halt", **kw},
	)


def _drain(ff: FakeFrappe, name: str, limit: int = 50) -> Any:
	for _ in range(limit):
		doc = ff.get_doc("Bulk Operation", name)
		if BulkStatus(doc.status) in REST:
			return doc
		bulk_engine.drive(name)
	raise AssertionError("bulk did not reach a resting state")


def _targets(ff: FakeFrappe, name: str) -> dict[str, str]:
	return {
		str(r["target_name"]): str(r["status"])
		for r in ff.get_all(
			"Bulk Operation Target", filters={"parent": name}, fields=["target_name", "status"]
		)
	}


# ----- lifecycle ---------------------------------------------------------------------------
def test_success_path_backups_then_canary_then_batch(ff: FakeFrappe) -> None:
	bulk = _create(ff, ["s1.iq", "s2.iq", "s3.iq"], canary="s1.iq", batch_size=5)
	doc = _drain(ff, bulk.name)
	assert doc.status == str(BulkStatus.SUCCESS)
	assert doc.done == 3 and doc.failed == 0 and doc.total == 3
	assert _targets(ff, bulk.name) == {"s1.iq": "Success", "s2.iq": "Success", "s3.iq": "Success"}
	# Backup-first: site.backup ran for every Site target before the migrate jobs.
	backups = [j for j in ff.store["Infra Job"].values() if j.playbook == "site.backup"]
	assert {j.target_name for j in backups} == {"s1.iq", "s2.iq", "s3.iq"}
	# The canary (batch 0) is the first migrate job; its child links back to the bulk.
	migrates = [j for j in ff.store["Infra Job"].values() if j.playbook == "site.migrate"]
	assert migrates[0].target_name == "s1.iq" and migrates[0].bulk_operation == bulk.name
	# Realtime: a bulk.updated per target plus status changes, ending Success.
	events = ff.events_of("infra:bulk.updated")
	assert events[-1]["status"] == "Success" and events[-1]["done"] == 3


def test_canary_failure_halts_and_skips_the_rest(ff: FakeFrappe) -> None:
	ff.outcomes[("site.migrate", "s1.iq")] = False  # type: ignore[attr-defined]
	bulk = _create(ff, ["s1.iq", "s2.iq", "s3.iq"], canary="s1.iq", batch_size=5)
	doc = _drain(ff, bulk.name)
	assert doc.status == str(BulkStatus.HALTED)
	assert _targets(ff, bulk.name) == {"s1.iq": "Failed", "s2.iq": "Skipped", "s3.iq": "Skipped"}
	# No batch migrate jobs ran for the skipped sites.
	assert not any(
		j.playbook == "site.migrate" and j.target_name in ("s2.iq", "s3.iq")
		for j in ff.store["Infra Job"].values()
	)
	assert ff.events_of("infra:bulk.updated")[-1]["status"] == "Halted"


def test_batch_failure_halts_under_halt_policy(ff: FakeFrappe) -> None:
	ff.outcomes[("site.migrate", "s2.iq")] = False  # type: ignore[attr-defined]
	bulk = _create(
		ff, ["s1.iq", "s2.iq", "s3.iq", "s4.iq"], canary="s1.iq", batch_size=1, failure_policy="halt"
	)
	doc = _drain(ff, bulk.name)
	assert doc.status == str(BulkStatus.HALTED)
	statuses = _targets(ff, bulk.name)
	assert statuses["s1.iq"] == "Success" and statuses["s2.iq"] == "Failed"
	assert statuses["s3.iq"] == "Skipped" and statuses["s4.iq"] == "Skipped"


def test_batch_failure_continues_under_continue_policy(ff: FakeFrappe) -> None:
	ff.outcomes[("site.migrate", "s2.iq")] = False  # type: ignore[attr-defined]
	bulk = _create(
		ff, ["s1.iq", "s2.iq", "s3.iq", "s4.iq"], canary="s1.iq", batch_size=1, failure_policy="continue"
	)
	doc = _drain(ff, bulk.name)
	assert doc.status == str(BulkStatus.FAILED)
	statuses = _targets(ff, bulk.name)
	assert statuses == {"s1.iq": "Success", "s2.iq": "Failed", "s3.iq": "Success", "s4.iq": "Success"}
	assert doc.done == 4 and doc.failed == 1


def test_backup_failure_halts_before_the_canary(ff: FakeFrappe) -> None:
	ff.outcomes[("site.backup", "s1.iq")] = False  # type: ignore[attr-defined]
	bulk = _create(ff, ["s1.iq", "s2.iq"], canary="s1.iq")
	doc = _drain(ff, bulk.name)
	assert doc.status == str(BulkStatus.HALTED)
	# No migrate job ran at all: the backup gate stopped the rollout.
	assert not any(j.playbook == "site.migrate" for j in ff.store["Infra Job"].values())
	assert set(_targets(ff, bulk.name).values()) == {"Skipped"}


def test_pause_at_a_batch_boundary_then_resume(ff: FakeFrappe) -> None:
	bulk = _create(ff, ["s1.iq", "s2.iq", "s3.iq"], canary="s1.iq", batch_size=1)
	name = bulk.name
	# Step through backups, the canary and the first batch, then request a pause.
	for _ in range(20):
		doc = ff.get_doc("Bulk Operation", name)
		if doc.phase == "batches" and doc.current_batch == 1 and _targets(ff, name)["s2.iq"] == "Success":
			break
		bulk_engine.drive(name)
	bulk_engine.pause(name)
	doc = _drain(ff, name)
	assert doc.status == str(BulkStatus.PAUSED)
	assert _targets(ff, name)["s3.iq"] == "Pending"  # the second batch has not run
	# Resume finishes the remaining batch.
	bulk_engine.resume(name)
	doc = _drain(ff, name)
	assert doc.status == str(BulkStatus.SUCCESS)
	assert _targets(ff, name)["s3.iq"] == "Success"


def test_cancel_finishes_current_target_and_skips_the_rest(ff: FakeFrappe) -> None:
	bulk = _create(ff, ["s1.iq", "s2.iq", "s3.iq", "s4.iq"], canary="s1.iq", batch_size=1)
	name = bulk.name
	# Drive until the first batch target has run, then cancel.
	for _ in range(20):
		if _targets(ff, name).get("s2.iq") == "Success":
			break
		bulk_engine.drive(name)
	bulk_engine.cancel(name)
	doc = _drain(ff, name)
	assert doc.status == str(BulkStatus.CANCELLED)
	statuses = _targets(ff, name)
	assert statuses["s1.iq"] == "Success" and statuses["s2.iq"] == "Success"
	assert statuses["s3.iq"] == "Skipped" and statuses["s4.iq"] == "Skipped"


def test_cancel_a_queued_bulk_finishes_immediately(ff: FakeFrappe) -> None:
	bulk = _create(ff, ["s1.iq", "s2.iq"], canary="s1.iq")
	bulk_engine.cancel(bulk.name)
	doc = ff.get_doc("Bulk Operation", bulk.name)
	assert doc.status == str(BulkStatus.CANCELLED)
	assert set(_targets(ff, bulk.name).values()) == {"Skipped"}


def test_health_check_failure_folds_into_the_failure_policy(
	ff: FakeFrappe, monkeypatch: pytest.MonkeyPatch
) -> None:
	# Jobs all succeed, but the post-batch health probe reports s2 down -> Failed -> halt.
	monkeypatch.setattr(
		health, "check_target", lambda dt, name, **kw: (name != "s2.iq", "down" if name == "s2.iq" else "ok")
	)
	bulk = bulk_engine.create_bulk(
		"site.migrate",
		[_ref("s1.iq"), _ref("s2.iq"), _ref("s3.iq")],
		_ref("s1.iq"),
		batch_size=5,
		failure_policy="halt",
		params={},  # health checks NOT skipped
	)
	doc = _drain(ff, bulk.name)
	assert doc.status == str(BulkStatus.HALTED)
	assert _targets(ff, bulk.name)["s2.iq"] == "Failed"


def test_invalid_state_guards(ff: FakeFrappe) -> None:
	from infra_control.core.errors import InvalidState

	bulk = _create(ff, ["s1.iq", "s2.iq"], canary="s1.iq")
	_drain(ff, bulk.name)  # runs to Success
	with pytest.raises(InvalidState):
		bulk_engine.pause(bulk.name)
	with pytest.raises(InvalidState):
		bulk_engine.resume(bulk.name)
	with pytest.raises(InvalidState):
		bulk_engine.cancel(bulk.name)
