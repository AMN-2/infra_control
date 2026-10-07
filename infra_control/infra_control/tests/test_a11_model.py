"""Integration (needs a site): roles exist, audit log is immutable, alert rule kinds validate."""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from infra_control.core import audit
from infra_control.core.permissions import ROLES
from infra_control.install import BUILTIN_RULES, ensure_builtin_alert_rules, ensure_roles


class TestA11Model(FrappeTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		ensure_roles()
		ensure_builtin_alert_rules()

	def test_roles_exist_and_install_is_idempotent(self) -> None:
		for role in ROLES:
			self.assertTrue(frappe.db.exists("Role", role), role)
		ensure_roles()
		ensure_builtin_alert_rules()
		self.assertEqual(frappe.db.count("Alert Rule", {"builtin": 1}), len(BUILTIN_RULES))

	def test_audit_log_is_append_only(self) -> None:
		name = audit.record(
			"jobs.run:site.backup",
			result="success",
			target_doctype="Site",
			target_name=None,
			params={"with_files": True},
		)
		doc = frappe.get_doc("Infra Audit Log", name)
		self.assertEqual(doc.action, "jobs.run:site.backup")
		self.assertEqual(len(doc.params_hash), 64)
		doc.action = "tampered"
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Infra Audit Log", name, ignore_permissions=True, force=True)

	def test_no_role_can_write_audit_log(self) -> None:
		for role in ROLES:
			perms = frappe.get_all(
				"DocPerm",
				filters={"parent": "Infra Audit Log", "role": role},
				fields=["write", "delete", "create"],
			)
			for p in perms:
				self.assertEqual((p.write, p.delete, p.create), (0, 0, 0), role)

	def test_builtin_rule_cannot_be_deleted_or_created_by_users(self) -> None:
		heartbeat = frappe.get_doc("Alert Rule", {"kind": "heartbeat", "builtin": 1})
		with self.assertRaises(frappe.ValidationError):
			heartbeat.delete()
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Alert Rule",
					"title": "x",
					"kind": "drift",
					"target_doctype": "Provider Account",
					"severity": "info",
				}
			).insert()

	def test_metric_rule_requires_its_fields_and_clears_others(self) -> None:
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Alert Rule",
					"title": "RAM",
					"kind": "metric",
					"target_doctype": "Server",
					"severity": "warning",
				}
			).insert()
		rule = frappe.get_doc(
			{
				"doctype": "Alert Rule",
				"title": "RAM above 95%",
				"kind": "metric",
				"target_doctype": "Server",
				"metric": "ram",
				"operator": "gt",
				"threshold": 95,
				"for_minutes": 5,
				"severity": "warning",
				"channels": [{"channel": "telegram"}],
			}
		).insert()
		self.assertEqual(rule.builtin, 0)
		rule.delete()

	def test_playbook_catalogue_is_seeded_and_upsert_is_idempotent(self) -> None:
		from infra_control.install import PLAYBOOKS, ensure_playbooks

		ensure_playbooks()
		ensure_playbooks()
		self.assertEqual(frappe.db.count("Playbook"), len(PLAYBOOKS))
		migrate = frappe.get_doc("Playbook", "site.migrate")
		self.assertEqual(migrate.risk, "medium")
		self.assertTrue(migrate.params_schema)
