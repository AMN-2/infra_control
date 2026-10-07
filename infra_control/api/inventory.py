"""inventory.topology: providers -> servers -> benches -> sites as nodes and edges."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import now_datetime

from infra_control.api import _serialize as ser
from infra_control.api import api
from infra_control.api._inventory_helpers import running_job_for, running_jobs


def _node(
	kind: str, ref: str, label: str, status: str | None, provider: str, running: bool
) -> dict[str, Any]:
	return {
		"id": f"{kind}:{ref}",
		"type": kind,
		"ref": ref,
		"label": label,
		"status": status,
		"provider": provider,
		"has_running_job": running,
	}


def _edge(source: str, target: str) -> dict[str, str]:
	return {"id": f"{source}->{target}", "source": source, "target": target}


@api()
def topology() -> dict[str, Any]:
	jobs = running_jobs()
	nodes: list[dict[str, Any]] = []
	edges: list[dict[str, str]] = []
	for acc in frappe.get_all(
		"Provider Account", filters={"enabled": 1}, fields=["name", "label", "provider"], order_by="name asc"
	):
		nodes.append(
			_node(
				"provider",
				acc["name"],
				acc.get("label") or acc["name"],
				None,
				acc["provider"],
				running_job_for("Provider Account", acc["name"], None, jobs) is not None,
			)
		)
	for srv in frappe.get_all(
		"Server", fields=["name", "hostname", "status", "provider", "provider_account"], order_by="name asc"
	):
		nodes.append(
			_node(
				"server",
				srv["name"],
				srv.get("hostname") or srv["name"],
				srv["status"],
				srv["provider"],
				running_job_for("Server", srv["name"], srv["name"], jobs) is not None,
			)
		)
		edges.append(_edge(f"provider:{srv['provider_account']}", f"server:{srv['name']}"))
	for b in frappe.get_all(
		"Bench", fields=["name", "title", "provider", "provider_account", "server"], order_by="name asc"
	):
		nodes.append(
			_node(
				"bench",
				b["name"],
				b.get("title") or b["name"],
				None,
				b["provider"],
				running_job_for("Bench", b["name"], b.get("server"), jobs) is not None,
			)
		)
		parent = f"server:{b['server']}" if b.get("server") else f"provider:{b['provider_account']}"
		edges.append(_edge(parent, f"bench:{b['name']}"))
	for s in frappe.get_all(
		"Site", fields=["name", "domain", "status", "provider", "bench", "server"], order_by="name asc"
	):
		nodes.append(
			_node(
				"site",
				s["name"],
				s.get("domain") or s["name"],
				s["status"],
				s["provider"],
				running_job_for("Site", s["name"], s.get("server"), jobs) is not None,
			)
		)
		edges.append(_edge(f"bench:{s['bench']}", f"site:{s['name']}"))
	return {"nodes": nodes, "edges": edges, "generated_at": ser.iso_utc(now_datetime()) or ""}
