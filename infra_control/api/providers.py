"""providers.* (ADR 0006): provider accounts and the live catalogue (regions, plans) a server can
be provisioned from. Read-only; the catalogue is cached for an hour per account."""

from __future__ import annotations

import json
from typing import Any

import frappe

from infra_control.api import api, str_param
from infra_control.core.enums import Provider as ProviderName
from infra_control.core.errors import NotFound, NotSupported
from infra_control.providers import registry
from infra_control.providers.digitalocean.adapter import DEFAULT_IMAGE

CACHE_SECONDS = 3600
FIELDS = ["name", "label", "provider", "enabled", "is_staging"]
DEFAULT_REGION = "fra1"
DEFAULT_SIZE = "s-2vcpu-4gb"


def _family(slug: str) -> str:
	prefix = slug.split("-", 1)[0]
	return {"s": "basic", "g": "general", "gd": "general", "c": "cpu", "m": "memory", "so": "storage"}.get(
		prefix, "other"
	)


def _serialize_size(s: dict[str, Any]) -> dict[str, Any]:
	return {
		"slug": str(s.get("slug") or ""),
		"family": _family(str(s.get("slug") or "")),
		"description": str(s.get("description") or ""),
		"vcpus": int(s.get("vcpus") or 0),
		"memory_mb": int(s.get("memory") or 0),
		"disk_gb": int(s.get("disk") or 0),
		"transfer_tb": float(s.get("transfer") or 0.0),
		"price_monthly": float(s.get("price_monthly") or 0.0),
		"price_hourly": float(s.get("price_hourly") or 0.0),
		"regions": [str(r) for r in (s.get("regions") or [])],
	}


def _serialize_region(r: dict[str, Any]) -> dict[str, Any]:
	return {
		"slug": str(r.get("slug") or ""),
		"name": str(r.get("name") or ""),
		"sizes": [str(s) for s in (r.get("sizes") or [])],
	}


def catalogue(account: str) -> dict[str, Any]:
	"""Regions and available sizes of a DigitalOcean account, cached per account for an hour."""
	key = f"infra_control:catalogue:{account}"
	cached = frappe.cache().get_value(key)
	if cached:
		data: dict[str, Any] = json.loads(cached) if isinstance(cached, str) else dict(cached)
		return data
	config = registry.config_from_account(account)
	if config.provider != ProviderName.DIGITALOCEAN:
		raise NotSupported("server", str(config.provider))
	provider: Any = registry.get_provider(account)
	regions = [_serialize_region(r) for r in provider.client.list_regions() if r.get("available", True)]
	sizes = [_serialize_size(s) for s in provider.client.list_sizes() if s.get("available", True)]
	sizes.sort(key=lambda s: (s["family"] != "basic", s["price_monthly"]))
	data = {
		"account": account,
		"provider": str(config.provider),
		"regions": sorted(regions, key=lambda r: r["slug"]),
		"sizes": sizes,
		"defaults": {"region": DEFAULT_REGION, "size": DEFAULT_SIZE, "image": DEFAULT_IMAGE},
	}
	frappe.cache().set_value(key, json.dumps(data), expires_in_sec=CACHE_SECONDS)
	return data


@api()
def accounts() -> dict[str, Any]:
	rows = frappe.get_all("Provider Account", fields=FIELDS, order_by="label asc")
	return {
		"items": [
			{
				"name": r["name"],
				"label": r["label"],
				"provider": r["provider"],
				"enabled": bool(r.get("enabled")),
				"is_staging": bool(r.get("is_staging")),
			}
			for r in rows
		]
	}


@api()
def options(account: str | None = None) -> dict[str, Any]:
	name = str_param("account", account, required=True) or ""
	if not frappe.db.exists("Provider Account", name):
		raise NotFound("Provider Account", name)
	return catalogue(name)
