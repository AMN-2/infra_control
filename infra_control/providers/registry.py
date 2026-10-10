"""Provider registry: provider name -> adapter class, and `Provider Account` -> adapter instance.

Adapters register themselves at import time (`register(DigitalOceanProvider)`); this module
imports the known adapter packages lazily so a missing optional dependency does not break the
API for the other provider.
"""

from __future__ import annotations

import importlib
from typing import Any

import frappe

from infra_control.core.enums import PROVIDER_CAPABILITIES, Capability
from infra_control.core.enums import Provider as ProviderName
from infra_control.core.errors import InternalError, NotFound, ValidationError
from infra_control.providers.base import Provider, ProviderConfig

_REGISTRY: dict[str, type[Provider]] = {}

# Adapter modules that register a provider when imported (filled in Phase 2).
ADAPTER_MODULES: dict[str, str] = {
	ProviderName.DIGITALOCEAN: "infra_control.providers.digitalocean.adapter",
	ProviderName.FRAPPE_CLOUD: "infra_control.providers.frappe_cloud.adapter",
}


def register(cls: type[Provider]) -> type[Provider]:
	"""Class decorator. The adapter's capability set must equal the plan's matrix (section 4.2)."""
	name = cls.name
	expected = PROVIDER_CAPABILITIES.get(ProviderName(name)) if name in set(ProviderName) else None
	if expected is not None and cls.capabilities != expected:
		raise InternalError(
			f"{name} adapter capabilities differ from plan section 4.2",
			{"extra": sorted(cls.capabilities - expected), "missing": sorted(expected - cls.capabilities)},
		)
	_REGISTRY[name] = cls
	return cls


def unregister(name: str) -> None:
	_REGISTRY.pop(name, None)


def registered() -> dict[str, type[Provider]]:
	return dict(_REGISTRY)


def adapter_class(name: str) -> type[Provider]:
	if name not in _REGISTRY and name in ADAPTER_MODULES:
		try:
			importlib.import_module(ADAPTER_MODULES[name])
		except ImportError as exc:  # adapter not shipped yet (Phase 2) or optional dependency missing
			raise InternalError(f"Provider adapter {name} is not available", {"reason": str(exc)}) from exc
	if name not in _REGISTRY:
		raise InternalError(f"Unknown provider {name}", {"provider": name})
	return _REGISTRY[name]


def capabilities_for(provider: str) -> frozenset[Capability]:
	"""Provider-level capability set (what the API exposes as `capabilities`)."""
	try:
		return PROVIDER_CAPABILITIES[ProviderName(provider)]
	except ValueError:
		if provider in _REGISTRY:
			return _REGISTRY[provider].capabilities
		raise ValidationError(f"Unknown provider {provider}", {"provider": provider}) from None


def build(config: ProviderConfig) -> Provider:
	return adapter_class(str(config.provider))(config)


def production_accounts_allowed() -> bool:
	"""Plan rule 11.6 (staging only) is the default; the production controller opts out explicitly."""
	return bool(frappe.db.get_single_value("Infra Settings", "allow_production_accounts"))


def config_from_account(account: str) -> ProviderConfig:
	"""Read a `Provider Account`. Non-staging accounts need `allow_production_accounts` in Infra Settings."""
	if not frappe.db.exists("Provider Account", account):
		raise NotFound("Provider Account", account)
	doc: Any = frappe.get_doc("Provider Account", account)
	if not doc.enabled:
		raise ValidationError(f"Provider Account {account} is disabled", {"account": account})
	if not doc.is_staging and not production_accounts_allowed():
		raise ValidationError(
			f"Provider Account {account} is a production account and production accounts are not enabled",
			{"account": account, "hint": "Infra Settings → Production → Allow production accounts"},
		)
	return ProviderConfig(
		account=account,
		provider=ProviderName(doc.provider),
		api_token=doc.get_password("api_token"),
		team=doc.team or None,
		is_staging=bool(doc.is_staging),
	)


def get_provider(account: str) -> Provider:
	"""Adapter instance for a `Provider Account` name. The job engine's resolver."""
	return build(config_from_account(account))
