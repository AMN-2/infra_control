"""Scheduled backups (A4.2): one `Backup Policy` per site decides when `site.backup` runs.

`run_due_policies()` is the hourly scheduler entry: every enabled policy whose `next_run` has
passed gets a `site.backup` job through the engine (audited, locked, visible like any job),
unless a job for that site is already queued or running. The time arithmetic is pure.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import frappe
from frappe.utils import get_datetime, now_datetime

from infra_control.core.enums import BackupFrequency
from infra_control.core.errors import InfraError
from infra_control.job_engine import engine

PLAYBOOK = "site.backup"
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
FREQUENCIES = tuple(str(f) for f in BackupFrequency)


def next_run_after(frequency: str, hour: int, weekday: str, after: datetime) -> datetime:
	"""Pure: the first run strictly after `after` (naive system time, hours on the dot)."""
	base = after.replace(minute=0, second=0, microsecond=0)
	if frequency == "hourly":
		return base + timedelta(hours=1)
	hour = min(23, max(0, int(hour)))
	candidate = base.replace(hour=hour)
	if frequency == "daily":
		return candidate if candidate > after else candidate + timedelta(days=1)
	if frequency == "weekly":
		target = WEEKDAYS.index(weekday) if weekday in WEEKDAYS else 6
		delta = (target - candidate.weekday()) % 7
		candidate = candidate + timedelta(days=delta)
		return candidate if candidate > after else candidate + timedelta(days=7)
	raise ValueError(f"unknown frequency {frequency}")


def is_due(policy: dict[str, Any], now: datetime) -> bool:
	if not policy.get("enabled"):
		return False
	nxt = get_datetime(policy.get("next_run")) if policy.get("next_run") else None
	return nxt is None or nxt <= now


def _site_busy(site: str) -> bool:
	return bool(
		frappe.get_all(
			"Infra Job",
			filters={"target_doctype": "Site", "target_name": site, "status": ["in", ["Queued", "Running"]]},
			limit=1,
		)
	)


def run_due_policies() -> dict[str, int]:
	"""Hourly: start the backups that are due. Returns counts for the scheduler log."""
	now = now_datetime()
	started = skipped = failed = 0
	for row in frappe.get_all(
		"Backup Policy",
		filters={"enabled": 1},
		fields=["name", "site", "frequency", "hour", "weekday", "with_files", "next_run", "enabled"],
	):
		if not is_due(row, now):
			continue
		if _site_busy(str(row["site"])):
			skipped += 1
			continue
		nxt = next_run_after(str(row["frequency"]), int(row["hour"] or 0), str(row["weekday"] or "sun"), now)
		try:
			job = engine.create_job(
				PLAYBOOK,
				"Site",
				str(row["site"]),
				{"with_files": bool(row.get("with_files"))},
				user=engine.SCHEDULER_USER,
			)
		except InfraError as exc:
			failed += 1
			frappe.log_error(title=f"scheduled backup not started for {row['site']}", message=str(exc))
			frappe.db.set_value("Backup Policy", row["name"], {"next_run": nxt})
			continue
		started += 1
		frappe.db.set_value(
			"Backup Policy", row["name"], {"last_run": now, "last_job": str(job.name), "next_run": nxt}
		)
	frappe.db.commit()
	return {"started": started, "skipped_busy": skipped, "failed": failed}
