# Copyright (c) 2026, SmartChoice IQ and contributors
# For license information, please see license.txt

import json
from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document

from infra_control.core.enums import Risk


class Playbook(Document):
	def validate(self) -> None:
		schema: Any = self.get("params_schema")
		if isinstance(schema, str):
			schema = json.loads(schema) if schema.strip() else None
		if schema is None:
			self.params_schema = json.dumps(
				{"type": "object", "additionalProperties": False, "properties": {}}
			)
		elif not isinstance(schema, dict) or schema.get("type") != "object":
			frappe.throw(_("params_schema must be a JSON Schema object with type 'object'"))
		if not self.ansible_file and not self.provider_method:
			frappe.throw(_("A playbook needs an ansible_file or a provider_method"))
		if self.creates and self.target_doctype not in ("Provider Account", "Bench"):
			frappe.throw(_("Creation playbooks target a Provider Account or a Bench (ADR 0001)"))

	@property
	def is_high_risk(self) -> bool:
		return bool(self.risk == Risk.HIGH)
