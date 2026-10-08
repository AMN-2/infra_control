"""A1.3: Provider base, capability gate, registry and the dummy adapter."""

from __future__ import annotations

from typing import Any

import pytest

from infra_control.core.enums import PROVIDER_CAPABILITIES, Capability
from infra_control.core.enums import Provider as ProviderName
from infra_control.core.errors import InternalError, NotSupported, ValidationError
from infra_control.providers import registry
from infra_control.providers.base import METHOD_CAPABILITY, OpRef, OpState, OpStatus, Provider, ProviderConfig
from infra_control.providers.dummy.adapter import DummyProvider


class _FcLike(Provider):
	"""A provider with the Frappe Cloud capability set that *implements* reboot anyway."""

	name = "fc_like"
	capabilities = PROVIDER_CAPABILITIES[ProviderName.FRAPPE_CLOUD]
	reboot_called = False

	def create_site(self, site: str, bench: str, apps: list[str], **kw: Any) -> OpRef:
		return OpRef(self.name, "press_job", "1")

	def backup_site(self, site: str, with_files: bool = True) -> OpRef:
		return OpRef(self.name, "press_job", "2")

	def restore_site(self, site: str, backup_ref: str) -> OpRef:
		return OpRef(self.name, "press_job", "3")

	def update_site(self, site: str) -> OpRef:
		return OpRef(self.name, "press_job", "4")

	def update_bench(
		self,
		bench: str,
		apps: list[str] | None = None,
		branch: str = "",
		migrate: bool = True,
		build: bool = True,
	) -> OpRef:
		return OpRef(self.name, "press_job", "4b")

	def add_app(self, bench: str, app: str, repo: str, branch: str = "") -> OpRef:
		return OpRef(self.name, "press_job", "4c")

	def install_app(self, site: str, app: str) -> OpRef:
		return OpRef(self.name, "press_job", "4d")

	def set_maintenance(self, site: str, on: bool) -> OpRef:
		return OpRef(self.name, "press_job", "5")

	def add_domain(self, site: str, domain: str) -> OpRef:
		return OpRef(self.name, "press_job", "6")

	def suspend_site(self, site: str, suspended: bool) -> OpRef:
		return OpRef(self.name, "press_job", "7")

	def get_status(self, op: OpRef) -> OpStatus:
		return OpStatus(OpState.SUCCESS)

	def sync_inventory(self) -> dict[str, Any]:
		return {}

	def reboot_server(self, server: str) -> OpRef:
		self.reboot_called = True
		return OpRef(self.name, "press_job", "8")


CONFIG = ProviderConfig(
	account="FC-STAGING", provider=ProviderName.FRAPPE_CLOUD, api_token="secret", is_staging=True
)


def test_capability_matrix_matches_plan_section_4_2() -> None:
	do = PROVIDER_CAPABILITIES[ProviderName.DIGITALOCEAN]
	fc = PROVIDER_CAPABILITIES[ProviderName.FRAPPE_CLOUD]
	assert {Capability.SITE, Capability.BENCH} <= do & fc
	assert {
		Capability.SERVER,
		Capability.SSH,
		Capability.SNAPSHOT,
		Capability.SERVICE_CONTROL,
		Capability.METRICS,
		Capability.CUSTOM_PLAYBOOK,
	} <= do
	assert {Capability.MANAGED_BACKUP, Capability.MANAGED_UPDATE} <= fc
	assert not ({Capability.SERVER, Capability.METRICS, Capability.CUSTOM_PLAYBOOK} & fc)
	assert not ({Capability.MANAGED_BACKUP, Capability.MANAGED_UPDATE} & do)


def test_call_checks_capability_before_dispatch() -> None:
	"""Plan 4.3 rule 1: never a silent no-op, and the adapter method must not even run."""
	p = _FcLike(CONFIG)
	with pytest.raises(NotSupported) as exc:
		p.call("reboot_server", server="SRV-0001")
	assert exc.value.http_status == 409
	assert exc.value.as_payload()["error"] == {
		"code": "capability_missing",
		"message": "Provider fc_like lacks capability server",
		"details": {"capability": "server", "provider": "fc_like"},
	}
	assert p.reboot_called is False
	assert p.call("backup_site", site="x").external_id == "2"
	assert p.call("get_status", op=OpRef("fc_like", "press_job", "1")).state is OpState.SUCCESS


