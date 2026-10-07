"""Controller-side settings the DigitalOcean adapter needs, read from `Infra Settings` and the
`Server` DocType. Kept in one module so tests can replace it and the adapter stays Frappe-free.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import frappe

from infra_control.providers.digitalocean.spaces import SpacesConfig

if TYPE_CHECKING:
	from infra_control.providers.digitalocean.runner import PlaybookRunner

DEFAULT_SSH_KEY = "~/.ssh/id_ed25519"


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


def ssh_key_path() -> str:
	"""Private key the controller uses for every managed server.

	Site config `infra_ssh_private_key` (a path), default `~/.ssh/id_ed25519` of the bench user.
	Its public half is the DigitalOcean SSH key named `infra-control` (docs/providers/digitalocean.md).
	"""
	configured = frappe.conf.get("infra_ssh_private_key") or DEFAULT_SSH_KEY
	return os.path.expanduser(str(configured))


def ansible_root() -> Path:
	"""Private data dirs of Ansible runs, inside the site's private files (never web-served)."""
	return Path(frappe.get_site_path("private", "infra_ansible")).resolve()


def default_runner() -> PlaybookRunner:
	"""ansible-runner when installed; otherwise a runner that fails every SSH call loudly."""
	from infra_control.providers.digitalocean.ansible import (
		AnsibleRunner,
		ansible_runner_available,
		default_playbooks_dir,
	)
	from infra_control.providers.digitalocean.runner import UnavailableRunner

	if not ansible_runner_available():
		return UnavailableRunner()
	return AnsibleRunner(
		root=ansible_root(), playbooks_dir=default_playbooks_dir(), ssh_key_path=ssh_key_path()
	)
