"""Integration (needs a site): inventory reconciliation writes and is idempotent (A2.5)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.tests.utils import FrappeTestCase

from infra_control.install import after_install
from infra_control.inventory.apply import reconcile

ACCOUNT = "DO-INV-TEST"


def _droplet(ref: str, host: str, size: str = "s-2vcpu-4gb") -> dict[str, Any]:
	from infra_control.core.enums import ServerRole, ServerStatus

	return {
		"provider_ref": ref,
		"hostname": host,
		"status": ServerStatus.ACTIVE,
		"public_ip": f"10.1.0.{ref[-1]}",
		"private_ip": None,
		"region": "fra1",
		"size": size,
		"role": ServerRole.ALL,
		"tags": ["inv-test"],
	}


class TestA25Inventory(FrappeTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		after_install()
		if not frappe.db.exists("Provider Account", ACCOUNT):
			frappe.get_doc(
				{
					"doctype": "Provider Account",
					"label": ACCOUNT,
					"provider": "digitalocean",
					"api_token": "dop_v1_" + "0" * 64,
					"is_staging": 1,
				}
			).insert(ignore_permissions=True)

	def _inventory(self, size: str = "s-2vcpu-4gb", version: str = "15.1.0") -> dict[str, Any]:
		return {
			"servers": [_droplet("701", "inv-01.fra1", size)],
			"benches": [
				{
					"server_ref": "701",
					"path": "/home/frappe/frappe-bench",
					"title": "frappe-bench",
					"frappe_version": version,
					"apps": [{"app": "frappe", "version": version, "branch": "version-15"}],
				}
			],
			"sites": [
				{
					"server_ref": "701",
					"bench_path": "/home/frappe/frappe-bench",
					"domain": "inv-a.test",
					"status": "Active",
				}
			],
			"unreachable": [],
			"discovered": ["701"],
		}

	def test_reconcile_creates_then_is_idempotent_then_updates(self) -> None:
		first = reconcile(ACCOUNT, "digitalocean", self._inventory())
		self.assertEqual(
			(first["servers_created"], first["benches_created"], first["sites_created"]), (1, 1, 1)
		)
		server = frappe.db.get_value("Server", {"provider_ref": "701"}, "name")
		self.assertTrue(server)
		bench = frappe.db.get_value("Bench", {"server": server}, "name")
		site = frappe.db.get_value("Site", "inv-a.test", "bench")
		self.assertEqual(site, bench)

		# Same inventory again: nothing created, nothing updated.
		second = reconcile(ACCOUNT, "digitalocean", self._inventory())
		self.assertEqual(
			(
				second["servers_created"],
				second["servers_updated"],
				second["benches_updated"],
				second["sites_updated"],
			),
			(0, 0, 0, 0),
		)

		# A changed size and frappe version update in place, still no creation.
		third = reconcile(ACCOUNT, "digitalocean", self._inventory(size="s-4vcpu-8gb", version="15.2.0"))
		self.assertEqual(third["servers_created"], 0)
		self.assertEqual(frappe.db.get_value("Server", server, "size"), "s-4vcpu-8gb")
		self.assertEqual(frappe.db.get_value("Bench", bench, "frappe_version"), "15.2.0")
		apps = frappe.get_all("Bench App", filters={"parent": bench}, fields=["app", "version"])
		self.assertEqual([(a["app"], a["version"]) for a in apps], [("frappe", "15.2.0")])

	def test_gone_resource_is_a_finding_not_a_deletion(self) -> None:
		reconcile(ACCOUNT, "digitalocean", self._inventory())
		# The provider no longer lists droplet 701: the Server stays, a finding reports it.
		result = reconcile(
			ACCOUNT,
			"digitalocean",
			{"servers": [], "benches": [], "sites": [], "unreachable": [], "discovered": []},
		)
		self.assertTrue(frappe.db.exists("Server", {"provider_ref": "701"}))
		kinds = {f["kind"] for f in result["findings"]}
		self.assertIn("server_missing", kinds)
