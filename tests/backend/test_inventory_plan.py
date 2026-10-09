"""A2.5: inventory reconciliation plan (pure) and discovery normalisation."""

from __future__ import annotations

from typing import Any

from infra_control.core.enums import ServerRole, ServerStatus
from infra_control.inventory.plan import SyncPlan, normalize_discovery, plan_sync

ACCOUNT = "DO-STAGING-LIVE"


def droplet(ref: str, host: str, **extra: Any) -> dict[str, Any]:
	return {
		"provider_ref": ref,
		"hostname": host,
		"status": ServerStatus.ACTIVE,
		"public_ip": f"10.0.0.{ref[-1]}",
		"private_ip": None,
		"region": "fra1",
		"size": "s-2vcpu-4gb",
		"role": ServerRole.ALL,
		"tags": ["gate"],
		**extra,
	}


def server_doc(name: str, ref: str, host: str, **extra: Any) -> dict[str, Any]:
	return {
		"name": name,
		"provider_ref": ref,
		"hostname": host,
		"status": "Active",
		"public_ip": f"10.0.0.{ref[-1]}",
		"private_ip": None,
		"region": "fra1",
		"size": "s-2vcpu-4gb",
		"role": "all",
		**extra,
	}


DISCOVERY = {
	"benches": [
		{
			"path": "/home/frappe/frappe-bench",
			"frappe_version": "15.122.0",
			"apps": [{"app": "frappe", "version": "15.122.0", "branch": "version-15"}],
			"sites": [
				{"domain": "a.iq", "maintenance_mode": False, "db_name": "_a"},
				{"domain": "b.iq", "maintenance_mode": True, "db_name": "_b"},
			],
		}
	]
}


def inventory(
	servers: list[dict[str, Any]],
	hosts: dict[str, dict[str, Any]] | None = None,
	unreachable: list[str] | None = None,
) -> dict[str, Any]:
	benches: list[dict[str, Any]] = []
	sites: list[dict[str, Any]] = []
	discovered: list[str] = []
	for host, payload in (hosts or {}).items():
		ref = next(s["provider_ref"] for s in servers if s["hostname"] == host)
		b, s_ = normalize_discovery(ref, host, payload)
		benches.extend(b)
		sites.extend(s_)
		discovered.append(ref)
	return {
		"servers": servers,
		"benches": benches,
		"sites": sites,
		"unreachable": unreachable or [],
		"discovered": discovered,
	}


def test_normalize_discovery_maps_benches_sites_and_maintenance() -> None:
	benches, sites = normalize_discovery("999", "gate-03.fra1", DISCOVERY)
	assert benches == [
		{
			"server_ref": "999",
			"path": "/home/frappe/frappe-bench",
			"title": "frappe-bench",
			"frappe_version": "15.122.0",
			"apps": [
				{
					"app": "frappe",
					"version": "15.122.0",
					"branch": "version-15",
					"commit": None,
					"remote": None,
				}
			],
		}
	]
	assert [(s["domain"], s["status"]) for s in sites] == [("a.iq", "Active"), ("b.iq", "Maintenance")]
	assert normalize_discovery("1", "h", {}) == ([], [])


def test_everything_new_is_created_with_placeholders_resolved_in_order() -> None:
	plan = plan_sync(
		ACCOUNT,
		"digitalocean",
		inventory([droplet("999", "gate-03.fra1")], {"gate-03.fra1": DISCOVERY}),
		{"servers": [], "benches": [], "sites": []},
	)
	assert plan.summary == {
		"servers_created": 1,
		"servers_updated": 0,
		"benches_created": 1,
		"benches_updated": 0,
		"sites_created": 2,
		"sites_updated": 0,
		"findings": 0,
	}
	srv = plan.create_servers[0]
	assert (
		srv["provider_ref"] == "999"
		and srv["provider_account"] == ACCOUNT
		and srv["status"] == "Active"
		and srv["tags"] == ["gate"]
	)
	bench = plan.create_benches[0]
	assert (
		bench["server"] == "new:999"
		and bench["path"] == "/home/frappe/frappe-bench"
		and bench["title"] == "frappe-bench"
	)
	assert bench["apps"][0]["version"] == "15.122.0"
	site = plan.create_sites[0]
	assert site["bench"] == "new:new:999:/home/frappe/frappe-bench" and site["server"] == "new:999"
	assert site["provider_ref"] == "new:999:/home/frappe/frappe-bench:a.iq"


