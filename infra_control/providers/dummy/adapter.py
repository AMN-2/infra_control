"""`DummyProvider`: completes every operation after a fixed number of status polls.

Used by the job engine tests (A1.2) and by `playbook: dummy.*` runs that exercise the full
enqueue -> lock -> steps -> realtime path without touching real infrastructure.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from infra_control.core.enums import Capability
from infra_control.providers.base import OpRef, OpState, OpStatus, OpStep, Provider
from infra_control.providers.registry import register

ALL_CAPABILITIES: frozenset[Capability] = frozenset(Capability)


@dataclass
class _Op:
	method: str
	steps: list[str]
	polls_per_step: int
	polls: int = 0
	cancelled: bool = False
	fail_at_step: int | None = None
	created: tuple[str, str] | None = None
	log: list[str] = field(default_factory=list)


@register
class DummyProvider(Provider):
	name = "dummy"
	capabilities = ALL_CAPABILITIES

	_ids = itertools.count(1)

	def __init__(
		self, config: Any = None, *, polls_per_step: int = 1, fail_at_step: int | None = None
	) -> None:
		self.config = config
		self.polls_per_step = polls_per_step
		self.fail_at_step = fail_at_step
		self.ops: dict[str, _Op] = {}
		self.calls: list[tuple[str, dict[str, Any]]] = []

	# --- helpers ------------------------------------------------------------------------
	def _start(
		self, method: str, steps: list[str], created: tuple[str, str] | None = None, **kw: Any
	) -> OpRef:
		self.calls.append((method, kw))
		op_id = f"dummy-{next(self._ids)}"
		self.ops[op_id] = _Op(
			method, steps, self.polls_per_step, fail_at_step=self.fail_at_step, created=created
		)
		return OpRef(provider=self.name, kind="dummy", external_id=op_id)

	# --- site level ---------------------------------------------------------------------
	def create_site(self, site: str, bench: str, apps: list[str] | None = None, **kw: Any) -> OpRef:
		return self._start(
			"create_site",
			["Create site", "Install apps"],
			created=("Site", site),
			site=site,
			bench=bench,
			apps=apps,
			**kw,
		)

	def backup_site(self, site: str, with_files: bool = True) -> OpRef:
		return self._start(
			"backup_site", ["Backup database", "Backup files" if with_files else "Skip files"], site=site
		)

	def restore_site(self, site: str, backup_ref: str) -> OpRef:
		return self._start("restore_site", ["Restore"], site=site, backup_ref=backup_ref)

	def update_site(self, site: str) -> OpRef:
		return self._start(
			"update_site", ["Enable maintenance mode", "bench migrate", "Disable maintenance mode"], site=site
		)

	def update_bench(
		self,
		bench: str,
		apps: list[str] | None = None,
		branch: str = "",
		migrate: bool = True,
		build: bool = True,
	) -> OpRef:
		steps = ["Fetch", "Pull (fast-forward only)", "Install requirements"]
		if migrate:
			steps += ["Backup every site before migrating", "bench migrate"]
		if build:
			steps.append("bench build")
		steps.append("bench restart")
		return self._start(
			"update_bench", steps, bench=bench, apps=apps, branch=branch, migrate=migrate, build=build
		)

	def add_app(self, bench: str, app: str, repo: str, branch: str = "", connection: str = "") -> OpRef:
		return self._start(
			"add_app", ["bench get-app", "Report"], bench=bench, app=app, repo=repo, branch=branch
		)

	def install_app(self, site: str, app: str) -> OpRef:
		return self._start(
			"install_app",
			[
				"Backup before installing",
				"Enable maintenance mode",
				"bench install-app",
				"Disable maintenance mode",
			],
			site=site,
			app=app,
		)

	def set_maintenance(self, site: str, on: bool) -> OpRef:
		return self._start("set_maintenance", ["Set maintenance"], site=site, on=on)

	def add_domain(self, site: str, domain: str) -> OpRef:
		return self._start("add_domain", ["Add domain"], site=site, domain=domain)

	def suspend_site(self, site: str, suspended: bool) -> OpRef:
		return self._start("suspend_site", ["Suspend"], site=site, suspended=suspended)

	def restore_test_site(self, site: str, backup_ref: str) -> OpRef:
		return self._start(
			"restore_test_site",
			["Restore into a throwaway site", "Probe", "Drop the throwaway site"],
			site=site,
			backup_ref=backup_ref,
		)

	def delete_site(self, site: str) -> OpRef:
		return self._start(
			"delete_site", ["Last backup before deleting", "bench drop-site", "Reload nginx"], site=site
		)

	def deprovision_server(self, server: str) -> OpRef:
		return self._start("deprovision_server", ["Delete droplet"], server=server)

	# --- optional -----------------------------------------------------------------------
	def create_server(self, **kw: Any) -> OpRef:
		return self._start(
			"create_server",
			["Create droplet", "Wait for cloud-init", "Role base"],
			created=("Server", str(kw.get("hostname", "dummy-server"))),
			**kw,
		)

	def reboot_server(self, server: str) -> OpRef:
		return self._start("reboot_server", ["Reboot"], server=server)

	def snapshot_server(self, server: str) -> OpRef:
		return self._start("snapshot_server", ["Snapshot"], server=server)

	def control_service(self, server: str, service: str, action: str) -> OpRef:
		return self._start(
			"control_service", [f"{action} {service}"], server=server, service=service, action=action
		)

	def get_metrics(self, server: str) -> dict[str, Any]:
		self.calls.append(("get_metrics", {"server": server}))
		return {"cpu": 1.0, "ram": 2.0, "disk": 3.0, "load1": 0.1, "queue_backlog": 0}

	def run_playbook(
		self,
		server: str,
		playbook_file: str,
		extra_vars: dict[str, Any] | None = None,
		resume_task: str | None = None,
	) -> OpRef:
		return self._start(
			"run_playbook", [f"Run {playbook_file}"], server=server, playbook_file=playbook_file
		)

	# --- lifecycle ----------------------------------------------------------------------
	def sync_inventory(self) -> OpRef | dict[str, Any]:
		self.calls.append(("sync_inventory", {}))
		return {"servers_created": 0, "servers_updated": 0, "findings": 0}

	def cancel(self, op: OpRef) -> bool:
		self.ops[op.external_id].cancelled = True
		return True

	def get_status(self, op: OpRef) -> OpStatus:
		state = self.ops[op.external_id]
		if not state.cancelled:
			state.polls += 1  # a cancelled operation stops advancing
		now = datetime.now(UTC)
		done_steps = min(state.polls // state.polls_per_step, len(state.steps))
		steps: list[OpStep] = []
		overall = OpState.RUNNING
		error = None
		for i, title in enumerate(state.steps):
			if state.cancelled and i >= done_steps:
				steps.append(OpStep(title, OpState.CANCELLED))
				overall = OpState.CANCELLED
			elif state.fail_at_step == i and i <= done_steps:
				steps.append(
					OpStep(
						title, OpState.FAILED, output=f"{title} failed (dummy)", started_at=now, ended_at=now
					)
				)
				overall, error = OpState.FAILED, f"{title} failed (dummy)"
				steps.extend(OpStep(t, OpState.QUEUED) for t in state.steps[i + 1 :])
				break
			elif i < done_steps:
				steps.append(
					OpStep(title, OpState.SUCCESS, output=f"{title}: ok\n", started_at=now, ended_at=now)
				)
			elif i == done_steps:
				steps.append(OpStep(title, OpState.RUNNING, started_at=now))
			else:
				steps.append(OpStep(title, OpState.QUEUED))
		if overall is OpState.RUNNING and done_steps >= len(state.steps):
			overall = OpState.SUCCESS
		created = state.created if overall is OpState.SUCCESS else None
		return OpStatus(state=overall, steps=tuple(steps), error=error, created=created)
