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


# --- recorders: what a successful operation leaves in the DocTypes ----------------------------
# Called once by the adapter when an operation reaches Success. Each is idempotent, so a repeated
# call (a poll after a worker restart) never duplicates a document.


def record_server(account: str, droplet: dict[str, Any]) -> str:
	"""Create or update the Server for a provisioned droplet (`droplet` is mapping.normalize_droplet)."""
	ref = str(droplet["provider_ref"])
	name = frappe.db.get_value("Server", {"provider_ref": ref}, "name")
	values = {
		"hostname": droplet["hostname"],
		"status": str(droplet["status"]),
		"provider_account": account,
		"provider": "digitalocean",
		"provider_ref": ref,
		"public_ip": droplet.get("public_ip"),
		"private_ip": droplet.get("private_ip"),
		"role": str(droplet.get("role") or "all"),
		"region": droplet.get("region") or "",
		"size": droplet.get("size") or "",
		"ssh_user": "frappe",
		"ssh_port": 22,
	}
	if name:
		doc: Any = frappe.get_doc("Server", name)
		doc.update(values)
		doc.save(ignore_permissions=True)
		return str(name)
	doc = frappe.get_doc(
		{"doctype": "Server", **values, "tags": [{"tag": t} for t in droplet.get("tags") or []]}
	)
	doc.insert(ignore_permissions=True)
	return str(doc.name)


def record_bench(account: str, server: str, path: str) -> str:
	"""The bench a provision initialised (one per server path). Apps and version: inventory.sync."""
	existing = frappe.db.get_value("Bench", {"server": server, "path": path}, "name")
	if existing:
		return str(existing)
	doc: Any = frappe.get_doc(
		{
			"doctype": "Bench",
			"title": os.path.basename(path.rstrip("/")) or path,
			"provider_account": account,
			"provider": "digitalocean",
			"provider_ref": f"{server}:{path}",
			"server": server,
			"path": path,
		}
	)
	doc.insert(ignore_permissions=True)
	return str(doc.name)


def controller_public_key() -> str:
	"""The public half of `ssh_key_path()`, or "" when it cannot be read."""
	try:
		return Path(ssh_key_path() + ".pub").read_text().strip()
	except OSError:
		return ""


def record_site(domain: str, bench: str) -> str:
	"""Create the Site a successful `site.create` produced (name = domain)."""
	if frappe.db.exists("Site", domain):
		frappe.db.set_value("Site", domain, "status", "Active")
		return domain
	b: Any = frappe.get_doc("Bench", bench)
	doc: Any = frappe.get_doc(
		{
			"doctype": "Site",
			"domain": domain,
			"status": "Active",
			"bench": bench,
			"server": b.server,
			"provider_account": b.provider_account,
			"provider": "digitalocean",
			"provider_ref": f"{b.server}:{b.path}:{domain}",
		}
	)
	doc.insert(ignore_permissions=True)
	return str(doc.name)


def record_backup(site: str, kind: str, location: str, size_mb: float, job_ref: str) -> str:
	"""One Backup per stored file; `location` is spaces://bucket/key, never a signed URL."""
	existing = frappe.db.get_value("Backup", {"location": location}, "name")
	if existing:
		return str(existing)
	now = frappe.utils.now_datetime()
	doc: Any = frappe.get_doc(
		{
			"doctype": "Backup",
			"site": site,
			"kind": kind,
			"location": location,
			"size_mb": size_mb,
			"created_at": now,
		}
	)
	doc.insert(ignore_permissions=True)
	if kind == "db":
		frappe.db.set_value("Site", site, "last_backup", now)
	return str(doc.name)


def load_backup_set(backup: str) -> dict[str, str]:
	"""A Backup name (or a spaces:// location) → the locations of that backup's files by kind.

	Files of one backup share the key prefix `<site>/<stamp>-`, so siblings are found by it."""
	if backup.startswith("spaces://"):
		row: Any = frappe.db.get_value("Backup", {"location": backup}, ["site", "location"], as_dict=True)
	else:
		row = frappe.db.get_value("Backup", backup, ["site", "location"], as_dict=True)
	if not row:
		from infra_control.core.errors import NotFound

		raise NotFound("Backup", backup)
	prefix = str(row.location).rsplit("-", 1)[0]
	siblings = frappe.get_all(
		"Backup",
		filters={"site": row.site, "location": ["like", f"{prefix}-%"]},
		fields=["kind", "location"],
	)
	return {str(s["kind"]): str(s["location"]) for s in siblings}


def record_domain(site: str, domain: str) -> None:
	doc: Any = frappe.get_doc("Site", site)
	if any(d.domain == domain for d in doc.custom_domains):
		return
	doc.append("custom_domains", {"domain": domain})
	doc.save(ignore_permissions=True)


def record_bench_app(bench: str, app: str, branch: str) -> None:
	"""Add the Bench App row a successful `bench.add_app` produced (inventory.sync keeps it current)."""
	doc: Any = frappe.get_doc("Bench", bench)
	if any(a.app == app for a in doc.apps):
		return
	doc.append("apps", {"app": app, "branch": branch or None})
	doc.save(ignore_permissions=True)


def spaces_client() -> Any:
	"""A SpacesClient for the configured bucket, or None when Spaces is not configured."""
	from infra_control.providers.digitalocean.spaces import SpacesClient

	cfg = load_controller_settings().spaces
	return SpacesClient(cfg) if cfg else None
