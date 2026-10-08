"""Metric rollups and retention (A3.1, plan 9.4).

- Hourly: fold 1m samples of the past hours into 1h samples. Daily: fold 1h into 1d.
- Retention: 1m for 7 days, 1h for 90 days, 1d for 2 years.

A rollup is idempotent: it replaces the target bucket rows it recomputes, so a re-run or an
overlap never double-counts. The aggregation itself is `aggregate.rollup` (pure).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime

from infra_control.core.enums import Resolution
from infra_control.monitoring import aggregate
from infra_control.monitoring.aggregate import ROLLUP_SOURCE, Sample

# How far back each rollup recomputes on every run (cheap, covers late-arriving samples).
ROLLUP_LOOKBACK_HOURS: dict[Resolution, int] = {Resolution.ONE_HOUR: 3, Resolution.ONE_DAY: 48}


def run_rollups() -> dict[str, int]:
	"""Scheduler entry point: hourly produces 1h, daily is folded in on the same pass when due."""
	produced = {str(Resolution.ONE_HOUR): rollup_resolution(Resolution.ONE_HOUR)}
	produced[str(Resolution.ONE_DAY)] = rollup_resolution(Resolution.ONE_DAY)
	frappe.db.commit()
	return produced


def rollup_resolution(target: Resolution) -> int:
	source = ROLLUP_SOURCE[target]
	since = add_to_date(now_datetime(), hours=-ROLLUP_LOOKBACK_HOURS[target])
	rows = frappe.get_all(
		"Server Metric",
		filters={"resolution": str(source), "ts": [">=", since]},
		fields=["server", "ts", "cpu", "ram", "disk", "load1", "queue_backlog"],
		order_by="ts asc",
	)
	by_server: dict[str, list[Sample]] = {}
	for r in rows:
		by_server.setdefault(str(r["server"]), []).append(_sample(r))

	written = 0
	for server, samples in by_server.items():
		for bucket in aggregate.rollup(samples, target):
			_upsert(server, target, bucket)
			written += 1
	return written


def purge_old_metrics() -> dict[str, int]:
	"""Delete metrics past their retention. Scheduler entry point (daily)."""
	now = now_datetime()
	deleted: dict[str, int] = {}
	for res in (Resolution.ONE_MINUTE, Resolution.ONE_HOUR, Resolution.ONE_DAY):
		cutoff = aggregate.retention_cutoff(res, get_datetime(now).replace(tzinfo=None))
		names = frappe.get_all(
			"Server Metric", filters={"resolution": str(res), "ts": ["<", cutoff]}, pluck="name"
		)
		for name in names:
			frappe.delete_doc("Server Metric", name, ignore_permissions=True, force=True)
		deleted[str(res)] = len(names)
	frappe.db.commit()
	return deleted


def _sample(row: dict[str, Any]) -> Sample:
	return Sample(
		ts=get_datetime(row["ts"]).replace(tzinfo=UTC)
		if get_datetime(row["ts"]).tzinfo is None
		else get_datetime(row["ts"]),
		cpu=row.get("cpu"),
		ram=row.get("ram"),
		disk=row.get("disk"),
		load1=row.get("load1"),
		queue_backlog=row.get("queue_backlog"),
	)


def _upsert(server: str, resolution: Resolution, bucket: Sample) -> None:
	ts_naive = _naive(bucket.ts)
	existing = frappe.db.get_value(
		"Server Metric", {"server": server, "resolution": str(resolution), "ts": ts_naive}, "name"
	)
	values = {
		"cpu": bucket.cpu,
		"ram": bucket.ram,
		"disk": bucket.disk,
		"load1": bucket.load1,
		"queue_backlog": bucket.queue_backlog or 0,
	}
	if existing:
		frappe.db.set_value("Server Metric", existing, values)
		return
	frappe.get_doc(
		{
			"doctype": "Server Metric",
			"server": server,
			"resolution": str(resolution),
			"ts": ts_naive,
			**values,
		}
	).insert(ignore_permissions=True)


def _naive(ts: datetime) -> datetime:
	return ts.replace(tzinfo=None) if ts.tzinfo else ts
