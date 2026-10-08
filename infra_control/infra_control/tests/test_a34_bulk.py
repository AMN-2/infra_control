"""Integration (needs a site): a bulk operation driven end to end on the dummy provider (A3.4).

Creates a small rollout over three fixed Site targets with a low-risk dummy playbook and drives it
to completion (health checks skipped on staging), asserting the canary runs first (batch 0), the
batches follow, the counters add up and the final status is Success. A second run proves a broken
canary halts the rollout and skips the rest. Every document is namespaced by a fixed prefix and
removed in tearDown/tearDownClass so the live site is left pristine.
"""

from __future__ import annotations

from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from infra_control.bulk import engine as bulk_engine
from infra_control.core.enums import TERMINAL_BULK_STATUSES, BulkStatus
from infra_control.install import after_install
from infra_control.job_engine import engine as jobs

ACCOUNT = "DO-A34"
HOST = "a34-01.fra1"
BENCH_TITLE = "a34-bench"
SITES = ["a34-s1.test", "a34-s2.test", "a34-s3.test"]
PLAYBOOK = "site.migrate"
REST = TERMINAL_BULK_STATUSES | {BulkStatus.PAUSED, BulkStatus.HALTED}


class TestA34Bulk(FrappeTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		after_install()
		frappe.conf.infra_use_dummy_provider = 1
		jobs.sleep = lambda _s: None
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
		if not frappe.db.exists("Server", {"hostname": HOST}):
			frappe.get_doc(
				{
					"doctype": "Server",
					"hostname": HOST,
					"provider_account": ACCOUNT,
					"provider": "digitalocean",
					"role": "all",
					"status": "Active",
				}
			).insert(ignore_permissions=True)
		cls._server = frappe.db.get_value("Server", {"hostname": HOST}, "name")
		if not frappe.db.exists("Bench", {"title": BENCH_TITLE}):
			frappe.get_doc(
				{
					"doctype": "Bench",
					"title": BENCH_TITLE,
					"provider_account": ACCOUNT,
					"provider": "digitalocean",
					"server": cls._server,
					"path": "/home/frappe/a34-bench",
					"frappe_version": "15.0.0",
				}
			).insert(ignore_permissions=True)
		cls._bench = frappe.db.get_value("Bench", {"title": BENCH_TITLE}, "name")
		for domain in SITES:
			if not frappe.db.exists("Site", domain):
				frappe.get_doc(
					{
						"doctype": "Site",
						"domain": domain,
						"bench": cls._bench,
						"status": "Active",
					}
				).insert(ignore_permissions=True)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls) -> None:
		cls._cleanup()
		for site in SITES:
			if frappe.db.exists("Site", site):
				frappe.delete_doc("Site", site, force=True, ignore_permissions=True)
		if cls._bench and frappe.db.exists("Bench", cls._bench):
			frappe.delete_doc("Bench", cls._bench, force=True, ignore_permissions=True)
		if cls._server and frappe.db.exists("Server", cls._server):
			frappe.delete_doc("Server", cls._server, force=True, ignore_permissions=True)
		if frappe.db.exists("Provider Account", ACCOUNT):
			frappe.delete_doc("Provider Account", ACCOUNT, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def tearDown(self) -> None:
		self._cleanup()
		frappe.db.commit()
		super().tearDown()

	@classmethod
	def _cleanup(cls) -> None:
		"""Remove every bulk/job this test created (scoped to its own sites), leaving the site clean."""
		for bulk in frappe.get_all("Bulk Operation", filters={"canary_name": ["in", SITES]}, pluck="name"):
			frappe.delete_doc("Bulk Operation", bulk, force=True, ignore_permissions=True)
		for job in frappe.get_all("Infra Job", filters={"target_name": ["in", SITES]}, pluck="name"):
			for step in frappe.get_all("Infra Job Step", filters={"job": job}, pluck="name"):
				frappe.delete_doc("Infra Job Step", step, force=True, ignore_permissions=True)
			frappe.delete_doc("Infra Job", job, force=True, ignore_permissions=True)

	# --- helpers -----------------------------------------------------------------------------
	def _refs(self) -> list[dict[str, str]]:
		return [{"target_doctype": "Site", "target_name": s} for s in SITES]

	def _drive(self, name: str, limit: int = 60) -> frappe.Document:
		for _ in range(limit):
			doc = frappe.get_doc("Bulk Operation", name)
			if BulkStatus(doc.status) in REST:
				return doc
			bulk_engine.drive(name)
		self.fail("bulk operation did not reach a resting state")

	def _target_status(self, name: str) -> dict[str, dict[str, object]]:
		return {
			r.target_name: {"status": r.status, "batch": r.batch, "job": r.job}
			for r in frappe.get_all(
				"Bulk Operation Target",
				filters={"parent": name},
				fields=["target_name", "status", "batch", "job"],
			)
		}

	# --- tests -------------------------------------------------------------------------------
	def test_canary_then_batches_to_success(self) -> None:
		bulk = bulk_engine.create_bulk(
			PLAYBOOK,
			self._refs(),
			{"target_doctype": "Site", "target_name": SITES[0]},
			batch_size=5,
			failure_policy="halt",
			params={"_skip_health": 1},
			user="Administrator",
		)
		doc = self._drive(bulk.name)
		self.assertEqual(doc.status, str(BulkStatus.SUCCESS))
		self.assertEqual(doc.total, 3)
		self.assertEqual(doc.done, 3)
		self.assertEqual(doc.failed, 0)
		self.assertEqual(doc.batches_total, 1)

		targets = self._target_status(bulk.name)
		# The canary is batch 0 and ran (it has a child job); the rest are batch 1.
		self.assertEqual(targets[SITES[0]]["batch"], 0)
		self.assertTrue(targets[SITES[0]]["job"])
		self.assertEqual(targets[SITES[1]]["batch"], 1)
		self.assertEqual(targets[SITES[2]]["batch"], 1)
		self.assertTrue(all(t["status"] == "Success" for t in targets.values()))

		# Backup-first: every Site target was backed up before the migrate jobs ran.
		backups = frappe.get_all(
			"Infra Job",
			filters={"bulk_operation": bulk.name, "playbook": "site.backup"},
			pluck="target_name",
		)
		self.assertEqual(set(backups), set(SITES))

	def test_broken_canary_halts_and_skips_the_rest(self) -> None:
		import infra_control.providers.dummy.adapter as dummy

		def provider_for(target: jobs.Target) -> dummy.DummyProvider:
			# Only the canary fails; everything else would succeed. `site.backup` is itself a backup
			# playbook, so there is no separate backup phase to trip over before the canary runs.
			fail = target.name == SITES[0]
			return dummy.DummyProvider(None, fail_at_step=0 if fail else None)

		bulk = bulk_engine.create_bulk(
			"site.backup",
			self._refs(),
			{"target_doctype": "Site", "target_name": SITES[0]},
			batch_size=5,
			failure_policy="halt",
			params={"_skip_health": 1},
			user="Administrator",
		)
		with mock.patch.object(jobs, "_provider_for", provider_for):
			doc = self._drive(bulk.name)

		self.assertEqual(doc.status, str(BulkStatus.HALTED))
		self.assertEqual(doc.failed, 1)
		targets = self._target_status(bulk.name)
		self.assertEqual(targets[SITES[0]]["batch"], 0)
		self.assertEqual(targets[SITES[0]]["status"], "Failed")
		self.assertEqual(targets[SITES[1]]["status"], "Skipped")
		self.assertEqual(targets[SITES[2]]["status"], "Skipped")
		# The batch sites never got a job: the broken canary stopped the rollout.
		ran = frappe.get_all(
			"Infra Job",
			filters={"bulk_operation": bulk.name, "playbook": "site.backup"},
			pluck="target_name",
		)
		self.assertNotIn(SITES[1], ran)
		self.assertNotIn(SITES[2], ran)
