# Copyright (c) 2026, SmartChoice IQ and contributors
# For license information, please see license.txt
"""Per-kind field rules from contracts/openapi.yaml (AlertRule); built-ins cannot be deleted."""

import frappe
from frappe import _
from frappe.model.document import Document

from infra_control.core.enums import RULE_KIND_FIELDS, RULE_KIND_TARGET, AlertRuleKind


class AlertRule(Document):
	def validate(self) -> None:
		kind = AlertRuleKind(self.kind)
		expected_target = str(RULE_KIND_TARGET[kind])
		if self.target_doctype != expected_target:
			frappe.throw(_("Rules of kind {0} target {1}").format(kind, expected_target))
		used = RULE_KIND_FIELDS[kind]
		for field in ("metric", "operator", "threshold", "for_minutes"):
			if field in used:
				if self.get(field) in (None, ""):
					frappe.throw(_("{0} is required for kind {1}").format(field, kind))
			else:
				self.set(field, None)
		if kind == AlertRuleKind.METRIC and self.builtin:
			frappe.throw(_("Metric rules are user-defined and cannot be built-in"))
		if kind != AlertRuleKind.METRIC and not self.builtin:
			frappe.throw(_("Rules of kind {0} are built-in and cannot be created").format(kind))
		if not self.is_new() and self.has_value_changed("kind"):
			frappe.throw(_("The kind of a rule cannot change"))

	def on_trash(self) -> None:
		if self.builtin:
			frappe.throw(_("Built-in alert rules cannot be deleted"), frappe.ValidationError)
