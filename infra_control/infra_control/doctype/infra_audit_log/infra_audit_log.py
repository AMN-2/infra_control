# Copyright (c) 2026, SmartChoice IQ and contributors
# For license information, please see license.txt
"""Immutable: rows are inserted by `infra_control.core.audit.record` and never changed."""

import frappe
from frappe import _
from frappe.model.document import Document


class InfraAuditLog(Document):
	def validate(self) -> None:
		if not self.is_new():
			frappe.throw(_("Infra Audit Log entries cannot be modified"), frappe.PermissionError)

	def on_trash(self) -> None:
		frappe.throw(_("Infra Audit Log entries cannot be deleted"), frappe.PermissionError)