def test_only_changed_provider_owned_fields_are_updated() -> None:
	docs = {
		"servers": [server_doc("SRV-0004", "999", "gate-03.fra1", size="s-1vcpu-1gb")],
		"benches": [
			{
				"name": "BENCH-0003",
				"server": "SRV-0004",
				"path": "/home/frappe/frappe-bench",
				"frappe_version": "15.98.1",
				"apps": [{"app": "frappe", "version": "15.98.1", "branch": "version-15"}],
			}
		],
		"sites": [
			{
				"name": "a.iq",
				"domain": "a.iq",
				"status": "Active",
				"bench": "BENCH-0003",
				"server": "SRV-0004",
			},
			{
				"name": "b.iq",
				"domain": "b.iq",
				"status": "Active",
				"bench": "BENCH-0003",
				"server": "SRV-0004",
			},
		],
	}
	plan = plan_sync(
		ACCOUNT,
		"digitalocean",
		inventory([droplet("999", "gate-03.fra1")], {"gate-03.fra1": DISCOVERY}),
		docs,
	)
	assert plan.create_servers == [] and plan.create_benches == [] and plan.create_sites == []
	assert plan.update_servers == [("SRV-0004", {"size": "s-2vcpu-4gb"})]
	# frappe_version 15.98.1 -> 15.122.0 and the app version both changed.
	assert len(plan.update_benches) == 1
	name, changes = plan.update_benches[0]
	assert name == "BENCH-0003" and changes["frappe_version"] == "15.122.0"
	assert changes["apps"][0]["version"] == "15.122.0"
	assert plan.update_sites == [("b.iq", {"status": "Maintenance"})]
	assert plan.findings == []


def test_gone_resources_are_findings_not_deletions() -> None:
	docs = {
		"servers": [
			server_doc("SRV-0004", "999", "gate-03.fra1"),
			server_doc("SRV-0009", "404", "ghost.fra1"),
			server_doc("SRV-0010", "500", "kept.fra1", status="Archived"),
		],
		"benches": [
			{
				"name": "BENCH-GONE",
				"server": "SRV-0004",
				"path": "/home/frappe/old-bench",
				"frappe_version": "15",
				"apps": [],
			}
		],
		"sites": [
			{
				"name": "gone.iq",
				"domain": "gone.iq",
				"status": "Active",
				"bench": "BENCH-0003",
				"server": "SRV-0004",
			}
		],
	}
	inv = inventory([droplet("999", "gate-03.fra1")], {"gate-03.fra1": DISCOVERY})
	plan = plan_sync(ACCOUNT, "digitalocean", inv, docs)
	kinds = {(f.kind, f.name) for f in plan.findings}
	# The droplet the provider no longer lists is a finding; the archived one is left alone.
	assert ("server_missing", "SRV-0009") in kinds
	assert not any(k[0] == "server_missing" and k[1] == "SRV-0010" for k in kinds)
	# The gone bench and site are on a server discovery actually scanned, so they are findings.
	assert ("bench_missing", "BENCH-GONE") in kinds
	assert ("site_missing", "gone.iq") in kinds
	assert plan.create_servers == [] and plan.update_servers == []


def test_benches_and_sites_on_unscanned_servers_are_never_reported_missing() -> None:
	# gate-03 has a droplet but discovery did not reach it (unreachable), so its bench/site
	# documents must not be reported missing just because we have no host data.
	docs = {
		"servers": [server_doc("SRV-0004", "999", "gate-03.fra1")],
		"benches": [
			{
				"name": "BENCH-0003",
				"server": "SRV-0004",
				"path": "/home/frappe/frappe-bench",
				"frappe_version": "15.98.1",
				"apps": [],
			}
		],
		"sites": [
			{
				"name": "a.iq",
				"domain": "a.iq",
				"status": "Active",
				"bench": "BENCH-0003",
				"server": "SRV-0004",
			}
		],
	}
	inv = inventory([droplet("999", "gate-03.fra1")], hosts=None, unreachable=["gate-03.fra1"])
	plan = plan_sync(ACCOUNT, "digitalocean", inv, docs)
	assert [f.kind for f in plan.findings] == ["server_unreachable"]
	assert plan.update_benches == [] and plan.update_sites == []


def test_suspended_and_archived_sites_keep_their_human_set_state() -> None:
	docs = {
		"servers": [server_doc("SRV-0004", "999", "gate-03.fra1")],
		"benches": [
			{
				"name": "BENCH-0003",
				"server": "SRV-0004",
				"path": "/home/frappe/frappe-bench",
				"frappe_version": "15.122.0",
				"apps": [
					{
						"app": "frappe",
						"version": "15.122.0",
						"branch": "version-15",
						"commit": None,
						"remote": None,
					}
				],
			}
		],
		"sites": [
			{
				"name": "a.iq",
				"domain": "a.iq",
				"status": "Suspended",
				"bench": "BENCH-0003",
				"server": "SRV-0004",
			},
			{
				"name": "b.iq",
				"domain": "b.iq",
				"status": "Archived",
				"bench": "BENCH-0003",
				"server": "SRV-0004",
			},
		],
	}
	plan = plan_sync(
		ACCOUNT,
		"digitalocean",
		inventory([droplet("999", "gate-03.fra1")], {"gate-03.fra1": DISCOVERY}),
		docs,
	)
	# The host reports both as Active/Maintenance, but Suspended and Archived are human states.
	assert plan.update_sites == []
	assert all(f.kind != "site_missing" for f in plan.findings)


def test_empty_inventory_is_an_empty_plan() -> None:
	plan = plan_sync(
		ACCOUNT,
		"digitalocean",
		{"servers": [], "benches": [], "sites": [], "unreachable": [], "discovered": []},
		{"servers": [], "benches": [], "sites": []},
	)
	assert isinstance(plan, SyncPlan)
	assert all(v == 0 for v in plan.summary.values())
