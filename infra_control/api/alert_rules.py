"""alert_rules CRUD (contracts/openapi.yaml) over the A3.2 `Alert Rule` DocType.

The engine owns the rule semantics; this module is the thin read/write API. `create` makes only
`metric` rules (the built-in kinds exist from install); `update` enforces the per-kind editable
matrix from the `AlertRule` schema; `delete` removes a user `metric` rule but keeps its historical
`Alert` records (`force=True` on `delete_doc` skips the link check).
"""

from __future__ import annotations

import builtins
from typing import Any

import frappe

from infra_control.api import _serialize as ser
from infra_control.api import api, bool_param, enum_param, int_param, list_param, str_param
from infra_control.api._pagination import LIMIT_DEFAULT, LIMIT_MAX, page_by_name
from infra_control.core.enums import (
	RULE_KIND_FIELDS,
	AlertChannel,
	AlertRuleKind,
	MetricName,
	Operator,
	Severity,
)
from infra_control.core.errors import InvalidState, NotFound, ValidationError
from infra_control.core.permissions import INFRA_ADMIN

# Editable for every kind; the per-kind condition fields come from RULE_KIND_FIELDS.
_ALWAYS_EDITABLE = frozenset({"title", "severity", "channels", "enabled"})
_CONDITION_FIELDS = frozenset({"metric", "operator", "threshold", "for_minutes"})


def _channels(rule: str) -> builtins.list[str]:
	# Order by the child `idx` so the set comes back in the order it was entered (deterministic).
	return [
		str(c)
		for c in frappe.get_all(
			"Alert Rule Channel", filters={"parent": rule}, pluck="channel", order_by="idx asc"
		)
	]


def _rule_row(name: str) -> dict[str, Any]:
	rows = frappe.get_all("Alert Rule", filters={"name": name}, fields=ser.ALERT_RULE_FIELDS, limit=1)
	if not rows:
		raise NotFound("Alert Rule", name)
	return dict(rows[0])


def _serialized(name: str) -> dict[str, Any]:
	return ser.alert_rule(_rule_row(name), channels=_channels(name))


def _channel_list(value: Any) -> builtins.list[str]:
	out: builtins.list[str] = []
	for item in list_param("channels", value):
		channel = enum_param("channels", item, AlertChannel)
		if channel and channel not in out:
			out.append(channel)
	return out


def _number(name: str, value: Any) -> float:
	try:
		return float(value)
	except (TypeError, ValueError):
		raise ValidationError(f"{name} must be a number", {"field": name}) from None


@api()
def list(limit: Any = None, cursor: str | None = None) -> dict[str, Any]:
	page = page_by_name(
		"Alert Rule",
		filters={},
		fields=ser.ALERT_RULE_FIELDS,
		limit=int_param("limit", limit, default=LIMIT_DEFAULT, minimum=1, maximum=LIMIT_MAX),
		cursor=cursor,
		serialize=lambda r: r,
	)
	page["items"] = [ser.alert_rule(r, channels=_channels(r["name"])) for r in page["items"]]
	return page


@api()
def get(rule: str | None = None) -> dict[str, Any]:
	name = str_param("rule", rule, required=True)
	assert name is not None
	return _serialized(name)  # bare AlertRule, not an envelope (see contract)


