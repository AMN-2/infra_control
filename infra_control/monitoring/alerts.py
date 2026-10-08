"""Alert engine (A3.2, plan 9.4): every minute, evaluate each enabled rule against its targets,
open an Alert when a condition holds, resolve it when it clears, and notify once on each
transition.

One firing Alert per (rule, target). While it is firing nothing re-notifies; a `fire` verdict on
an already-firing alert only refreshes its value. A `clear` verdict resolves the alert and
notifies once. Acknowledged alerts stay acknowledged (a human owns them) until they resolve.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import frappe
from frappe.utils import get_datetime, now_datetime

from infra_control.core.enums import AlertRuleKind, AlertStatus
from infra_control.job_engine import realtime
from infra_control.monitoring import notify, rules
from infra_control.monitoring.rules import (
	CLEAR,
	FIRE,
	HeartbeatInput,
	MetricInput,
	SslInput,
	Verdict,
)

OPEN_STATUSES = (AlertStatus.FIRING, AlertStatus.ACKNOWLEDGED)


def evaluate_rules() -> dict[str, int]:
	"""Scheduler entry point."""
	now = now_datetime()
	fired = 0
	resolved = 0
	for rule in frappe.get_all(
		"Alert Rule",
		filters={"enabled": 1},
		fields=[
			"name",
			"title",
			"kind",
			"severity",
			"target_doctype",
			"metric",
			"operator",
			"threshold",
			"for_minutes",
		],
	):
		kind = AlertRuleKind(str(rule["kind"]))
		if kind not in rules.KIND_EVALUATORS:
			continue  # drift and contract are driven by their own producers
		for target in _targets(rule):
			verdict = _evaluate(kind, rule, target, now)
			if verdict.state == FIRE:
				if _open_alert(str(rule["name"]), target) is None:
					_fire(rule, target, verdict)
					fired += 1
				else:
					_refresh(str(rule["name"]), target, verdict)
			elif verdict.state == CLEAR:
				if _resolve(str(rule["name"]), target, verdict):
					resolved += 1
	frappe.db.commit()
	return {"fired": fired, "resolved": resolved}


def _targets(rule: dict[str, Any]) -> list[str]:
	target_doctype = str(rule["target_doctype"])
	if target_doctype == "Server":
		rows = frappe.get_all("Server", filters={"status": ["!=", "Archived"]}, pluck="name")
	elif target_doctype == "Site":
		rows = frappe.get_all("Site", filters={"status": ["not in", ["Archived"]]}, pluck="name")
	else:
		rows = frappe.get_all("Provider Account", filters={"enabled": 1}, pluck="name")
	return [str(r) for r in rows]


def _evaluate(kind: AlertRuleKind, rule: dict[str, Any], target: str, now: Any) -> Verdict:
	if kind is AlertRuleKind.METRIC:
		since = now - timedelta(minutes=max(int(rule.get("for_minutes") or 1), 1))
		rows = frappe.get_all(
			"Server Metric",
			filters={"server": target, "resolution": "1m", "ts": [">=", since]},
			fields=["ts", str(rule["metric"])],
			order_by="ts asc",
		)
		samples = [(get_datetime(r["ts"]), _num(r.get(str(rule["metric"])))) for r in rows]
		return rules.evaluate_metric(rule, MetricInput(target, samples), now)
	if kind is AlertRuleKind.HEARTBEAT:
		row = frappe.db.get_value("Server", target, ["last_heartbeat", "status"], as_dict=True)
		hb = get_datetime(row["last_heartbeat"]) if row and row.get("last_heartbeat") else None
		return rules.evaluate_heartbeat(
			rule, HeartbeatInput(target, hb, str(row["status"]) if row else ""), now
		)
	expiry = frappe.db.get_value("Site", target, "ssl_expiry")
	return rules.evaluate_ssl(rule, SslInput(target, get_datetime(expiry) if expiry else None), now)


def _open_alert(rule: str, target: str) -> str | None:
	name = frappe.db.get_value(
		"Alert",
		{"rule": rule, "target_name": target, "status": ["in", [str(s) for s in OPEN_STATUSES]]},
		"name",
	)
	return str(name) if name else None


def _fire(rule: dict[str, Any], target: str, verdict: Verdict) -> None:
	doc: Any = frappe.get_doc(
		{
			"doctype": "Alert",
			"rule": rule["name"],
			"rule_title": rule.get("title"),
			"kind": str(rule["kind"]),
			"severity": str(rule["severity"]),
			"status": str(AlertStatus.FIRING),
			"target_doctype": str(rule["target_doctype"]),
			"target_name": target,
			"metric": str(rule.get("metric") or ""),
			"value": verdict.value,
			"message": verdict.message,
			"fired_at": now_datetime(),
		}
	)
	doc.insert(ignore_permissions=True)
	realtime.emit(
		*realtime.alert_fired(
			str(doc.name), str(rule["name"]), str(rule["target_doctype"]), target, str(rule["severity"])
		)
	)
	notify.notify(_alert_dict(doc), _channels(str(rule["name"])), AlertStatus.FIRING)


def _refresh(rule: str, target: str, verdict: Verdict) -> None:
	name = _open_alert(rule, target)
	if name and verdict.value is not None:
		frappe.db.set_value("Alert", name, {"value": verdict.value, "message": verdict.message})


def _resolve(rule: str, target: str, verdict: Verdict) -> bool:
	name = _open_alert(rule, target)
	if not name:
		return False
	alert: Any = frappe.get_doc("Alert", name)
	alert.status = str(AlertStatus.RESOLVED)
	alert.resolved_at = now_datetime()
	if verdict.message:
		alert.message = verdict.message
	alert.save(ignore_permissions=True)
	realtime.emit(
		*realtime.alert_resolved(name, rule, str(alert.target_doctype), target, str(alert.severity))
	)
	notify.notify(_alert_dict(alert), _channels(rule), AlertStatus.RESOLVED)
	return True


def _channels(rule: str) -> list[str]:
	return [str(c) for c in frappe.get_all("Alert Rule Channel", filters={"parent": rule}, pluck="channel")]


def _alert_dict(doc: Any) -> dict[str, Any]:
	return {
		"rule": doc.rule,
		"rule_title": doc.rule_title,
		"severity": doc.severity,
		"target_doctype": doc.target_doctype,
		"target_name": doc.target_name,
		"message": doc.message,
	}


def _num(value: Any) -> float | None:
	try:
		return None if value is None else float(value)
	except (TypeError, ValueError):
		return None


# --- drift alerts (fed by inventory.sync, A2.5/A3.3) -------------------------------------------
def sync_drift_alerts(account: str, findings: list[dict[str, Any]]) -> dict[str, int]:
	"""Open a drift Alert per account when inventory.sync reports findings, resolve it when there
	are none. One Alert per account for the built-in drift rule, so the UI shows a single row."""
	rule = frappe.db.get_value(
		"Alert Rule",
		{"kind": str(AlertRuleKind.DRIFT), "builtin": 1},
		["name", "title", "severity"],
		as_dict=True,
	)
	if not rule:
		return {"fired": 0, "resolved": 0}
	open_name = _open_alert(str(rule["name"]), account)
	if findings:
		summary = "; ".join(f"{f['kind']}: {f['doctype']} {f['name']}" for f in findings[:5])
		if len(findings) > 5:
			summary += f" (+{len(findings) - 5} more)"
		if open_name:
			frappe.db.set_value("Alert", open_name, {"value": len(findings), "message": summary})
			return {"fired": 0, "resolved": 0}
		rule_spec = {
			**rule,
			"kind": str(AlertRuleKind.DRIFT),
			"target_doctype": "Provider Account",
			"metric": "",
		}
		_fire(rule_spec, account, Verdict(FIRE, value=float(len(findings)), message=summary))
		return {"fired": 1, "resolved": 0}
	# no findings: resolve any open drift alert
	if open_name and _resolve(
		str(rule["name"]), account, Verdict(CLEAR, message="inventory matches the provider")
	):
		return {"fired": 0, "resolved": 1}
	return {"fired": 0, "resolved": 0}
