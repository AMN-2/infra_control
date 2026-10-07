"""`AnsibleRunner`: the `PlaybookRunner` behind every SSH-backed DigitalOcean operation (A2.2).

Plan 9.1 step 3: ansible-runner events map 1:1 to `Infra Job Step`. One step per task.

Design:
- `start()` writes a private data dir (`<root>/<ident>/`) with a one-host inventory, the extra
  vars and the SSH key path, then launches `ansible_runner.run_async` in a background thread of
  the worker process. The `OpRef` external id is the ident.
- `status()` never relies on in-memory state: it rebuilds the steps from the run's
  `artifacts/<ident>/job_events/*.json` and the overall state from `artifacts/<ident>/status`.
  A fresh adapter instance (worker restart, retry, crash recovery) reads the same answer.
- `cancel()` drops a `cancel` marker file the run's cancel callback checks.
- Retry resumes with `--start-at-task <name of the first failed step>` (plan 9.1 step 6).

`ansible_runner` is imported lazily so the controller still starts when it is missing; the
adapter then falls back to `UnavailableRunner`.
"""

from __future__ import annotations

import json
import shlex
import shutil
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from infra_control.core.errors import ProviderError, ValidationError
from infra_control.providers.base import OpRef, OpState, OpStatus, OpStep

KIND = "ansible"
CANCEL_MARKER = "cancel"
OUTPUT_PER_STEP_MAX = 16 * 1024
SSH_ARGS = (
	"-o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 "
	"-o ControlMaster=auto -o ControlPersist=60s"
)

# ansible-runner `status` file → OpState. Absent or `starting`/`running` → still running.
_RUN_STATUS: dict[str, OpState] = {
	"successful": OpState.SUCCESS,
	"failed": OpState.FAILED,
	"timeout": OpState.FAILED,
	"canceled": OpState.CANCELLED,
}


@dataclass
class _Step:
	name: str
	uuid: str
	state: OpState = OpState.RUNNING
	output: list[str] = field(default_factory=list)
	started_at: datetime | None = None
	ended_at: datetime | None = None
	error: str | None = None


def _ts(event: dict[str, Any]) -> datetime | None:
	raw = event.get("created")
	if not isinstance(raw, str):
		return None
	try:
		dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
	except ValueError:
		return None
	return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _result_message(res: dict[str, Any]) -> str:
	for key in ("msg", "stderr", "module_stderr", "reason"):
		value = res.get(key)
		if isinstance(value, str) and value.strip():
			return value.strip()
	return "task failed"


def steps_from_events(events: list[dict[str, Any]]) -> tuple[list[_Step], str | None]:
	"""Pure: ansible-runner job events (in counter order) → steps and the first failure message."""
	steps: list[_Step] = []
	by_uuid: dict[str, _Step] = {}
	first_error: str | None = None
	for ev in events:
		kind = ev.get("event")
		data = ev.get("event_data") or {}
		if not isinstance(data, dict):
			continue
		task_uuid = str(data.get("task_uuid") or "")
		if kind == "playbook_on_task_start":
			name = str(data.get("task") or data.get("name") or "task")
			started = _Step(name=name, uuid=task_uuid, started_at=_ts(ev))
			steps.append(started)
			by_uuid[task_uuid] = started
			continue
		step = by_uuid.get(task_uuid)
		if step is None:
			continue
		stdout = ev.get("stdout")
		if isinstance(stdout, str) and stdout.strip():
			step.output.append(stdout.strip() + "\n")
		raw_res = data.get("res")
		res: dict[str, Any] = raw_res if isinstance(raw_res, dict) else {}
		if kind == "runner_on_ok":
			step.state, step.ended_at = OpState.SUCCESS, _ts(ev)
		elif kind == "runner_on_skipped":
			step.state, step.ended_at = OpState.SUCCESS, _ts(ev)
			if not step.output:
				step.output.append("skipped\n")
		elif kind in ("runner_on_failed", "runner_on_unreachable"):
			ignored = bool(data.get("ignore_errors")) and kind == "runner_on_failed"
			step.ended_at = _ts(ev)
			if ignored:
				step.state = OpState.SUCCESS
				step.output.append("failed, ignored\n")
			else:
				step.state = OpState.FAILED
				step.error = ("unreachable: " if kind == "runner_on_unreachable" else "") + _result_message(
					res
				)
				first_error = first_error or f"{step.name}: {step.error}"
	return steps, first_error


def read_events(artifact_dir: Path) -> list[dict[str, Any]]:
	events_dir = artifact_dir / "job_events"
	if not events_dir.is_dir():
		return []
	events: list[dict[str, Any]] = []
	for path in events_dir.glob("*.json"):
		try:
			data = json.loads(path.read_text())
		except (OSError, ValueError):
			continue  # a file being written right now; picked up on the next poll
		if isinstance(data, dict):
			events.append(data)
	events.sort(key=lambda e: int(e.get("counter") or 0))
	return events