@api(methods=("POST",), role=INFRA_ADMIN)
def create(
	title: str | None = None,
	kind: str | None = None,
	target_doctype: str | None = None,
	metric: str | None = None,
	operator: str | None = None,
	threshold: Any = None,
	for_minutes: Any = None,
	severity: str | None = None,
	channels: Any = None,
	enabled: Any = None,
) -> dict[str, Any]:
	if kind not in (None, "", str(AlertRuleKind.METRIC)):
		raise ValidationError("Only metric alert rules can be created", {"field": "kind"})
	if target_doctype not in (None, "", "Server"):
		raise ValidationError("target_doctype must be Server for metric rules", {"field": "target_doctype"})
	rule_title = str_param("title", title, required=True)
	metric_value = enum_param("metric", metric, MetricName)
	operator_value = enum_param("operator", operator, Operator)
	severity_value = enum_param("severity", severity, Severity)
	if not metric_value:
		raise ValidationError("metric is required", {"field": "metric"})
	if not operator_value:
		raise ValidationError("operator is required", {"field": "operator"})
	if not severity_value:
		raise ValidationError("severity is required", {"field": "severity"})
	if threshold in (None, ""):
		raise ValidationError("threshold is required", {"field": "threshold"})
	if for_minutes in (None, ""):
		raise ValidationError("for_minutes is required", {"field": "for_minutes"})
	if channels in (None, ""):
		raise ValidationError("channels is required", {"field": "channels"})
	doc: Any = frappe.get_doc(
		{
			"doctype": "Alert Rule",
			"title": rule_title,
			"kind": str(AlertRuleKind.METRIC),
			"target_doctype": "Server",
			"metric": metric_value,
			"operator": operator_value,
			"threshold": _number("threshold", threshold),
			"for_minutes": int_param("for_minutes", for_minutes, default=0, minimum=0, maximum=1440),
			"severity": severity_value,
			"enabled": 1 if bool_param("enabled", enabled, default=True) else 0,
			"builtin": 0,
		}
	)
	for channel in _channel_list(channels):
		doc.append("channels", {"channel": channel})
	doc.flags.ignore_permissions = True
	doc.insert()
	return {"rule": _serialized(doc.name)}


@api(methods=("POST",), role=INFRA_ADMIN)
def update(
	rule: str | None = None,
	title: str | None = None,
	metric: str | None = None,
	operator: str | None = None,
	threshold: Any = None,
	for_minutes: Any = None,
	severity: str | None = None,
	channels: Any = None,
	enabled: Any = None,
) -> dict[str, Any]:
	name = str_param("rule", rule, required=True)
	assert name is not None
	row = _rule_row(name)
	kind = AlertRuleKind(str(row.get("kind") or AlertRuleKind.METRIC))
	editable = _ALWAYS_EDITABLE | RULE_KIND_FIELDS[kind]
	candidates: dict[str, Any] = {
		"title": title,
		"metric": metric,
		"operator": operator,
		"threshold": threshold,
		"for_minutes": for_minutes,
		"severity": severity,
		"channels": channels,
		"enabled": enabled,
	}
	provided = {field for field, value in candidates.items() if value not in (None, "")}
	rejected = sorted((provided & _CONDITION_FIELDS) - editable)
	if rejected:
		raise ValidationError(
			f"{rejected[0]} cannot be edited for a {kind} rule", {"field": rejected[0], "kind": str(kind)}
		)
	doc: Any = frappe.get_doc("Alert Rule", name)
	if "title" in provided:
		doc.title = str_param("title", title, required=True)
	if "severity" in provided:
		doc.severity = enum_param("severity", severity, Severity)
	if "enabled" in provided:
		doc.enabled = 1 if bool_param("enabled", enabled, default=True) else 0
	if "metric" in provided:
		doc.metric = enum_param("metric", metric, MetricName)
	if "operator" in provided:
		doc.operator = enum_param("operator", operator, Operator)
	if "threshold" in provided:
		doc.threshold = _number("threshold", threshold)
	if "for_minutes" in provided:
		doc.for_minutes = int_param("for_minutes", for_minutes, default=0, minimum=0, maximum=1440)
	if "channels" in provided:
		doc.set("channels", [])
		for channel in _channel_list(channels):
			doc.append("channels", {"channel": channel})
	doc.flags.ignore_permissions = True
	doc.save()
	return {"rule": _serialized(name)}


@api(methods=("POST",), role=INFRA_ADMIN)
def delete(rule: str | None = None) -> dict[str, Any]:
	name = str_param("rule", rule, required=True)
	assert name is not None
	row = _rule_row(name)
	if row.get("builtin") or str(row.get("kind") or "") != str(AlertRuleKind.METRIC):
		raise InvalidState(f"Alert Rule {name} is built-in and cannot be deleted", {"name": name})
	# force=True skips the link check so the rule's historical alerts are kept, not cascade-deleted.
	frappe.delete_doc("Alert Rule", name, force=True, ignore_permissions=True)
	return {"rule": name, "deleted": True}
