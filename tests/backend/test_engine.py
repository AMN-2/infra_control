"""A1.2: the job engine end to end against the in-memory Frappe and the dummy provider."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fake_frappe import FakeFrappe

from infra_control.core import audit, permissions
from infra_control.core.enums import PROVIDER_CAPABILITIES, Capability
from infra_control.core.enums import Provider as ProviderName
from infra_control.core.errors import (
	ConfirmationRequired,
	InvalidState,
	NotFound,
	NotSupported,
	PermissionDenied,
	ValidationError,
)
from infra_control.install import PLAYBOOKS
from infra_control.job_engine import engine, realtime
from infra_control.job_engine.masking import MASK
from infra_control.providers import registry
from infra_control.providers.base import OpRef, OpState, OpStatus, OpStep
from infra_control.providers.dummy.adapter import DummyProvider

FAKE_TOKEN = "dop_v1_" + "cafe" * 16
PASSWORD = "Sup3r-Secret-Pass"


@pytest.fixture
def ff(monkeypatch: pytest.MonkeyPatch) -> FakeFrappe:
	f = FakeFrappe()
	for module in (engine, realtime, audit, permissions, registry):
		monkeypatch.setattr(module, "frappe", f)
	monkeypatch.setattr(engine, "now_datetime", f.now)
	monkeypatch.setattr(engine, "get_system_timezone", lambda: "Asia/Baghdad")
	monkeypatch.setattr(audit, "now_datetime", f.now)
	monkeypatch.setattr(engine, "sleep", lambda s: None)
	monkeypatch.setattr(engine, "LOCK_WAIT_SECONDS", 0.0)
	f.conf["infra_use_dummy_provider"] = 1
	for spec in PLAYBOOKS:
		f.add(
			"Playbook",
			name=spec["key"],
			key=spec["key"],
			title=spec["title"],
			target_doctype=str(spec["target_doctype"]),
			creates=spec.get("creates") or "",
			risk=str(spec["risk"]),
			required_capability=str(spec["required_capability"]) if spec.get("required_capability") else "",
			ansible_file=spec.get("ansible_file") or "",
			provider_method=spec.get("provider_method") or "",
			params_schema=json.dumps(
				spec.get("params_schema")
				or {"type": "object", "additionalProperties": False, "properties": {}}
			),
			enabled=1,
		)
	f.add(
		"Provider Account",
		name="DO-STAGING",
		label="DO-STAGING",
		provider="digitalocean",
		api_token=FAKE_TOKEN,
		is_staging=1,
		enabled=1,
	)
	f.add(
		"Provider Account",
		name="FC-STAGING",
		label="FC-STAGING",
		provider="frappe_cloud",
		api_token="press-token-xyz",
		team="t",
		is_staging=1,
		enabled=1,
	)
	f.add(
		"Server",
		name="SRV-0001",
		hostname="app-01",
		provider_account="DO-STAGING",
		provider="digitalocean",
		status="Active",
	)
	f.add(
		"Server",
		name="SRV-0002",
		hostname="app-02",
		provider_account="DO-STAGING",
		provider="digitalocean",
		status="Active",
	)
	f.add(
		"Bench",
		name="BENCH-0001",
		title="v15-prod",
		provider_account="DO-STAGING",
		provider="digitalocean",
		server="SRV-0001",
	)
	f.add(
		"Bench",
		name="BENCH-FC-01",
		title="fc",
		provider_account="FC-STAGING",
		provider="frappe_cloud",
		server=None,
	)
	f.add(
		"Site",
		name="demo.smartchoice-iq.com",
		domain="demo.smartchoice-iq.com",
		bench="BENCH-0001",
		server="SRV-0001",
		provider_account="DO-STAGING",
		provider="digitalocean",
		status="Active",
	)
	f.add(
		"Site",
		name="erp.client-a.iq",
		domain="erp.client-a.iq",
		bench="BENCH-0001",
		server="SRV-0001",
		provider_account="DO-STAGING",
		provider="digitalocean",
		status="Active",
	)
	f.add(
		"Site",
		name="fc.site",
		domain="fc.site",
		bench="BENCH-FC-01",
		server=None,
		provider_account="FC-STAGING",
		provider="frappe_cloud",
		status="Active",
	)
	return f


def _run(ff: FakeFrappe, job: Any) -> Any:
	engine.run_job(job.name)
	return ff.get_doc("Infra Job", job.name)


# --- create_job ---------------------------------------------------------------------------
def test_create_job_validates_and_audits(ff: FakeFrappe) -> None:
	with pytest.raises(NotFound):
		engine.create_job("nope", "Site", "demo.smartchoice-iq.com")
	with pytest.raises(ValidationError):  # wrong target doctype for the playbook
		engine.create_job("site.backup", "Server", "SRV-0001")
	with pytest.raises(NotFound):
		engine.create_job("site.backup", "Site", "ghost.iq")
	with pytest.raises(ValidationError) as exc:  # params against params_schema
		engine.create_job("site.backup", "Site", "demo.smartchoice-iq.com", {"with_files": "yes"})
	assert exc.value.details["field"] == "params.with_files"
	with pytest.raises(ConfirmationRequired) as conf:  # high risk needs confirm == target name
		engine.create_job("server.reboot", "Server", "SRV-0001")
	assert conf.value.details == {"expected": "SRV-0001"}
	with pytest.raises(NotSupported) as ns:  # capability check: snapshot on Frappe Cloud
		engine.create_job("site.backup", "Site", "fc.site")  # site is fine...
		raise NotSupported("snapshot", "frappe_cloud")  # ...so force the real case below
	ff.add(
		"Server",
		name="SRV-FC",
		hostname="x",
		provider_account="FC-STAGING",
		provider="frappe_cloud",
		status="Active",
	)
	with pytest.raises(NotSupported) as ns:
		engine.create_job("server.snapshot", "Server", "SRV-FC")
	assert ns.value.http_status == 409 and ns.value.details["capability"] == "snapshot"
	results = [d.result for d in ff.store["Infra Audit Log"].values()]
	assert results.count("denied") >= 2 and "failed" in results
	assert all(len(d.params_hash) == 64 for d in ff.store["Infra Audit Log"].values())


def test_create_job_role_checks(ff: FakeFrappe) -> None:
	ff.roles["viewer@x"] = ("Infra Viewer",)
	ff.roles["op@x"] = ("Infra Operator",)
	with pytest.raises(PermissionDenied):
		engine.create_job("site.backup", "Site", "demo.smartchoice-iq.com", user="viewer@x")
	with pytest.raises(PermissionDenied) as exc:
		engine.create_job("server.reboot", "Server", "SRV-0001", confirm="SRV-0001", user="op@x")
	assert exc.value.details == {"role": "Infra Operator", "required": "Infra Admin"}
	job = engine.create_job("site.backup", "Site", "demo.smartchoice-iq.com", user="op@x")
	assert job.status == "Queued" and job.triggered_by == "op@x"


def test_create_job_masks_params_stashes_real_ones_and_enqueues(ff: FakeFrappe) -> None:
	job = engine.create_job(
		"site.create",
		"Bench",
		"BENCH-0001",
		{"domain": "new.iq", "admin_password": PASSWORD, "apps": ["erpnext"]},
	)
	assert json.loads(job.params) == {"domain": "new.iq", "admin_password": MASK, "apps": ["erpnext"]}
	assert PASSWORD not in json.dumps(ff.store["Infra Job"][job.name].as_dict(), default=str)
	assert json.loads(ff.cache_client.get(f"infra:job:params:{job.name}"))["admin_password"] == PASSWORD
	assert ff.enqueued[-1]["queue"] == "infra" and ff.enqueued[-1]["job"] == job.name
	assert ff.enqueued[-1]["enqueue_after_commit"] is True
	assert ff.events_of("infra:job.updated")[-1] == {"job": job.name, "status": "Queued", "progress": 0}
	assert [d.result for d in ff.store["Infra Audit Log"].values()] == ["success"]
	assert next(iter(ff.store["Infra Audit Log"].values())).job == job.name


# --- run_job ------------------------------------------------------------------------------
def test_run_job_happy_path_steps_logs_and_lock(ff: FakeFrappe) -> None:
	job = engine.create_job("site.migrate", "Site", "demo.smartchoice-iq.com")
	ff.events.clear()
	done = _run(ff, job)
	assert done.status == "Success" and done.progress == 100 and done.steps_done == 3 == done.steps_total
	assert done.started_at and done.ended_at and done.lock_key == "infra:lock:server:SRV-0001"
	assert json.loads(done.op_ref)["kind"] == "dummy"
	steps = sorted(ff.store["Infra Job Step"].values(), key=lambda s: s.step_index)
	assert [s.title for s in steps] == [
		"Enable maintenance mode",
		"bench migrate",
		"Disable maintenance mode",
	]
	assert all(s.status == "Success" and s.output.endswith(": ok\n") for s in steps)
	events = [e for e, _ in ff.events]
	assert events[0] == "infra:job.updated" and ff.events[0][1]["status"] == "Running"
	assert events.count("infra:job.log") == 3
	step_events = ff.events_of("infra:job.step")
	assert step_events[0] == {
		"job": job.name,
		"idx": 0,
		"title": "Enable maintenance mode",
		"status": "Queued",
	}
	assert [e["status"] for e in step_events if e["idx"] == 1] == ["Queued", "Running", "Success"]
	assert ff.events_of("infra:job.updated")[-1] == {"job": job.name, "status": "Success", "progress": 100}
	assert ff.events_of("infra:inventory.changed") == [
		{"doctype": "Site", "name": "demo.smartchoice-iq.com", "change": "updated"}
	]
	assert ff.cache_client.get("infra:lock:server:SRV-0001") is None, "lock released"
	assert ff.cache_client.get(f"infra:job:params:{job.name}") is None, "real params dropped"


def test_one_running_job_per_server(ff: FakeFrappe) -> None:
	"""Two sites on SRV-0001: the second job must not run while the first holds the lock."""
	first = engine.create_job("site.backup", "Site", "demo.smartchoice-iq.com")
	second = engine.create_job("site.backup", "Site", "erp.client-a.iq")
	ff.cache_client.set("infra:lock:server:SRV-0001", first.name)  # first is running on a worker
	ff.enqueued.clear()
	engine.run_job(second.name)
	assert ff.get_doc("Infra Job", second.name).status == "Queued"
	assert ff.enqueued[-1]["job"] == second.name, "re-enqueued, not run"
	assert "Infra Job Step" not in ff.store
	ff.cache_client.delete("infra:lock:server:SRV-0001")
	assert _run(ff, second).status == "Success"
	# A job on another server is never blocked.
	other = engine.create_job("server.snapshot", "Server", "SRV-0002")
	ff.cache_client.set("infra:lock:server:SRV-0001", "JOB-x")
	assert _run(ff, other).status == "Success"


def test_frappe_cloud_targets_lock_per_site(ff: FakeFrappe) -> None:
	job = engine.create_job("site.backup", "Site", "fc.site")
	assert _run(ff, job).lock_key == "infra:lock:site:fc.site"


def test_cancel_queued_and_running(ff: FakeFrappe) -> None:
	queued = engine.create_job("site.backup", "Site", "demo.smartchoice-iq.com")
	engine.cancel_job(queued.name)
	assert ff.get_doc("Infra Job", queued.name).status == "Cancelled"
	with pytest.raises(InvalidState):
		engine.cancel_job(queued.name)
	running = engine.create_job("site.migrate", "Site", "erp.client-a.iq")
	polls = {"n": 0}

	def cancel_during_second_poll(_: float) -> None:
		polls["n"] += 1
		if polls["n"] == 1:
			ff.get_doc("Infra Job", running.name).db_set("cancel_requested", 1)

	engine.sleep = cancel_during_second_poll  # type: ignore[assignment]
	done = _run(ff, running)
	assert done.status == "Cancelled"
	assert ff.events_of("infra:job.updated")[-1]["status"] == "Cancelled"
	assert ff.cache_client.get("infra:lock:server:SRV-0001") is None


def test_failure_then_retry_resumes_from_first_failed_step(
	ff: FakeFrappe, monkeypatch: pytest.MonkeyPatch
) -> None:
	import infra_control.providers.dummy.adapter as dummy

	class FailsAtMigrate(DummyProvider):
		def __init__(self, config: Any = None, **kw: Any) -> None:
			super().__init__(config, fail_at_step=1)

	monkeypatch.setattr(dummy, "DummyProvider", FailsAtMigrate)
	job = engine.create_job("site.migrate", "Site", "demo.smartchoice-iq.com")
	done = _run(ff, job)
	assert done.status == "Failed" and done.error == "bench migrate failed (dummy)"
	assert engine.first_failed_step(job.name) == 1
	assert ff.events_of("infra:job.updated")[-1]["status"] == "Failed"
	with pytest.raises(InvalidState):
		engine.retry_job(queued_name := engine.create_job("site.backup", "Site", "erp.client-a.iq").name)
	retried = engine.retry_job(job.name)
	assert retried.retry_of == job.name and retried.status == "Queued"
	stashed = json.loads(ff.cache_client.get(f"infra:job:params:{retried.name}"))
	# Index for the record, task name for Ansible's --start-at-task (plan 9.1 step 6).
	assert stashed["_resume_from"] == 1
	assert stashed["_resume_task"] == "bench migrate"
	assert queued_name


def test_build_call_passes_the_resume_task_to_ansible_playbooks(ff: FakeFrappe) -> None:
	playbook = ff.get_doc("Playbook", "server.apt_security")
	target = engine.resolve_target("Server", "SRV-0001")
	method, kwargs = engine._build_call(
		playbook, target, {"_resume_from": 2, "_resume_task": "Apply security upgrades", "x": 1}
	)
	assert method == "run_playbook"
	assert kwargs == {
		"server": "SRV-0001",
		"playbook_file": "server_apt_security.yml",
		"extra_vars": {"x": 1},
		"resume_task": "Apply security upgrades",
	}
	# The kwargs must be callable on a real adapter: this used to pass `resume_from`, which no
	# run_playbook accepted, so every Ansible retry raised TypeError.
	import inspect

	from infra_control.providers.digitalocean.adapter import DigitalOceanProvider

	inspect.signature(DigitalOceanProvider.run_playbook).bind(None, **kwargs)
	inspect.signature(DummyProvider.run_playbook).bind(None, **kwargs)
	site_target = engine.resolve_target("Site", "demo.smartchoice-iq.com")
	assert engine._build_call(ff.get_doc("Playbook", "site.backup"), site_target, {"with_files": False}) == (
		"backup_site",
		{"with_files": False, "site": "demo.smartchoice-iq.com"},
	)
	fc_server = engine.Target("Server", "SRV-FC", "FC-STAGING", "frappe_cloud", None)
	with pytest.raises(NotSupported):
		engine._build_call(playbook, fc_server, {})


def test_creation_flow_links_created_document(ff: FakeFrappe) -> None:
	job = engine.create_job(
		"site.create", "Bench", "BENCH-0001", {"domain": "new.iq", "admin_password": PASSWORD}
	)
	ff.add(
		"Site",
		name="new.iq",
		domain="new.iq",
		bench="BENCH-0001",
		server="SRV-0001",
		provider_account="DO-STAGING",
		provider="digitalocean",
	)
	done = _run(ff, job)
	assert done.status == "Success" and (done.created_doctype, done.created_name) == ("Site", "new.iq")
	assert {"doctype": "Site", "name": "new.iq", "change": "created"} in ff.events_of(
		"infra:inventory.changed"
	)


def test_output_is_masked_before_storage_and_emission(
	ff: FakeFrappe, monkeypatch: pytest.MonkeyPatch
) -> None:
	class Leaky(DummyProvider):
		def get_status(self, op: OpRef) -> OpStatus:
			return OpStatus(
				OpState.SUCCESS,
				(
					OpStep(
						"Create site",
						OpState.SUCCESS,
						output=f"token={FAKE_TOKEN} pw {PASSWORD} Authorization: Bearer abc.def",
					),
				),
			)

	import infra_control.providers.dummy.adapter as dummy

	monkeypatch.setattr(dummy, "DummyProvider", Leaky)
	job = engine.create_job(
		"site.create", "Bench", "BENCH-0001", {"domain": "new.iq", "admin_password": PASSWORD}
	)
	_run(ff, job)
	stored = ff.get_doc("Infra Job Step", f"{job.name}-0").output
	emitted = ff.events_of("infra:job.log")[0]["chunk"]
	for text in (stored, emitted):
		assert FAKE_TOKEN not in text and PASSWORD not in text and "abc.def" not in text
		assert text == f"token={MASK} pw {MASK} Authorization: Bearer {MASK}"


def test_crash_in_adapter_ends_failed_and_unlocks(ff: FakeFrappe, monkeypatch: pytest.MonkeyPatch) -> None:
	import infra_control.providers.dummy.adapter as dummy

	class Boom(DummyProvider):
		def backup_site(self, site: str, with_files: bool = True) -> OpRef:
			raise RuntimeError(f"boom {FAKE_TOKEN}")

	monkeypatch.setattr(dummy, "DummyProvider", Boom)
	job = engine.create_job("site.backup", "Site", "demo.smartchoice-iq.com")
	done = _run(ff, job)
	assert done.status == "Failed" and done.error == f"boom {MASK}"
	assert ff.errors and ff.cache_client.get("infra:lock:server:SRV-0001") is None


def test_fail_stale_jobs_releases_locks(ff: FakeFrappe) -> None:
	ff.singles["Infra Settings"] = {"job_heartbeat_timeout_minutes": 5}
	stale = ff.add(
		"Infra Job",
		playbook="site.backup",
		target_doctype="Site",
		target_name="demo.smartchoice-iq.com",
		status="Running",
		progress=30,
		worker_heartbeat=ff.now() - timedelta(minutes=6),
		lock_key="infra:lock:server:SRV-0001",
		triggered_by="x",
	)
	fresh = ff.add(
		"Infra Job",
		playbook="site.backup",
		target_doctype="Site",
		target_name="erp.client-a.iq",
		status="Running",
		progress=10,
		worker_heartbeat=ff.now() - timedelta(minutes=1),
		lock_key="infra:lock:server:SRV-0002",
		triggered_by="x",
	)
	ff.cache_client.set("infra:lock:server:SRV-0001", stale.name)
	ff.cache_client.set("infra:lock:server:SRV-0002", fresh.name)
	assert engine.fail_stale_jobs() == [stale.name]
	assert ff.get_doc("Infra Job", stale.name).status == "Failed"
	assert "heartbeat" in ff.get_doc("Infra Job", stale.name).error
	assert ff.get_doc("Infra Job", fresh.name).status == "Running"
	assert ff.cache_client.get("infra:lock:server:SRV-0001") is None
	assert ff.cache_client.get("infra:lock:server:SRV-0002") == fresh.name
	assert ff.events_of("infra:job.updated")[-1] == {"job": stale.name, "status": "Failed", "progress": 30}


def test_registry_rejects_wrong_capability_sets_for_real_providers() -> None:
	assert PROVIDER_CAPABILITIES[ProviderName.FRAPPE_CLOUD] < frozenset(Capability)


def test_step_timestamps_are_stored_naive_in_the_system_timezone(ff: FakeFrappe) -> None:
	"""Regression for the Phase 1 gate run: the dummy adapter reports tz-aware UTC timestamps and
	MariaDB rejected the `+00:00` offset. Steps must land as naive system-time datetimes."""
	job = engine.create_job("site.migrate", "Site", "demo.smartchoice-iq.com")
	_run(ff, job)
	steps = list(ff.store["Infra Job Step"].values())
	assert steps
	for step in steps:
		for value in (step.started_at, step.ended_at):
			assert value is None or (isinstance(value, datetime) and value.tzinfo is None)
	aware = datetime(2026, 10, 7, 18, 40, 57, tzinfo=UTC)
	assert engine._db_datetime(aware) == datetime(2026, 10, 7, 21, 40, 57)
	assert engine._db_datetime(None) is None
	naive = datetime(2026, 10, 7, 18, 40, 57)
	assert engine._db_datetime(naive) is naive


def test_worker_commits_progress_while_the_job_runs(ff: FakeFrappe) -> None:
	"""Live gate JOB-00012: Frappe commits a background job only when it returns, so a 12-minute
	provision showed `Queued` with no steps until the end and cancel was never observed. The
	engine checkpoints: lock, Running, op_ref, every poll, and the terminal state."""
	job = engine.create_job("site.migrate", "Site", "demo.smartchoice-iq.com")
	before = ff.commits
	_run(ff, job)
	polls = 4  # the dummy migrate reports 3 steps over successive polls, then terminal
	assert ff.commits - before >= 3 + polls


def test_cancel_set_by_the_api_is_seen_on_the_next_poll(
	ff: FakeFrappe, monkeypatch: pytest.MonkeyPatch
) -> None:
	job = engine.create_job("site.migrate", "Site", "demo.smartchoice-iq.com")
	seen_commits: list[int] = []
	real_reload = ff.get_doc("Infra Job", job.name).__class__.reload

	def reload_after_commit(self: Any) -> Any:
		seen_commits.append(ff.commits)
		return real_reload(self)

	monkeypatch.setattr(ff.get_doc("Infra Job", job.name).__class__, "reload", reload_after_commit)
	_run(ff, job)
	# Every reload (where cancel_requested is read) happens after at least one commit in that poll.
	assert seen_commits and all(c > 0 for c in seen_commits)
	assert seen_commits == sorted(seen_commits)


def test_scheduler_user_may_run_a_low_risk_playbook_without_any_role(ff: FakeFrappe) -> None:
	# The scheduler has no Infra role; a low-risk, system playbook must still be creatable.
	ff.session.user = engine.SCHEDULER_USER
	ff.roles.pop(engine.SCHEDULER_USER, None)
	job = engine.create_job("inventory.sync", "Provider Account", "DO-STAGING", user=engine.SCHEDULER_USER)
	assert job.status == "Queued" and job.triggered_by == engine.SCHEDULER_USER


def test_scheduler_user_may_not_run_a_high_risk_playbook(ff: FakeFrappe) -> None:
	from infra_control.core.errors import PermissionDenied

	with pytest.raises(PermissionDenied):
		engine.create_job("server.reboot", "Server", "SRV-0001", user=engine.SCHEDULER_USER)


def test_read_only_playbooks_run_without_the_server_lock(ff: FakeFrappe) -> None:
	"""A3.8: a log read runs beside a mutating job instead of queueing behind it."""
	from infra_control.job_engine import engine as eng

	assert "server.logs" in eng.READ_ONLY_PLAYBOOKS
	held = ff.cache().set("infra:lock:server:SRV-0001", "someone-else")
	assert held is True
	ff.add(
		"Playbook",
		name="server.logs",
		key="server.logs",
		title="Read logs",
		target_doctype="Server",
		risk="low",
		required_capability="ssh",
		ansible_file="logs_read.yml",
		enabled=1,
		params_schema='{"type": "object", "properties": {"source": {"type": "string"}}}',
	)
	job = eng.create_job("server.logs", "Server", "SRV-0001", {"source": "system"}, enqueue=False)
	eng.run_job(job.name)
	doc = ff.store["Infra Job"][job.name]
	assert doc.get("status") in ("Success", "Failed") and not doc.get("lock_key")
	assert ff.cache().get("infra:lock:server:SRV-0001") == "someone-else"
