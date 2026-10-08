"""Integration (needs a site): the A3.2 alerts/alert_rules HTTP API over real docs.

Exercises alert_rules.create -> list -> get -> update -> delete of a metric rule and alerts.ack of
a manually-inserted firing Alert, calling the Python functions directly (not over HTTP). Every doc
is guarded by a fixed title/name and removed again, so the live site is left pristine (audit-log
rows are append-only by design and cannot be removed; that is the only residue).
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from infra_control.api import alert_rules, alerts
from infra_control.install import after_install

RULE_TITLE = "A32API cpu high"
UPDATED_TITLE = "A32API cpu very high"
HOSTNAME = "a32api-01.fra1"
ACCOUNT = "DO-A32API"


def _call(fn: Any, **kwargs: Any) -> tuple[int, dict[str, Any]]:
	"""Invoke the handler behind a whitelisted endpoint and return (status, body)."""
	frappe.local.response = frappe._dict({"docs": []})
	fn.handler(**kwargs)
	body = dict(frappe.local.response)
	status = body.pop("http_status_code", 200)
	return status, body


class TestA32AlertsApi(FrappeTestCase):
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
		if not frappe.db.exists("Server", {"hostname": HOSTNAME}):
			frappe.get_doc(
				{
					"doctype": "Server",
					"hostname": HOSTNAME,
					"provider_account": ACCOUNT,
					"role": "all",
					"status": "Active",
				}
			).insert(ignore_permissions=True)
		cls._server = frappe.db.get_value("Server", {"hostname": HOSTNAME}, "name")
		cls._cleanup()
		frappe.db.commit()

	@classmethod
	def _cleanup(cls) -> None:
		for alert in frappe.get_all("Alert", filters={"target_name": cls._server}, pluck="name"):
			frappe.delete_doc("Alert", alert, force=True, ignore_permissions=True)
		for title in (RULE_TITLE, UPDATED_TITLE):
			for rule in frappe.get_all("Alert Rule", filters={"title": title}, pluck="name"):
				frappe.delete_doc("Alert Rule", rule, force=True, ignore_permissions=True)

	@classmethod
	def tearDownClass(cls) -> None:
		cls._cleanup()
		if frappe.db.exists("Server", cls._server):
			frappe.delete_doc("Server", cls._server, force=True, ignore_permissions=True)
		if frappe.db.exists("Provider Account", ACCOUNT):
			frappe.delete_doc("Provider Account", ACCOUNT, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def tearDown(self) -> None:
		self._cleanup()
		frappe.db.commit()
		super().tearDown()

	def _create_rule(self, title: str = RULE_TITLE) -> str:
		status, body = _call(
			alert_rules.create,
			title=title,
			metric="cpu",
			operator="gt",
			threshold=90,
			for_minutes=5,
			severity="warning",
			channels=["telegram", "email"],
		)
		self.assertEqual(status, 200, body)
		return str(body["rule"]["name"])

	def _insert_firing_alert(self, rule: str) -> str:
		doc = frappe.get_doc(
			{
				"doctype": "Alert",
				"rule": rule,
				"kind": "metric",
				"severity": "warning",
				"status": "firing",
				"target_doctype": "Server",
				"target_name": self._server,
				"metric": "cpu",
				"value": 95.0,
				"message": "CPU 95%",
				"fired_at": now_datetime(),
			}
		)
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		return str(doc.name)

	def test_rule_crud_and_history_kept_on_delete(self) -> None:
		name = self._create_rule()
		frappe.db.commit()

		# create shape
		_, created = _call(alert_rules.get, rule=name)
		self.assertEqual(created["kind"], "metric")
		self.assertEqual(created["target_doctype"], "Server")
		self.assertFalse(created["builtin"])
		self.assertEqual(created["channels"], ["telegram", "email"])
		self.assertEqual(created["threshold"], 90.0)

		# list contains it
		_, page = _call(alert_rules.list, limit=200)
		self.assertIn(name, [r["name"] for r in page["items"]])

		# update the allowed fields
		status, updated = _call(
			alert_rules.update,
			rule=name,
			title=UPDATED_TITLE,
			threshold=95,
			severity="critical",
			channels=["email"],
			enabled=False,
		)
		self.assertEqual(status, 200, updated)
		self.assertEqual(updated["rule"]["title"], UPDATED_TITLE)
		self.assertEqual(updated["rule"]["threshold"], 95.0)
		self.assertEqual(updated["rule"]["severity"], "critical")
		self.assertFalse(updated["rule"]["enabled"])
		self.assertEqual(updated["rule"]["channels"], ["email"])
		frappe.db.commit()

		# a historical alert for this rule must survive the rule's deletion
		alert_name = self._insert_firing_alert(name)
		status, deleted = _call(alert_rules.delete, rule=name)
		self.assertEqual(status, 200, deleted)
		self.assertEqual(deleted, {"rule": name, "deleted": True})
		self.assertFalse(frappe.db.exists("Alert Rule", name))
		self.assertTrue(frappe.db.exists("Alert", alert_name), "historical alert must be kept")
		frappe.db.commit()

	def test_builtin_rule_cannot_be_deleted(self) -> None:
		builtin = frappe.get_all("Alert Rule", filters={"builtin": 1}, pluck="name", limit=1)
		self.assertTrue(builtin, "install should seed built-in rules")
		status, body = _call(alert_rules.delete, rule=builtin[0])
		self.assertEqual(status, 409)
		self.assertEqual(body["error"]["code"], "invalid_state")
		self.assertTrue(frappe.db.exists("Alert Rule", builtin[0]))

	def test_ack_firing_alert(self) -> None:
		rule = self._create_rule()
		frappe.db.commit()
		alert_name = self._insert_firing_alert(rule)

		status, body = _call(alerts.ack, alert=alert_name)
		self.assertEqual(status, 200, body)
		self.assertEqual(body["alert"]["status"], "acknowledged")
		self.assertEqual(body["alert"]["acknowledged_by"], frappe.session.user)
		self.assertIsNotNone(body["alert"]["acknowledged_at"])
		frappe.db.commit()

		# it now appears among the firing-first list, and a second ack is rejected
		_, page = _call(alerts.list, target_name=self._server)
		self.assertIn(alert_name, [a["name"] for a in page["items"]])
		status, body = _call(alerts.ack, alert=alert_name)
		self.assertEqual(status, 409)
		self.assertEqual(body["error"]["code"], "invalid_state")
