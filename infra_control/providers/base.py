"""`Provider` interface (plan section 4.1) and the operation types the job engine polls.

Rules (plan section 4.3):
- Capability check before every call: the job engine invokes adapters only through
  `Provider.call()`, which raises `NotSupported` (409 `capability_missing`) before dispatching.
- Every mutating call returns an `OpRef`; `get_status()` is polled until a terminal `OpState`.
- Provider-specific status strings are mapped to `OpState` inside the adapter package.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, ClassVar

from infra_control.core.enums import Capability
from infra_control.core.enums import Provider as ProviderName
from infra_control.core.errors import NotSupported

__all__ = [
	"METHOD_CAPABILITY",
	"Capability",
	"NotSupported",
	"OpRef",
	"OpState",
	"OpStatus",
	"OpStep",
	"Provider",
	"ProviderConfig",
]


class OpState(StrEnum):
	QUEUED = "Queued"
	RUNNING = "Running"
	SUCCESS = "Success"
	FAILED = "Failed"
	CANCELLED = "Cancelled"

	@property
	def terminal(self) -> bool:
		return self in (OpState.SUCCESS, OpState.FAILED, OpState.CANCELLED)


@dataclass(frozen=True)
class OpRef:
	"""Reference to an operation the provider started. Stored as JSON in `Infra Job.op_ref`."""

	provider: str
	"""`digitalocean` | `frappe_cloud` | `dummy`"""
	kind: str
	"""`ansible` | `do_action` | `press_job` | `dummy`"""
	external_id: str

	def to_dict(self) -> dict[str, str]:
		return asdict(self)

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> OpRef:
		return cls(
			provider=str(data["provider"]), kind=str(data["kind"]), external_id=str(data["external_id"])
		)


@dataclass(frozen=True)
class OpStep:
	name: str
	state: OpState
	output: str = ""
	started_at: datetime | None = None
	ended_at: datetime | None = None


@dataclass(frozen=True)
class OpStatus:
	state: OpState
	steps: tuple[OpStep, ...] = ()
	error: str | None = None
	created: tuple[str, str] | None = None
	"""(doctype, provider_ref) of a document the operation created, once known (ADR 0001)."""


@dataclass(frozen=True)
class ProviderConfig:
	"""What an adapter needs from a `Provider Account`; the token never leaves this object."""

	account: str
	provider: ProviderName
	api_token: str = field(repr=False)
	team: str | None = None
	is_staging: bool = False


# Capability each provider method needs (plan sections 4.1 and 4.2). Methods absent here need
# none beyond the provider existing (`get_status`, `sync_inventory`).
METHOD_CAPABILITY: dict[str, Capability | None] = {
	"create_site": Capability.SITE,
	"backup_site": Capability.SITE,
	"restore_site": Capability.SITE,
	"update_site": Capability.SITE,
	"set_maintenance": Capability.SITE,
	"add_domain": Capability.SITE,
	"suspend_site": Capability.SITE,
	"get_status": None,
	"sync_inventory": None,
	"create_server": Capability.SERVER,
	"reboot_server": Capability.SERVER,
	"snapshot_server": Capability.SNAPSHOT,
	"control_service": Capability.SERVICE_CONTROL,
	"get_metrics": Capability.METRICS,
	"run_playbook": Capability.CUSTOM_PLAYBOOK,
}


class Provider(ABC):
	"""One instance per `Provider Account`. Subclasses set `name` and `capabilities`."""

	name: ClassVar[str]
	capabilities: ClassVar[frozenset[Capability]]

	def __init__(self, config: ProviderConfig) -> None:
		self.config = config

	# --- capability gate ----------------------------------------------------------------
	def supports(self, capability: Capability | str) -> bool:
		return Capability(capability) in self.capabilities

	def require(self, capability: Capability | str) -> None:
		if not self.supports(capability):
			raise NotSupported(Capability(capability), self.name)

	def call(self, method: str, /, **kwargs: Any) -> Any:
		"""The job engine's only entry point: check the capability, then dispatch."""
		if method not in METHOD_CAPABILITY:
			raise NotSupported(method, self.name)
		needed = METHOD_CAPABILITY[method]
		if needed is not None:
			self.require(needed)
		return getattr(self, method)(**kwargs)

	# --- site level (all providers) -----------------------------------------------------
	@abstractmethod
	def create_site(self, site: str, bench: str, apps: list[str], **kw: Any) -> OpRef: ...

	@abstractmethod
	def backup_site(self, site: str, with_files: bool = True) -> OpRef: ...

	@abstractmethod
	def restore_site(self, site: str, backup_ref: str) -> OpRef: ...

	@abstractmethod
	def update_site(self, site: str) -> OpRef: ...

	@abstractmethod
	def set_maintenance(self, site: str, on: bool) -> OpRef: ...

	@abstractmethod
	def add_domain(self, site: str, domain: str) -> OpRef: ...

	@abstractmethod
	def suspend_site(self, site: str, suspended: bool) -> OpRef: ...

	# --- lifecycle ----------------------------------------------------------------------
	@abstractmethod
	def get_status(self, op: OpRef) -> OpStatus: ...

	@abstractmethod
	def sync_inventory(self) -> dict[str, Any]:
		"""Normalized `{"servers": [...], "benches": [...], "sites": [...]}` (unified enums)."""

	def cancel(self, op: OpRef) -> bool:
		"""Best effort. Returns True if the provider accepted the cancellation."""
		return False

	# --- optional, guarded by capabilities ----------------------------------------------
	def create_server(self, **kw: Any) -> OpRef:
		raise NotSupported(Capability.SERVER, self.name)

	def reboot_server(self, server: str) -> OpRef:
		raise NotSupported(Capability.SERVER, self.name)

	def snapshot_server(self, server: str) -> OpRef:
		raise NotSupported(Capability.SNAPSHOT, self.name)

	def control_service(self, server: str, service: str, action: str) -> OpRef:
		raise NotSupported(Capability.SERVICE_CONTROL, self.name)

	def get_metrics(self, server: str) -> dict[str, Any]:
		raise NotSupported(Capability.METRICS, self.name)

	def run_playbook(
		self, server: str, playbook_file: str, extra_vars: dict[str, Any] | None = None
	) -> OpRef:
		raise NotSupported(Capability.CUSTOM_PLAYBOOK, self.name)
