"""Apply a `SyncPlan` to the DocTypes (the only writer of inventory documents besides the
adapters' success recorders) and emit `infra:inventory.changed` for what changed.

Adapters are Frappe-free, so they reach this through their `Records` seam.
"""

from __future__ import annotations

from typing import Any

import frappe

from infra_control.inventory.plan import SyncPlan, plan_sync
from infra_control.job_engine import realtime


def load_documents(account: str) -> dict[str, list[dict[str, Any]]]:
	"""The account's Server, Bench and Site documents in the shape `plan_sync` compares."""
	servers = frappe.get_all(
		"Server",
		filters={"provider_account": account},
		fields=[
			"name",
			"provider_ref",
			"hostname",
			"status",
			"public_ip",
			"private_ip",
			"region",
			"size",
			"role",
		],
	)
	benches = frappe.get_all(
		"Bench",
		filters={"provider_account": account},
		fields=["name", "server", "path", "frappe_version"],
	)
	apps_by_bench: dict[str, list[dict[str, Any]]] = {}
	if benches:
		for row in frappe.get_all(
			"Bench App",
			filters={"parent": ["in", [b["name"] for b in benches]], "parenttype": "Bench"},
			fields=["parent", "app", "version", "branch", "commit", "remote"],
			order_by="idx asc",
		):
			apps_by_bench.setdefault(str(row["parent"]), []).append(
				{
					"app": row["app"],
					"version": row["version"],
					"branch": row["branch"],
					"commit": row.get("commit"),
					"remote": row.get("remote"),
				}
			)
	for b in benches:
		b["apps"] = apps_by_bench.get(str(b["name"]), [])
	sites = frappe.get_all(
		"Site",
		filters={"provider_account": account},
		fields=["name", "domain", "status", "bench", "server"],
	)
	return {
		"servers": [dict(s) for s in servers],
		"benches": [dict(b) for b in benches],
		"sites": [dict(s) for s in sites],
	}


def _app_row(a: dict[str, Any]) -> dict[str, Any]:
	return {
		"app": a["app"],
		"version": a.get("version"),
		"branch": a.get("branch"),
		"commit": a.get("commit"),
		"remote": a.get("remote"),
	}


def apply_plan(plan: SyncPlan) -> dict[str, Any]:
	"""Write the plan. Returns the summary plus the names created, for the job output."""
	created: dict[str, list[str]] = {"Server": [], "Bench": [], "Site": []}
	updated: dict[str, list[str]] = {"Server": [], "Bench": [], "Site": []}
	server_names: dict[str, str] = {}  # placeholder `new:<ref>` -> real name

	for spec in plan.create_servers:
		tags = spec.pop("tags", [])
		doc: Any = frappe.get_doc(
			{
				"doctype": "Server",
				**spec,
				"ssh_user": "frappe",
				"ssh_port": 22,
				"tags": [{"tag": t} for t in tags],
			}
		)
		doc.insert(ignore_permissions=True)
		server_names[f"new:{spec['provider_ref']}"] = str(doc.name)
		created["Server"].append(str(doc.name))
	for name, changes in plan.update_servers:
		frappe.db.set_value("Server", name, changes)
		updated["Server"].append(name)

	def real_server(value: str) -> str:
		return server_names.get(value, value)

	bench_names: dict[str, str] = {}  # placeholder `new:<server>:<path>` -> real name
	for spec in plan.create_benches:
		server = real_server(str(spec["server"]))
		apps = spec.get("apps") or []
		doc = frappe.get_doc(
			{
				"doctype": "Bench",
				"title": spec["title"],
				"provider_account": spec["provider_account"],
				"provider": spec["provider"],
				"provider_ref": f"{server}:{spec['path']}",
				"server": server,
				"path": spec["path"],
				"frappe_version": spec.get("frappe_version"),
				"apps": [_app_row(a) for a in apps],
			}
		)
		doc.insert(ignore_permissions=True)
		bench_names[f"new:{spec['server']}:{spec['path']}"] = str(doc.name)
		created["Bench"].append(str(doc.name))
	for name, changes in plan.update_benches:
		doc = frappe.get_doc("Bench", name)
		if "frappe_version" in changes:
			doc.frappe_version = changes["frappe_version"]
		if "apps" in changes:
			# Keep the last update check for apps whose commit did not move.
			previous = {str(r.app): r for r in doc.get("apps") or []}
			doc.set("apps", [])
			for a in changes["apps"]:
				row = _app_row(a)
				old = previous.get(str(a["app"]))
				if old is not None and (old.commit or None) == (a.get("commit") or None):
					for f in ("upstream_commit", "behind", "latest_tag", "checked_at"):
						row[f] = old.get(f)
				doc.append("apps", row)
		doc.save(ignore_permissions=True)
		updated["Bench"].append(name)

	for spec in plan.create_sites:
		server = real_server(str(spec["server"]))
		bench = bench_names.get(str(spec["bench"]), str(spec["bench"]))
		doc = frappe.get_doc(
			{
				"doctype": "Site",
				"domain": spec["domain"],
				"status": spec["status"],
				"bench": bench,
				"server": server,
				"provider_account": spec["provider_account"],
				"provider": spec["provider"],
				"provider_ref": spec["provider_ref"].replace(str(spec["server"]), server, 1),
			}
		)
		doc.insert(ignore_permissions=True)
		created["Site"].append(str(doc.name))
	for name, changes in plan.update_sites:
		if "bench" in changes:
			changes = {**changes, "bench": bench_names.get(str(changes["bench"]), str(changes["bench"]))}
		frappe.db.set_value("Site", name, changes)
		updated["Site"].append(name)

	frappe.db.commit()
	for doctype, names in created.items():
		for name in names:
			realtime.emit(*realtime.inventory_changed(doctype, name, "created"))
	for doctype, names in updated.items():
		for name in names:
			realtime.emit(*realtime.inventory_changed(doctype, name, "updated"))
	return {
		**plan.summary,
		"created": created,
		"updated": updated,
		"findings": [
			{"kind": f.kind, "doctype": f.doctype, "name": f.name, "detail": f.detail} for f in plan.findings
		],
	}


def reconcile(account: str, provider: str, inventory: dict[str, Any]) -> dict[str, Any]:
	"""Plan against the current documents and apply. The adapters' `Records.reconcile`."""
	plan = plan_sync(account, provider, inventory, load_documents(account))
	result = apply_plan(plan)
	# A2.5/A3.3: findings open or resolve the account's inventory-drift alert.
	from infra_control.monitoring.alerts import sync_drift_alerts

	drift = sync_drift_alerts(account, list(result.get("findings") or []))
	result["drift_alerts"] = drift
	return result
