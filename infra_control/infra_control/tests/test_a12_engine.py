"""Integration (needs a site): create_job + run_job on the dummy provider, synchronously."""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from infra_control.install import after_install
from infra_control.job_engine import engine


class TestA12Engine(FrappeTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		after_install()
		frappe.conf.infra_use_dummy_provider = 1
		if not frappe.db.exists("Provider Account", "DO-TEST"):
			frappe.get_doc(
				{
					"doctype": "Provider Account",
					"label": "DO-TEST",
					"provider": "digitalocean",
					"api_token": "dop_v1_" + "0" * 64,
					"is_staging": 1,
				}
			).insert()
		if not frappe.db.exists("Server", {"hostname": "test-app-01"}):
			cls.server = frappe.get_doc(
				{
					"doctype": "Server",
					"hostname": "test-app-01",
					"provider_account": "DO-TEST",
					"role": "all",
					"status": "Active",
				}
			).insert()
		else:
			cls.server = frappe.get_doc("Server", {"hostname": "test-app-01"})

	def test_dummy_playbook_runs_end_to_end(self) -> None:
		engine.sleep = lambda s: None
		job = engine.create_job(
			"server.snapshot", "Server", self.server.name, enqueue=False, user="Administrator"
		)
		self.assertEqual(job.status, "Queued")
		engine.run_job(job.name)
		job.reload()
		self.assertEqual(job.status, "Success")
		self.assertEqual(job.progress, 100)
		steps = frappe.get_all("Infra Job Step", filters={"job": job.name}, fields=["title", "status"])
		self.assertEqual([(s.title, s.status) for s in steps], [("Snapshot", "Success")])
		self.assertIsNone(frappe.cache().get(f"infra:lock:server:{self.server.name}"))
		self.assertTrue(frappe.db.exists("Infra Audit Log", {"job": job.name, "result": "success"}))
