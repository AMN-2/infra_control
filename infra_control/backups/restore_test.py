"""Monthly restore test (A4.2, security requirement 10): every site with a backup policy gets
its newest database backup restored into a throwaway site through `site.restore_test`.
`days_since_last_ok()` feeds the security posture: more than 35 days without a successful
test is a finding."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import frappe
from frappe.utils import get_datetime, now_datetime

from infra_control.core.errors import InfraError
from infra_control.job_engine import engine

PLAYBOOK = "site.restore_test"
MAX_DAYS_WITHOUT_OK = 35


def latest_db_backup(site: str) -> str | None:
	rows = frappe.get_all(
		"Backup",
		filters={"site": site, "kind": "db"},
		fields=["name"],
		order_by="created_at desc, creation desc",
		limit=1,
	)
	return str(rows[0]["name"]) if rows else None


def run_monthly() -> dict[str, int]:
	"""Scheduler (first day of the month): one restore test per site with a policy."""
	started = skipped = failed = 0
	for policy in frappe.get_all("Backup Policy", filters={"enabled": 1}, fields=["site"]):
		backup = latest_db_backup(str(policy["site"]))
		if not backup:
			skipped += 1
			continue
		try:
			engine.create_job(
				PLAYBOOK, "Site", str(policy["site"]), {"backup": backup}, user=engine.SCHEDULER_USER
			)
			started += 1
		except InfraError as exc:
			failed += 1
			frappe.log_error(title=f"restore test not started for {policy['site']}", message=str(exc))
	frappe.db.commit()
	return {"started": started, "skipped_no_backup": skipped, "failed": failed}


def days_since_last_ok(now: datetime | None = None) -> int | None:
	"""Days since the newest successful restore test anywhere, or None when there was none."""
	rows = frappe.get_all(
		"Backup",
		filters={"restore_test_result": "ok"},
		fields=["last_restore_test"],
		order_by="last_restore_test desc",
		limit=1,
	)
	if not rows or not rows[0].get("last_restore_test"):
		return None
	last: Any = get_datetime(rows[0]["last_restore_test"])
	return int(((now or now_datetime()) - last).total_seconds() // 86400)