def test_unimplemented_optional_methods_raise_not_supported() -> None:
	p = _FcLike(CONFIG)
	for method in ("snapshot_server", "control_service", "get_metrics", "run_playbook"):
		with pytest.raises(NotSupported):
			p.call(
				method,
				**{"server": "x", "service": "nginx", "action": "restart", "playbook_file": "f"}.copy()
				if method == "control_service"
				else {"server": "x"}
				if method in ("snapshot_server", "get_metrics")
				else {"server": "x", "playbook_file": "f"},
			)
	with pytest.raises(NotSupported):
		p.call("not_a_method")


def test_every_provider_method_has_a_capability_entry() -> None:
	public = {n for n in dir(Provider) if not n.startswith("_") and callable(getattr(Provider, n))} - {
		"call",
		"supports",
		"require",
		"cancel",
	}
	assert public == set(METHOD_CAPABILITY)


def test_op_ref_round_trips_through_json_dict() -> None:
	ref = OpRef("digitalocean", "do_action", "2211004")
	assert OpRef.from_dict(ref.to_dict()) == ref
	assert ref.to_dict() == {"provider": "digitalocean", "kind": "do_action", "external_id": "2211004"}


def test_provider_config_hides_the_token_in_repr() -> None:
	assert "secret" not in repr(CONFIG)


def test_registry_register_build_and_unknown() -> None:
	registry.register(_FcLike)
	try:
		assert registry.registered()["fc_like"] is _FcLike
		cfg = ProviderConfig(account="X", provider=ProviderName.FRAPPE_CLOUD, api_token="t")
		assert isinstance(registry.adapter_class("fc_like")(cfg), _FcLike)
	finally:
		registry.unregister("fc_like")
	with pytest.raises(InternalError):
		registry.adapter_class("nope")
	# A known provider whose adapter is not shipped yet (Frappe Cloud until A2.4) fails loudly.
	with pytest.raises(InternalError):
		registry.adapter_class(ProviderName.FRAPPE_CLOUD)


def test_registry_rejects_adapters_that_deviate_from_the_matrix() -> None:
	class BadDo(_FcLike):
		name = ProviderName.DIGITALOCEAN
		capabilities = frozenset({Capability.SITE})

	with pytest.raises(InternalError) as exc:
		registry.register(BadDo)
	assert "server" in exc.value.details["missing"]
	# The rejected impostor never replaces the real adapter (A2.1).
	assert registry.registered().get(ProviderName.DIGITALOCEAN) is not BadDo


def test_capabilities_for() -> None:
	assert registry.capabilities_for("frappe_cloud") == PROVIDER_CAPABILITIES[ProviderName.FRAPPE_CLOUD]
	assert registry.capabilities_for("dummy") == frozenset(Capability)
	with pytest.raises(ValidationError):
		registry.capabilities_for("aws")


def test_dummy_provider_runs_steps_fails_and_cancels() -> None:
	p = DummyProvider(polls_per_step=1)
	ref = p.call("update_site", site="demo")
	assert ref.kind == "dummy"
	s1 = p.get_status(ref)
	assert s1.state is OpState.RUNNING and [s.state for s in s1.steps] == [
		OpState.SUCCESS,
		OpState.RUNNING,
		OpState.QUEUED,
	]
	p.get_status(ref)
	s3 = p.get_status(ref)
	assert s3.state is OpState.SUCCESS and all(s.state is OpState.SUCCESS for s in s3.steps)

	created = p.call("create_server", hostname="app-03")
	for _ in range(3):
		st = p.get_status(created)
	assert st.state is OpState.SUCCESS and st.created == ("Server", "app-03")

	failing = DummyProvider(fail_at_step=1)
	ref = failing.call("update_site", site="demo")
	failing.get_status(ref)
	st = failing.get_status(ref)
	assert (
		st.state is OpState.FAILED
		and st.error
		and st.steps[1].state is OpState.FAILED
		and st.steps[2].state is OpState.QUEUED
	)

	ref = p.call("backup_site", site="demo")
	assert p.cancel(ref) is True
	assert p.get_status(ref).state is OpState.CANCELLED