def inventory_for(server: dict[str, Any], ssh_key_path: str) -> dict[str, Any]:
	host = str(server.get("name") or server.get("hostname") or "target")
	address = server.get("public_ip") or server.get("private_ip")
	if not address:
		raise ValidationError("Server has no IP address to connect to", {"server": host})
	return {
		"all": {
			"hosts": {
				host: {
					"ansible_host": str(address),
					"ansible_user": str(server.get("ssh_user") or "frappe"),
					"ansible_port": int(server.get("ssh_port") or 22),
					"ansible_ssh_private_key_file": ssh_key_path,
					"ansible_python_interpreter": "/usr/bin/python3",
					"server_role": str(server.get("role") or "all"),
				}
			}
		}
	}


class AnsibleRunner:
	def __init__(
		self,
		*,
		root: Path | str,
		playbooks_dir: Path | str,
		ssh_key_path: str,
		launcher: Callable[..., Any] | None = None,
		ident_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
	) -> None:
		self.root = Path(root)
		self.playbooks_dir = Path(playbooks_dir)
		self.ssh_key_path = ssh_key_path
		self._launcher = launcher
		self._ident = ident_factory

	# --- launching ---------------------------------------------------------------------------
	def _launch(self, **kwargs: Any) -> Any:
		if self._launcher is not None:
			return self._launcher(**kwargs)
		import ansible_runner

		return ansible_runner.run_async(**kwargs)

	def start(
		self,
		server: dict[str, Any],
		playbook_file: str,
		extra_vars: dict[str, Any] | None = None,
		*,
		start_at_task: str | None = None,
	) -> OpRef:
		playbook = (self.playbooks_dir / playbook_file).resolve()
		if self.playbooks_dir.resolve() not in playbook.parents or not playbook.is_file():
			raise ValidationError("Unknown playbook file", {"playbook": playbook_file})
		ident = self._ident()
		private = self.root / ident
		private.mkdir(parents=True, exist_ok=False)
		cancel_marker = private / CANCEL_MARKER
		cmdline = f"--start-at-task {shlex.quote(start_at_task)}" if start_at_task else None
		self._launch(
			private_data_dir=str(private),
			ident=ident,
			playbook=str(playbook),
			inventory=inventory_for(server, self.ssh_key_path),
			extravars=dict(extra_vars or {}),
			envvars={
				"ANSIBLE_ROLES_PATH": str(self.playbooks_dir.parent / "roles"),
				"ANSIBLE_SSH_ARGS": SSH_ARGS,
				"ANSIBLE_FORCE_COLOR": "0",
				"ANSIBLE_NOCOLOR": "1",
			},
			cmdline=cmdline,
			quiet=True,
			cancel_callback=cancel_marker.exists,
			# Facts stay in the artifacts; secrets in extravars are masked by the engine on output.
			suppress_env_files=True,
			binary=ansible_playbook_binary(),
		)
		return OpRef("digitalocean", KIND, ident)

	# --- polling -----------------------------------------------------------------------------
	def _artifact_dir(self, ident: str) -> Path:
		return self.root / ident / "artifacts" / ident

	def status(self, op: OpRef) -> OpStatus:
		private = self.root / op.external_id
		if not private.is_dir():
			raise ProviderError("Unknown Ansible run", {"op": op.to_dict()})
		artifacts = self._artifact_dir(op.external_id)
		steps, error = steps_from_events(read_events(artifacts))
		status_file = artifacts / "status"
		raw = status_file.read_text().strip() if status_file.is_file() else ""
		state = _RUN_STATUS.get(raw, OpState.RUNNING)
		if state is OpState.FAILED and error is None:
			rc_file = artifacts / "rc"
			rc = rc_file.read_text().strip() if rc_file.is_file() else "?"
			error = "Ansible run timed out" if raw == "timeout" else f"Ansible exited with rc {rc}"
		if state is OpState.CANCELLED:
			steps = [
				_Step(s.name, s.uuid, OpState.CANCELLED, s.output, s.started_at, s.ended_at)
				if s.state is OpState.RUNNING
				else s
				for s in steps
			]
		elif state.terminal:
			# A task still "running" when the run ended never reported; treat it as failed.
			for s in steps:
				if s.state is OpState.RUNNING:
					s.state = OpState.FAILED if state is OpState.FAILED else OpState.SUCCESS
		return OpStatus(
			state=state,
			steps=tuple(
				OpStep(
					s.name,
					s.state,
					output="".join(s.output)[-OUTPUT_PER_STEP_MAX:],
					started_at=s.started_at,
					ended_at=s.ended_at,
				)
				for s in steps
			),
			error=error,
		)

	def cancel(self, op: OpRef) -> bool:
		private = self.root / op.external_id
		if not private.is_dir():
			return False
		(private / CANCEL_MARKER).touch()
		return True


def default_playbooks_dir() -> Path:
	"""`<app root>/ansible/playbooks` (bench installs the app in place)."""
	return Path(__file__).resolve().parents[3] / "ansible" / "playbooks"


def ansible_runner_available() -> bool:
	try:
		import ansible_runner  # noqa: F401
	except ImportError:
		return False
	return True


def ansible_playbook_binary() -> str:
	"""`ansible-playbook` next to the worker's Python (the bench venv), else from PATH.

	A bench worker's PATH does not always include the venv's `bin`, so ansible-runner would not
	find the binary that `bench setup requirements` installed."""
	local = Path(sys.executable).with_name("ansible-playbook")
	if local.is_file():
		return str(local)
	return shutil.which("ansible-playbook") or "ansible-playbook"
