"""A2.2: AnsibleRunner. Events are written to disk the way ansible-runner writes them; no
Ansible process is started (an injected launcher records the call)."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from infra_control.core.errors import ProviderError, ValidationError
from infra_control.providers.base import OpRef, OpState
from infra_control.providers.digitalocean.ansible import (
	KIND,
	AnsibleRunner,
	default_playbooks_dir,
	inventory_for,
	steps_from_events,
)

SERVER = {
	"name": "SRV-0001",
	"hostname": "app-01.fra1",
	"public_ip": "164.92.10.11",
	"ssh_user": "frappe",
	"ssh_port": 22,
	"role": "app",
}


def ev(counter: int, event: str, task: str = "", uuid: str = "", **data: Any) -> dict[str, Any]:
	payload: dict[str, Any] = {"task_uuid": uuid, "task": task, **data}
	return {
		"counter": counter,
		"event": event,
		"created": f"2026-10-07T10:00:{counter:02d}.000000+00:00",
		"stdout": data.pop("stdout", "") if "stdout" in data else "",
		"event_data": payload,
	}


def task_events() -> list[dict[str, Any]]:
	return [
		ev(1, "playbook_on_start"),
		ev(2, "playbook_on_task_start", "Install packages", "t1"),
		ev(3, "runner_on_ok", "Install packages", "t1", stdout="changed: [SRV-0001]"),
		ev(4, "playbook_on_task_start", "Optional cleanup", "t2"),
		ev(5, "runner_on_failed", "Optional cleanup", "t2", ignore_errors=True, res={"msg": "nope"}),
		ev(6, "playbook_on_task_start", "Skipped on containers", "t3"),
		ev(7, "runner_on_skipped", "Skipped on containers", "t3"),
		ev(8, "playbook_on_task_start", "Restart nginx", "t4"),
		ev(9, "runner_on_failed", "Restart nginx", "t4", res={"msg": "Job for nginx.service failed"}),
	]


def test_steps_from_events_one_step_per_task() -> None:
	steps, error = steps_from_events(task_events())
	assert [(s.name, s.state) for s in steps] == [
		("Install packages", OpState.SUCCESS),
		("Optional cleanup", OpState.SUCCESS),
		("Skipped on containers", OpState.SUCCESS),
		("Restart nginx", OpState.FAILED),
	]
	assert steps[0].output == ["changed: [SRV-0001]\n"]
	assert steps[1].output == ["nope\n", "failed, ignored\n"]  # the message, then the marker
	assert steps[2].output == ["skipped\n"]
	assert steps[0].started_at == datetime(2026, 10, 7, 10, 0, 2, tzinfo=UTC)
	assert error == "Restart nginx: Job for nginx.service failed"


def test_unreachable_host_is_a_failed_step() -> None:
	steps, error = steps_from_events(
		[
			ev(1, "playbook_on_task_start", "Gathering Facts", "t0"),
			ev(2, "runner_on_unreachable", "Gathering Facts", "t0", res={"msg": "ssh: connect timed out"}),
		]
	)
	assert steps[0].state is OpState.FAILED
	assert error == "Gathering Facts: unreachable: ssh: connect timed out"


def test_inventory_for_one_host() -> None:
	inv = inventory_for(SERVER, "/home/frappe/.ssh/id_ed25519")
	host = inv["all"]["hosts"]["SRV-0001"]
	assert host == {
		"ansible_host": "164.92.10.11",
		"ansible_user": "frappe",
		"ansible_port": 22,
		"ansible_ssh_private_key_file": "/home/frappe/.ssh/id_ed25519",
		"ansible_python_interpreter": "/usr/bin/python3",
		"server_role": "app",
	}
	with pytest.raises(ValidationError):
		inventory_for({"name": "x"}, "/k")


@pytest.fixture
def playbooks(tmp_path: Path) -> Path:
	d = tmp_path / "ansible" / "playbooks"
	d.mkdir(parents=True)
	(d / "service_control.yml").write_text("- hosts: all\n  tasks: []\n")
	(tmp_path / "secret.yml").write_text("x")
	return d


def make_runner(tmp_path: Path, playbooks: Path) -> tuple[AnsibleRunner, list[dict[str, Any]]]:
	calls: list[dict[str, Any]] = []
	runner = AnsibleRunner(
		root=tmp_path / "runs",
		playbooks_dir=playbooks,
		ssh_key_path="/home/frappe/.ssh/id_ed25519",
		launcher=lambda **kw: calls.append(kw),
		ident_factory=lambda: "run1",
	)
	return runner, calls


def write_artifacts(
	root: Path, ident: str, events: list[dict[str, Any]], status: str | None, rc: int | None = None
) -> None:
	art = root / ident / "artifacts" / ident
	(art / "job_events").mkdir(parents=True, exist_ok=True)
	for e in events:
		(art / "job_events" / f"{e['counter']}-x.json").write_text(json.dumps(e))
	if status is not None:
		(art / "status").write_text(status)
	if rc is not None:
		(art / "rc").write_text(str(rc))


def test_start_launches_ansible_runner_with_inventory_vars_and_resume(
	tmp_path: Path, playbooks: Path
) -> None:
	runner, calls = make_runner(tmp_path, playbooks)
	ref = runner.start(
		SERVER, "service_control.yml", {"service": "nginx", "action": "reload"}, start_at_task="Reload nginx"
	)
	assert ref == OpRef("digitalocean", KIND, "run1")
	(kw,) = calls
	assert kw["private_data_dir"] == str(tmp_path / "runs" / "run1")
	assert kw["ident"] == "run1"
	assert kw["playbook"] == str((playbooks / "service_control.yml").resolve())
	assert kw["extravars"]["service"] == "nginx" and kw["extravars"]["action"] == "reload"
	# Every run gets a results dir for playbooks that write per-host output (discovery).
	assert kw["extravars"]["discovery_dest"].endswith("/results")
	assert kw["inventory"]["all"]["hosts"]["SRV-0001"]["ansible_host"] == "164.92.10.11"
	assert kw["cmdline"] == "--start-at-task 'Reload nginx'"
	assert kw["envvars"]["ANSIBLE_ROLES_PATH"].endswith("ansible/roles")
	assert "StrictHostKeyChecking=accept-new" in kw["envvars"]["ANSIBLE_SSH_ARGS"]
	assert kw["cancel_callback"]() is False
	assert "binary" not in kw  # RAW mode would drop the playbook argument
	assert kw["envvars"]["PATH"].split(":")[0] == str(Path(sys.executable).parent)


def test_start_refuses_playbooks_outside_the_playbooks_dir(tmp_path: Path, playbooks: Path) -> None:
	runner, calls = make_runner(tmp_path, playbooks)
	for bad in ("../../secret.yml", "/etc/passwd", "missing.yml"):
		with pytest.raises(ValidationError):
			runner.start(SERVER, bad)
	assert calls == []


def test_status_is_rebuilt_from_disk_by_any_instance(tmp_path: Path, playbooks: Path) -> None:
	runner, _ = make_runner(tmp_path, playbooks)
	ref = runner.start(SERVER, "service_control.yml")
	running = runner.status(ref)
	assert running.state is OpState.RUNNING and running.steps == ()

	write_artifacts(tmp_path / "runs", "run1", task_events()[:3], status="running")
	partial = runner.status(ref)
	assert partial.state is OpState.RUNNING
	assert [s.name for s in partial.steps] == ["Install packages"]

	write_artifacts(tmp_path / "runs", "run1", task_events(), status="failed", rc=2)
	fresh = AnsibleRunner(root=tmp_path / "runs", playbooks_dir=playbooks, ssh_key_path="/k")
	done = fresh.status(ref)
	assert done.state is OpState.FAILED
	assert done.error == "Restart nginx: Job for nginx.service failed"
	assert [s.state for s in done.steps][-1] is OpState.FAILED


def test_terminal_states_settle_dangling_steps(tmp_path: Path, playbooks: Path) -> None:
	runner, _ = make_runner(tmp_path, playbooks)
	ref = runner.start(SERVER, "service_control.yml")
	dangling = [ev(1, "playbook_on_task_start", "Long task", "t1")]
	write_artifacts(tmp_path / "runs", "run1", dangling, status="canceled")
	assert runner.status(ref).steps[0].state is OpState.CANCELLED
	write_artifacts(tmp_path / "runs", "run1", dangling, status="timeout", rc=254)
	timed_out = runner.status(ref)
	assert timed_out.state is OpState.FAILED and timed_out.error == "Ansible run timed out"
	assert timed_out.steps[0].state is OpState.FAILED
	write_artifacts(tmp_path / "runs", "run1", [], status="failed", rc=4)
	assert runner.status(ref).error == "Ansible exited with rc 4"


def test_cancel_drops_the_marker_the_callback_reads(tmp_path: Path, playbooks: Path) -> None:
	runner, calls = make_runner(tmp_path, playbooks)
	ref = runner.start(SERVER, "service_control.yml")
	assert calls[0]["cancel_callback"]() is False
	assert runner.cancel(ref) is True
	assert calls[0]["cancel_callback"]() is True
	assert runner.cancel(OpRef("digitalocean", KIND, "unknown")) is False
	with pytest.raises(ProviderError):
		runner.status(OpRef("digitalocean", KIND, "unknown"))


# --- the shipped Ansible content -------------------------------------------------------------
ANSIBLE_DIR = default_playbooks_dir().parent


def test_default_playbooks_dir_is_the_repo_ansible_folder() -> None:
	assert default_playbooks_dir().is_dir()
	assert (ANSIBLE_DIR / "roles").is_dir()


@pytest.mark.parametrize(
	"playbook", ["server_provision.yml", "service_control.yml", "server_apt_security.yml"]
)
def test_playbooks_the_adapter_references_exist_and_parse(playbook: str) -> None:
	data = yaml.safe_load((default_playbooks_dir() / playbook).read_text())
	assert isinstance(data, list) and all("hosts" in play for play in data)


def test_roles_use_only_builtin_modules() -> None:
	"""The controller ships plain ansible-core: no collection may be required at run time."""
	offenders = []
	for path in (ANSIBLE_DIR / "roles").rglob("*.yml"):
		for task in yaml.safe_load(path.read_text()) or []:
			if not isinstance(task, dict):
				continue
			for key in task:
				if "." in key and not key.startswith("ansible.builtin."):
					offenders.append(f"{path.relative_to(ANSIBLE_DIR)}: {key}")
	assert offenders == []


def test_provision_role_map_covers_every_server_role() -> None:
	from infra_control.core.enums import ServerRole

	plays = yaml.safe_load((default_playbooks_dir() / "server_provision.yml").read_text())
	role_map = plays[1]["vars"]["role_map"]
	assert set(role_map) == {str(r) for r in ServerRole}
	for roles in role_map.values():
		assert roles[0] == "base"
		for role in roles:
			assert (ANSIBLE_DIR / "roles" / role / "tasks" / "main.yml").is_file()


CONFLICTING_PACKAGES = [{"libmariadb-dev", "libmysqlclient-dev"}]


def test_roles_never_install_conflicting_packages() -> None:
	"""Molecule caught this: two roles installing conflicting packages swap them on every run,
	so no server could ever converge (changed on every run)."""
	installed: set[str] = set()
	for defaults in (ANSIBLE_DIR / "roles").glob("*/defaults/main.yml"):
		for value in (yaml.safe_load(defaults.read_text()) or {}).values():
			if isinstance(value, list):
				installed.update(str(v) for v in value)
	for group in CONFLICTING_PACKAGES:
		assert len(group & installed) <= 1, f"conflicting packages {sorted(group & installed)}"


def test_ansible_runner_builds_a_playbook_command_from_our_arguments(tmp_path: Path, playbooks: Path) -> None:
	"""Regression for the live gate: feed ansible-runner's real config the exact kwargs start()
	produces and check the generated command runs the playbook (and honours --start-at-task)."""
	ansible_runner = pytest.importorskip("ansible_runner")
	from ansible_runner.config.runner import RunnerConfig

	runner, calls = make_runner(tmp_path, playbooks)
	runner.start(SERVER, "service_control.yml", {"service": "nginx"}, start_at_task="Reload nginx")
	from ansible_runner.utils import dump_artifacts

	kw = dict(calls[0])
	dump_artifacts(kw)  # what run_async does first: writes the inventory dict to a file
	allowed = {
		"private_data_dir",
		"ident",
		"playbook",
		"inventory",
		"extravars",
		"envvars",
		"cmdline",
		"suppress_env_files",
		"binary",  # the argument that broke the live run must reach the real config
	}
	config = RunnerConfig(**{k: v for k, v in kw.items() if k in allowed})
	config.prepare()
	command = config.command
	assert ansible_runner is not None
	assert command[0].endswith("ansible-playbook")
	assert str((playbooks / "service_control.yml").resolve()) in command
	assert "--start-at-task" in command and "Reload nginx" in command


def test_start_many_runs_one_play_against_several_servers_with_a_results_dir(
	tmp_path: Path, playbooks: Path
) -> None:
	(playbooks / "inventory_discover.yml").write_text("- hosts: all\n  tasks: []\n")
	runner, calls = make_runner(tmp_path, playbooks)
	a = {**SERVER, "name": "gate-02.fra1", "public_ip": "1.1.1.1"}
	b = {**SERVER, "name": "gate-03.fra1", "public_ip": "2.2.2.2"}
	ref = runner.start_many([a, b], "inventory_discover.yml", {})
	(kw,) = calls
	hosts = kw["inventory"]["all"]["hosts"]
	assert set(hosts) == {"gate-02.fra1", "gate-03.fra1"}
	assert hosts["gate-03.fra1"]["ansible_host"] == "2.2.2.2"
	# The playbook is told where to drop per-host JSON, and the dir exists.
	dest = kw["extravars"]["discovery_dest"]
	assert Path(dest).is_dir() and dest == str(runner.results_dir(ref))


def test_read_results_and_unreachable_from_disk(tmp_path: Path, playbooks: Path) -> None:
	(playbooks / "inventory_discover.yml").write_text("- hosts: all\n  tasks: []\n")
	runner, _ = make_runner(tmp_path, playbooks)
	ref = runner.start_many([SERVER], "inventory_discover.yml", {})
	(runner.results_dir(ref) / "gate-03.fra1.json").write_text('{"benches": [{"path": "/x"}]}')
	(runner.results_dir(ref) / "broken.json").write_text("{not json")
	assert runner.read_results(ref) == {"gate-03.fra1": {"benches": [{"path": "/x"}]}}
	# unreachable comes from the run's events.
	write_artifacts(
		tmp_path / "runs",
		ref.external_id,
		[ev(1, "runner_on_unreachable", "Scan", "t1", host="dead.fra1", res={"msg": "timed out"})],
		status="successful",
	)
	assert runner.unreachable(ref) == ["dead.fra1"]


def test_ignore_unreachable_run_stays_success_and_annotates_the_step(tmp_path: Path, playbooks: Path) -> None:
	(playbooks / "inventory_discover.yml").write_text("- hosts: all\n  tasks: []\n")
	runner, _ = make_runner(tmp_path, playbooks)
	ref = runner.start_many([SERVER], "inventory_discover.yml", {})
	events = [
		ev(1, "playbook_on_task_start", "Scan for benches", "t1"),
		ev(2, "runner_on_ok", "Scan for benches", "t1", host="gate-02.fra1", stdout="{}"),
		ev(
			3,
			"runner_on_unreachable",
			"Scan for benches",
			"t1",
			host="dead.fra1",
			res={"msg": "ssh timed out"},
		),
	]
	write_artifacts(tmp_path / "runs", ref.external_id, events, status="successful")
	status = runner.status(ref)
	assert status.state is OpState.SUCCESS and status.error is None
	assert "unreachable, skipped: dead.fra1" in status.steps[0].output


def test_step_output_carries_command_stdout_debug_messages_and_loop_items() -> None:
	"""Operators asked to see what a task did, not only `ok: [host]`."""
	from infra_control.providers.digitalocean.ansible import _clip, steps_from_events

	events = [
		ev(1, "playbook_on_task_start", "bench version", "t1"),
		ev(
			2,
			"runner_on_ok",
			"bench version",
			"t1",
			stdout="ok: [SRV-0001]",
			res={"stdout": "frappe 15.98.1\nerpnext 15.95.2", "msg": "non-zero return code"},
		),
		ev(3, "playbook_on_task_start", "Report", "t2"),
		ev(
			4,
			"runner_on_ok",
			"Report",
			"t2",
			stdout="ok: [SRV-0001]",
			res={"msg": "updated: erpnext 1a2b -> 3c4d"},
		),
		ev(5, "playbook_on_task_start", "Pull", "t3"),
		ev(
			6,
			"runner_on_ok",
			"Pull",
			"t3",
			stdout="ok: [SRV-0001]",
			res={
				"results": [
					{"item": "frappe", "stdout": "Already up to date."},
					{"item": "erpnext", "stdout": "Updating 1a2b..3c4d"},
				]
			},
		),
		ev(7, "playbook_on_task_start", "Secret", "t4"),
		ev(
			8,
			"runner_on_ok",
			"Secret",
			"t4",
			stdout="ok: [SRV-0001]",
			res={"censored": "the output has been hidden due to the fact that 'no_log: true' was specified"},
		),
		ev(9, "playbook_on_task_start", "Fails", "t5"),
		ev(
			10,
			"runner_on_failed",
			"Fails",
			"t5",
			stdout="fatal: [SRV-0001]",
			res={"stdout": "", "stderr": "fatal: not a git repository", "msg": "non-zero return code"},
		),
	]
	steps, first_error = steps_from_events(events)
	outputs = ["".join(s.output) for s in steps]
	assert "frappe 15.98.1\nerpnext 15.95.2" in outputs[0] and "non-zero" not in outputs[0]
	assert "updated: erpnext 1a2b -> 3c4d" in outputs[1]
	assert "[frappe] Already up to date." in outputs[2] and "[erpnext] Updating 1a2b..3c4d" in outputs[2]
	assert outputs[3].strip() == "ok: [SRV-0001]"  # censored results add nothing
	assert (
		"stderr: fatal: not a git repository" in outputs[4]
		and first_error == "Fails: fatal: not a git repository"
	)
	assert "characters omitted" in _clip("x" * 40_000) and len(_clip("x" * 40_000)) < 17_000
