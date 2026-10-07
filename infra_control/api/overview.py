"""overview.summary: counts by status, running jobs, unresolved alerts."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import add_to_date, now_datetime

from infra_control.api import _serialize as ser
from infra_control.api import api
from infra_control.api._inventory_helpers import count_by
from infra_control.core.enums import AlertStatus, JobStatus, ServerStatus, Severity, SiteStatus


def _counts(doctype: str, enum: Any) -> dict[str, Any]:
	by = count_by(doctype, "status")
	by_status = {str(v): by.get(str(v), 0) for v in enum}
	return {"total": sum(by_status.values()), "by_status": by_status}


@api()
def summary() -> dict[str, Any]:
	since = add_to_date(now_datetime(), hours=-24)
	running = frappe.get_all(
		"Infra Job", filters={"status": JobStatus.RUNNING}, fields=ser.JOB_FIELDS, order_by="creation desc"
	)
	unresolved = frappe.get_all(
		"Alert",
		filters={"status": ["in", [AlertStatus.FIRING, AlertStatus.ACKNOWLEDGED]]},
		fields=["severity"],
	)
	recent = frappe.get_all(
		"Alert",
		filters={"status": ["in", [AlertStatus.FIRING, AlertStatus.ACKNOWLEDGED]]},
		fields=ser.ALERT_FIELDS,
		order_by="fired_at desc",
		limit=10,
	)
	return {
		"servers": _counts("Server", ServerStatus),
		"sites": _counts("Site", SiteStatus),
		"jobs": {
			"queued": frappe.db.count("Infra Job", {"status": JobStatus.QUEUED}),
			"running": len(running),
			"success_24h": frappe.db.count(
				"Infra Job", {"status": JobStatus.SUCCESS, "ended_at": [">=", since]}
			),
			"failed_24h": frappe.db.count(
				"Infra Job", {"status": JobStatus.FAILED, "ended_at": [">=", since]}
			),
		},
		"alerts": {
			"unresolved": len(unresolved),
			**{str(s): sum(1 for a in unresolved if a["severity"] == s) for s in Severity},
		},
		"running_jobs": [ser.job(j) for j in running],
		"recent_alerts": [ser.alert(a) for a in recent],
		"generated_at": ser.iso_utc(now_datetime()) or "",
	}
