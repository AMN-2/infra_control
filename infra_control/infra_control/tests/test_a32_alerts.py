"""Integration (needs a site): the alert engine fires, dedups and resolves against real docs (A3.2)."""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from infra_control.install import after_install
from infra_control.monitoring import alerts


class TestA32Alerts(FrappeTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		after_install()
		if not frappe.db.exists("Provider Account", "DO-A32"):
			frappe.get_doc(
				{
					"doctype": "Provider Account",
					"label": "DO-A32",
					"provider": "digitalocean",
					"api_token": "dop_v1_" + "0" * 64,
					"is_staging": 1,
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Server", {"hostname": "a32-01.fra1"}):
			frappe.get_doc(
				{
					"doctype": "Server",
					"hostname": "a32-01.fra1",
					"provider_account": "DO-A32",
					"role": "all",
					"status": "Active",
				}
			).insert(ignore_permissions=True)
		cls._server = frappe.db.get_value("Server", {"hostname": "a32-01.fra1"}, "name")
		for old in frappe.get_all("Alert Rule", filters={"title": "A32 disk high"}, pluck="name"):
			frappe.delete_doc("Alert Rule", old, force=True, ignore_permissions=True)
		rule = frappe.get_doc(
			{
				"doctype": "Alert Rule",
				"title": "A32 disk high",
				"kind": "metric",
				"severity": "critical",
				"target_doctype": "Server",
				"metric": "disk",
				"operator": "gt",
				"threshold": 85.0,
				"for_minutes": 2,
				"enabled": 1,
			}
		)
		rule.append("channels", {"channel": "telegram"})
		rule.insert(ignore_permissions=True)
		cls._rule = rule.name
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls) -> None:
		for alert in frappe.get_all("Alert", filters={"target_name": cls._server}, pluck="name"):
			frappe.delete_doc("Alert", alert, force=True, ignore_permissions=True)
		for metric in frappe.get_all("Server Metric", filters={"server": cls._server}, pluck="name"):
			frappe.delete_doc("Server Metric", metric, force=True, ignore_permissions=True)
		if frappe.db.exists("Alert Rule", cls._rule):
			frappe.delete_doc("Alert Rule", cls._rule, force=True, ignore_permissions=True)
		if frappe.db.exists("Server", cls._server):
			frappe.delete_doc("Server", cls._server, force=True, ignore_permissions=True)
		if frappe.db.exists("Provider Account", "DO-A32"):
			frappe.delete_doc("Provider Account", "DO-A32", force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def _metric(self, disk: float, minutes_ago: int) -> None:
		frappe.get_doc(
			{
				"doctype": "Server Metric",
				"server": self._server,
				"resolution": "1m",
				"ts": add_to_date(now_datetime(), minutes=-minutes_ago),
				"disk": disk,
			}
		).insert(ignore_permissions=True)

	def tearDown(self) -> None:
		for alert in frappe.get_all("Alert", filters={"target_name": self._server}, pluck="name"):
			frappe.delete_doc("Alert", alert, force=True, ignore_permissions=True)
		for metric in frappe.get_all("Server Metric", filters={"server": self._server}, pluck="name"):
			frappe.delete_doc("Server Metric", metric, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDown()

	def _mine(self, status: str) -> int:
		# Scope to this rule+target: the live site has other rules/servers whose
		# alerts must not sway the count.
		return frappe.db.count("Alert", {"rule": self._rule, "target_name": self._server, "status": status})

	def test_fire_dedup_and_resolve(self) -> None:
		self._metric(90.0, 1)
		self._metric(92.0, 0)
		alerts.evaluate_rules()
		alert = frappe.db.get_value(
			"Alert",
			{"rule": self._rule, "target_name": self._server, "status": "firing"},
			["severity", "metric"],
			as_dict=True,
		)
		self.assertIsNotNone(alert, "a firing alert should exist for the breaching rule")
		self.assertEqual((alert["severity"], alert["metric"]), ("critical", "disk"))

		# Still breaching: no duplicate for this rule+target.
		self._metric(95.0, 0)
		alerts.evaluate_rules()
		self.assertEqual(self._mine("firing"), 1)

		# Recovered: the alert resolves, none left firing.
		self._metric(40.0, 0)
		alerts.evaluate_rules()
		self.assertEqual(self._mine("firing"), 0)
		self.assertEqual(self._mine("resolved"), 1)

	def test_drift_alert_lifecycle(self) -> None:
		findings = [{"kind": "server_missing", "doctype": "Server", "name": "SRV-X", "detail": "gone"}]
		self.assertEqual(alerts.sync_drift_alerts("DO-A32", findings)["fired"], 1)
		self.assertTrue(
			frappe.db.exists("Alert", {"target_name": "DO-A32", "kind": "drift", "status": "firing"})
		)
		self.assertEqual(alerts.sync_drift_alerts("DO-A32", [])["resolved"], 1)
		# clean up the drift alert (target is the account, not the server)
		for a in frappe.get_all("Alert", filters={"target_name": "DO-A32"}, pluck="name"):
			frappe.delete_doc("Alert", a, force=True, ignore_permissions=True)
		frappe.db.commit()
