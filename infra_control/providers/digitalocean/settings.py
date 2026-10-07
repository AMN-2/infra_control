"""Controller-side settings the DigitalOcean adapter needs, read from `Infra Settings` and the
`Server` DocType. Kept in one module so tests can replace it and the adapter stays Frappe-free.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import frappe

from infra_control.providers.digitalocean.spaces import SpacesConfig


@dataclass(frozen=True)
class ControllerSettings:
	controller_ip: str | None
	spaces: SpacesConfig | None


def load_controller_settings() -> ControllerSettings:
	doc: Any = frappe.get_single("Infra Settings")
	spaces: SpacesConfig | None = None
	if doc.spaces_bucket and doc.spaces_region:
		spaces = SpacesConfig(
			bucket=str(doc.spaces_bucket),
			region=str(doc.spaces_region),
			key=str(doc.get_password("spaces_key") or ""),
			secret=str(doc.get_password("spaces_secret") or ""),
		)
	return ControllerSettings(
		controller_ip=(str(doc.controller_ip) if doc.controller_ip else None), spaces=spaces
	)


def load_server(name: str) -> dict[str, Any]:
	"""The Server document as a plain dict (what the runner and the API calls need)."""
	doc: Any = frappe.get_doc("Server", name)
	return {
		"name": name,
		"hostname": doc.hostname,
		"provider_ref": doc.provider_ref,
		"public_ip": doc.public_ip,
		"private_ip": doc.private_ip,
		"ssh_user": doc.ssh_user or "frappe",
		"ssh_port": int(doc.ssh_port or 22),
		"role": doc.role,
		"region": doc.region,
		"size": doc.size,
	}


def load_site(name: str) -> dict[str, Any]:
	"""The Site document with its bench and server, for site playbooks."""
	doc: Any = frappe.get_doc("Site", name)
	bench: Any = frappe.get_doc("Bench", doc.bench) if doc.bench else None
	return {
		"name": name,
		"domain": doc.domain,
		"bench": doc.bench,
		"bench_path": bench.path if bench else None,
		"server": doc.server,
	}


def load_bench(name: str) -> dict[str, Any]:
	doc: Any = frappe.get_doc("Bench", name)
	return {"name": name, "title": doc.title, "path": doc.path, "server": doc.server}
