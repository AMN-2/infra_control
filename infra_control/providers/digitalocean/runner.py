"""The seam between the DigitalOcean adapter and Ansible.

Every DO operation that needs SSH (site and bench playbooks, service control, metrics
collection, custom playbooks, the post-create configuration of a droplet) goes through a
`PlaybookRunner`. `AnsibleRunner` (ansible.py, A2.2) is the real implementation; `UnavailableRunner` is used
only when `ansible-runner` is not installed, and fails loudly instead of pretending.
"""

from __future__ import annotations

from typing import Any, Protocol

from infra_control.core.errors import ProviderError
from infra_control.providers.base import OpRef, OpStatus


class PlaybookRunner(Protocol):
	def start(
		self,
		server: dict[str, Any],
		playbook_file: str,
		extra_vars: dict[str, Any] | None = None,
		*,
		start_at_task: str | None = None,
	) -> OpRef:
		"""Launch a playbook against one server (`server` is the normalized Server document)."""

	def status(self, op: OpRef) -> OpStatus: ...

	def cancel(self, op: OpRef) -> bool: ...


class UnavailableRunner:
	"""Used when ansible-runner is missing: any SSH-backed call is a clear error, never a no-op."""

	reason = "ansible-runner is not installed on this controller (bench setup requirements)"

	def start(
		self,
		server: dict[str, Any],
		playbook_file: str,
		extra_vars: dict[str, Any] | None = None,
		*,
		start_at_task: str | None = None,
	) -> OpRef:
		raise ProviderError(self.reason, {"playbook": playbook_file, "server": server.get("name")})

	def status(self, op: OpRef) -> OpStatus:
		raise ProviderError(self.reason, {"op": op.to_dict()})

	def cancel(self, op: OpRef) -> bool:
		return False
