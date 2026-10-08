"""ADR 0006 API: provider accounts without tokens, and the cached provisioning catalogue."""

from __future__ import annotations

from typing import Any

import pytest
from fake_frappe import FakeFrappe
from test_api import call, validate

import infra_control.api as api_pkg
from infra_control.api import providers
from infra_control.core import permissions
from infra_control.core.enums import Provider as ProviderName
from infra_control.providers import registry
from infra_control.providers.base import ProviderConfig

REGIONS = [
	{"slug": "fra1", "name": "Frankfurt 1", "available": True, "sizes": ["s-1vcpu-1gb", "s-2vcpu-4gb"]},
	{"slug": "nyc9", "name": "Closed", "available": False, "sizes": []},
	{"slug": "ams3", "name": "Amsterdam 3", "available": True, "sizes": ["s-2vcpu-4gb", "g-2vcpu-8gb"]},
]
SIZES = [
	{
		"slug": "g-2vcpu-8gb",
		"description": "General Purpose",
		"vcpus": 2,
		"memory": 8192,
		"disk": 25,
		"transfer": 4.0,
		"price_monthly": 63.0,
		"price_hourly": 0.09375,
		"regions": ["ams3"],
		"available": True,
	},
	{
		"slug": "s-2vcpu-4gb",
		"description": "Basic",
		"vcpus": 2,
		"memory": 4096,
		"disk": 80,
		"transfer": 4.0,
		"price_monthly": 24.0,
		"price_hourly": 0.03571,
		"regions": ["fra1", "ams3"],
		"available": True,
	},
	{
		"slug": "s-1vcpu-1gb",
		"description": "Basic",
		"vcpus": 1,
		"memory": 1024,
		"disk": 25,
		"transfer": 1.0,
		"price_monthly": 6.0,
		"price_hourly": 0.00893,
		"regions": ["fra1"],
		"available": True,
	},
	{
		"slug": "s-old",
		"description": "Retired",
		"vcpus": 1,
		"memory": 512,
		"disk": 20,
		"transfer": 1.0,
		"price_monthly": 5.0,
		"price_hourly": 0.007,
		"regions": [],
		"available": False,
	},
]


class _Client:
	calls = 0

	def list_regions(self) -> list[dict[str, Any]]:
		_Client.calls += 1
		return REGIONS

	def list_sizes(self) -> list[dict[str, Any]]:
		return SIZES


class _Provider:
	client = _Client()


@pytest.fixture
def ff(monkeypatch: pytest.MonkeyPatch) -> FakeFrappe:
	f = FakeFrappe()
	for module in (api_pkg, providers, permissions):
		monkeypatch.setattr(module, "frappe", f)
	f.add(
		"Provider Account",
		name="DO-STAGING",
		label="DO-STAGING",
		provider="digitalocean",
		enabled=1,
		is_staging=1,
		api_token="tok",
	)
	f.add(
		"Provider Account",
		name="FC-STAGING",
		label="FC-STAGING",
		provider="frappe_cloud",
		enabled=1,
		is_staging=1,
		api_token="tok",
	)
	monkeypatch.setattr(registry, "get_provider", lambda account: _Provider())
	monkeypatch.setattr(
		registry,
		"config_from_account",
		lambda account: ProviderConfig(
			account=account,
			provider=ProviderName.DIGITALOCEAN if account.startswith("DO") else ProviderName.FRAPPE_CLOUD,
			api_token="tok",
			team=None,
			is_staging=True,
		),
	)
	_Client.calls = 0
	return f


def test_accounts_are_listed_without_tokens(ff: FakeFrappe) -> None:
	status, body = call(providers.accounts)
	assert status == 200
	validate("providers.accounts", body)
	assert [a["name"] for a in body["items"]] == ["DO-STAGING", "FC-STAGING"]
	assert "api_token" not in body["items"][0]


def test_catalogue_filters_unavailable_sorts_basic_first_and_caches(ff: FakeFrappe) -> None:
	status, body = call(providers.options, account="DO-STAGING")
	assert status == 200
	validate("providers.options", body)
	assert [r["slug"] for r in body["regions"]] == ["ams3", "fra1"]
	assert [s["slug"] for s in body["sizes"]] == ["s-1vcpu-1gb", "s-2vcpu-4gb", "g-2vcpu-8gb"]
	assert body["sizes"][2]["family"] == "general" and body["sizes"][1]["memory_mb"] == 4096
	assert body["defaults"] == {"region": "fra1", "size": "s-2vcpu-4gb", "image": "ubuntu-24-04-x64"}
	call(providers.options, account="DO-STAGING")
	assert _Client.calls == 1  # second read served from the cache
	status, body = call(providers.options, account="NOPE")
	assert status == 404
	status, body = call(providers.options, account="FC-STAGING")
	assert status == 409 and body["error"]["code"] == "capability_missing"
