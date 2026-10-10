"""Inventory reconciliation plan (A2.5, plan sections 9.2 `inventory.sync` and 9.4 drift).

Pure: provider inventory in, documents in, a plan out. The plan says what to create, what to
update and what the provider no longer has (`missing`). Only `apply.py` writes.

Rules:
- The provider is the source of truth for what exists and for provider-owned facts (address,
  size, region, status, apps, versions). Documents are created for resources the provider has
  and updated when those facts changed.
- Nothing is ever deleted or archived automatically (plan 9.4: drift never auto-fixes). A
  document whose resource is gone is reported as a finding for a human.
- Servers match by `provider_ref` (the droplet id), benches by (server, path), sites by domain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from infra_control.core.enums import ServerStatus, SiteStatus

SERVER_FIELDS = ("hostname", "status", "public_ip", "private_ip", "region", "size", "role")
BENCH_FIELDS = ("frappe_version", "apps")
SITE_FIELDS = ("status", "bench")


@dataclass
class Finding:
	"""Drift the sync will not fix on its own."""

	kind: str
	"""`server_missing` | `bench_missing` | `site_missing` | `server_unreachable`"""
	doctype: str
	name: str
	detail: str


@dataclass
class SyncPlan:
	create_servers: list[dict[str, Any]] = field(default_factory=list)
	update_servers: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
	create_benches: list[dict[str, Any]] = field(default_factory=list)
	update_benches: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
	create_sites: list[dict[str, Any]] = field(default_factory=list)
	update_sites: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
	findings: list[Finding] = field(default_factory=list)

	@property
	def summary(self) -> dict[str, int]:
		return {
			"servers_created": len(self.create_servers),
			"servers_updated": len(self.update_servers),
			"benches_created": len(self.create_benches),
			"benches_updated": len(self.update_benches),
			"sites_created": len(self.create_sites),
			"sites_updated": len(self.update_sites),
			"findings": len(self.findings),
		}


def _changed(doc: dict[str, Any], wanted: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
	out: dict[str, Any] = {}
	for f in fields:
		if f in wanted and _norm(doc.get(f)) != _norm(wanted[f]):
			out[f] = wanted[f]
	return out


def _norm(value: Any) -> Any:
	if value is None or value == "":
		return None
	if isinstance(value, list):
		return [_norm(v) for v in value]
	if isinstance(value, dict):
		# An absent key and a key holding None/"" mean the same thing (a Bench App row always has
		# `commit`/`remote` columns; a discovery payload may omit them), so drop empty entries.
		return {k: n for k, v in value.items() if (n := _norm(v)) is not None}
	return str(value) if not isinstance(value, bool) else value


def plan_sync(
	account: str,
	provider: str,
	inventory: dict[str, Any],
	documents: dict[str, list[dict[str, Any]]],
) -> SyncPlan:
	"""`inventory` = {"servers": [...], "benches": [...], "sites": [...], "unreachable": [...]}
	in the normalized shapes `providers/<name>/mapping.py` produce (benches/sites carry
	`server_ref`, the droplet id, and benches a `path`; sites a `bench_path`).

	`documents` = {"servers": [...], "benches": [...], "sites": [...]}: the account's documents as
	dicts with `name`, their matching keys and the fields in *_FIELDS (benches: `apps` as a list
	of {app, version, branch}).
	"""
	plan = SyncPlan()

	# --- servers -----------------------------------------------------------------------------
	docs_by_ref = {
		str(d.get("provider_ref")): d for d in documents.get("servers", []) if d.get("provider_ref")
	}
	seen_refs: set[str] = set()
	server_name_by_ref: dict[str, str] = {}
	for s in inventory.get("servers", []):
		ref = str(s["provider_ref"])
		seen_refs.add(ref)
		wanted = {
			"hostname": s.get("hostname"),
			"status": str(s.get("status") or ServerStatus.ACTIVE),
			"public_ip": s.get("public_ip"),
			"private_ip": s.get("private_ip"),
			"region": s.get("region") or "",
			"size": s.get("size") or "",
			"role": str(s.get("role") or "all"),
		}
		doc = docs_by_ref.get(ref)
		if doc is None:
			plan.create_servers.append(
				{
					**wanted,
					"provider_ref": ref,
					"provider_account": account,
					"provider": provider,
					"tags": list(s.get("tags") or []),
				}
			)
			continue
		server_name_by_ref[ref] = str(doc["name"])
		if str(doc.get("status")) == ServerStatus.ARCHIVED:
			# A human archived it; the provider still has it. Leave the document, say so.
			plan.findings.append(
				Finding(
					"server_archived_but_present",
					"Server",
					str(doc["name"]),
					f"droplet {ref} still exists at the provider",
				)
			)
			continue
		changes = _changed(doc, wanted, SERVER_FIELDS)
		if changes:
			plan.update_servers.append((str(doc["name"]), changes))
	for ref, doc in docs_by_ref.items():
		if ref not in seen_refs and str(doc.get("status")) != ServerStatus.ARCHIVED:
			plan.findings.append(
				Finding(
					"server_missing",
					"Server",
					str(doc["name"]),
					f"droplet {ref} is not at the provider any more",
				)
			)

	for host in inventory.get("unreachable", []):
		plan.findings.append(
			Finding(
				"server_unreachable", "Server", str(host), "discovery could not reach the server over SSH"
			)
		)

	# --- benches -------------------------------------------------------------------------------
	# Keyed by (server document name, path); provider benches reference the server by droplet id,
	# so servers created in this very plan are addressed by a placeholder `new:<ref>`.
	def server_name(ref: str) -> str:
		return server_name_by_ref.get(ref, f"new:{ref}")

	bench_docs = {
		(str(d.get("server")), str(d.get("path"))): d for d in documents.get("benches", []) if d.get("path")
	}
	# `discovered` is the set of droplet refs discovery actually scanned; resolve to server names.
	discovered_servers = {server_name(str(ref)) for ref in inventory.get("discovered", [])}
	seen_benches: set[tuple[str, str]] = set()
	bench_name_by_key: dict[tuple[str, str], str] = {}
	for b in inventory.get("benches", []):
		key = (server_name(str(b["server_ref"])), str(b["path"]))
		seen_benches.add(key)
		wanted_b = {"frappe_version": b.get("frappe_version"), "apps": list(b.get("apps") or [])}
		doc = bench_docs.get(key)
		if doc is None:
			plan.create_benches.append(
				{
					**wanted_b,
					"server": key[0],
					"path": key[1],
					"title": b.get("title") or key[1].rstrip("/").rsplit("/", 1)[-1],
					"provider_account": account,
					"provider": provider,
					"provider_ref": f"{key[0]}:{key[1]}",
				}
			)
			continue
		bench_name_by_key[key] = str(doc["name"])
		changes = _changed(doc, wanted_b, BENCH_FIELDS)
		if changes:
			plan.update_benches.append((str(doc["name"]), changes))
	for key, doc in bench_docs.items():
		if key in seen_benches or key[0] not in discovered_servers:
			continue  # only servers discovery actually scanned can prove a bench is gone
		plan.findings.append(
			Finding("bench_missing", "Bench", str(doc["name"]), f"no bench at {key[1]} on {key[0]}")
		)

	# --- sites ---------------------------------------------------------------------------------
	def bench_name(server: str, path: str) -> str:
		return bench_name_by_key.get((server, path), f"new:{server}:{path}")

	site_docs = {str(d.get("name")): d for d in documents.get("sites", [])}
	seen_sites: set[str] = set()
	for s in inventory.get("sites", []):
		domain = str(s["domain"])
		seen_sites.add(domain)
		server = server_name(str(s["server_ref"]))
		wanted_s = {
			"status": str(s.get("status") or SiteStatus.ACTIVE),
			"bench": bench_name(server, str(s["bench_path"])),
		}
		doc = site_docs.get(domain)
		if doc is None:
			plan.create_sites.append(
				{
					**wanted_s,
					"domain": domain,
					"server": server,
					"provider_account": account,
					"provider": provider,
					"provider_ref": f"{server}:{s['bench_path']}:{domain}",
				}
			)
			continue
		if str(doc.get("status")) in (SiteStatus.ARCHIVED, SiteStatus.SUSPENDED):
			continue  # human-set states the host cannot tell apart from Active or Maintenance
		changes = _changed(doc, wanted_s, SITE_FIELDS)
		if changes:
			plan.update_sites.append((domain, changes))
	for domain, doc in site_docs.items():
		if domain in seen_sites or str(doc.get("status")) == SiteStatus.ARCHIVED:
			continue
		if str(doc.get("server")) not in discovered_servers:
			continue
		plan.findings.append(
			Finding("site_missing", "Site", domain, f"no site directory on {doc.get('server')}")
		)
	return plan


def normalize_discovery(
	server_ref: str, hostname: str, payload: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
	"""One host's `discover_bench.py` output → normalized benches and sites for `plan_sync`."""
	benches: list[dict[str, Any]] = []
	sites: list[dict[str, Any]] = []
	for b in payload.get("benches") or []:
		path = str(b.get("path") or "")
		if not path:
			continue
		benches.append(
			{
				"server_ref": server_ref,
				"path": path,
				"title": path.rstrip("/").rsplit("/", 1)[-1],
				"frappe_version": b.get("frappe_version"),
				"apps": [
					{
						"app": str(a.get("app")),
						"version": a.get("version"),
						"branch": a.get("branch"),
						"commit": a.get("commit"),
						"remote": a.get("remote"),
					}
					for a in b.get("apps") or []
					if a.get("app")
				],
			}
		)
		for s in b.get("sites") or []:
			domain = str(s.get("domain") or "")
			if not domain:
				continue
			sites.append(
				{
					"server_ref": server_ref,
					"bench_path": path,
					"domain": domain,
					"status": str(SiteStatus.MAINTENANCE if s.get("maintenance_mode") else SiteStatus.ACTIVE),
					"hostname": hostname,
				}
			)
	return benches, sites
