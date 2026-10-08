"""Metric collector (A3.1, plan 9.4): every minute, read each managed server's metrics through
the provider layer, store a 1m `Server Metric`, update the server's heartbeat and status, and
emit `infra:server.heartbeat`.

Monitoring never calls DigitalOcean, Press or SSH directly (plan 3): metrics come from
`Provider.get_metrics`, which is capability-gated. A server the provider cannot report on, or
whose last heartbeat is older than the timeout, is marked `Down` (the alert engine, A3.2, turns
that into a notification). A collection failure for one server never stops the others.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import add_to_date, get_datetime, get_system_timezone, now_datetime

from infra_control.core.enums import Capability, ServerStatus
from infra_control.job_engine import realtime
from infra_control.providers import registry

HEARTBEAT_TIMEOUT_MINUTES = 3
"""No successful heartbeat for this long (plan 9.4) marks a server Down."""
ACTIVE_STATUSES = (ServerStatus.ACTIVE, ServerStatus.DEGRADED, ServerStatus.PROVISIONING)


def collect_all() -> dict[str, int]:
	"""Scheduler entry point. Returns counts for the log."""
	collected = 0
	failed = 0
	downed = 0
	servers = frappe.get_all(
		"Server",
		filters={"status": ["in", [str(s) for s in ACTIVE_STATUSES]]},
		fields=["name", "provider_account", "provider", "last_heartbeat", "status"],
	)
	for srv in servers:
		caps = registry.capabilities_for(str(srv["provider"]))
		if Capability.METRICS not in caps:
			continue
		try:
			if collect_one(str(srv["name"]), str(srv["provider_account"])):
				collected += 1
			else:
				failed += 1
		except Exception:  # one server's failure must not stop the sweep
			failed += 1
			frappe.log_error(
				title=f"metric collection failed for {srv['name']}", message=frappe.get_traceback()
			)
		if _is_stale(srv.get("last_heartbeat")) and str(srv["status"]) != ServerStatus.DOWN:
			_mark_down(str(srv["name"]))
			downed += 1
	frappe.db.commit()
	return {"collected": collected, "failed": failed, "downed": downed}


def collect_one(server: str, account: str) -> bool:
	"""Read and store one server's metrics. Returns False when the provider reported nothing."""
	provider = registry.get_provider(account)
	metrics = provider.get_metrics(server)
	if not isinstance(metrics, dict) or metrics.get("cpu") is None:
		return False
	ts = _db_datetime(get_datetime(metrics.get("ts"))) if metrics.get("ts") else now_datetime()
	cpu = _num(metrics.get("cpu"))
	ram = _num(metrics.get("ram"))
	disk = _num(metrics.get("disk"))
	frappe.get_doc(
		{
			"doctype": "Server Metric",
			"server": server,
			"ts": ts,
			"resolution": "1m",
			"cpu": cpu,
			"ram": ram,
			"disk": disk,
			"load1": _num(metrics.get("load1")),
			"queue_backlog": int(metrics.get("queue_backlog") or 0),
		}
	).insert(ignore_permissions=True)

	status = _status_from(server, cpu, ram, disk)
	frappe.db.set_value("Server", server, {"last_heartbeat": ts, "status": status})
	realtime.emit(*realtime.server_heartbeat(server, status, cpu or 0.0, ram or 0.0, disk or 0.0, _iso(ts)))
	return True


def _status_from(server: str, cpu: float | None, ram: float | None, disk: float | None) -> str:
	"""A reachable server is Active, or Degraded when a resource is critically high. A collector
	run that reaches the server never leaves it Down; it recovers the status."""
	worst = (
		max(v for v in (cpu, ram, disk) if v is not None)
		if any(v is not None for v in (cpu, ram, disk))
		else 0.0
	)
	current = frappe.db.get_value("Server", server, "status")
	if current == ServerStatus.PROVISIONING:
		return str(ServerStatus.PROVISIONING)
	return str(ServerStatus.DEGRADED if worst >= 90 else ServerStatus.ACTIVE)


def _is_stale(last_heartbeat: Any) -> bool:
	if not last_heartbeat:
		return False  # never heard from yet (freshly provisioned): not a timeout
	cutoff = add_to_date(now_datetime(), minutes=-HEARTBEAT_TIMEOUT_MINUTES)
	return bool(get_datetime(last_heartbeat) < get_datetime(cutoff))


def _mark_down(server: str) -> None:
	frappe.db.set_value("Server", server, "status", str(ServerStatus.DOWN))
	realtime.emit(*realtime.inventory_changed("Server", server, "updated"))


def _num(value: Any) -> float | None:
	try:
		return None if value is None else round(float(value), 2)
	except (TypeError, ValueError):
		return None


def _db_datetime(value: datetime | None) -> datetime | None:
	"""Adapters return tz-aware (UTC) timestamps; Frappe stores naive system-timezone datetimes
	and MariaDB rejects an offset (the Phase 1 gate bug, fixed for job steps in #17)."""
	if value is None or value.tzinfo is None:
		return value
	return value.astimezone(ZoneInfo(get_system_timezone())).replace(tzinfo=None)


def _iso(ts: Any) -> str:
	"""Naive system-timezone datetime -> RFC 3339 UTC with `Z` (the realtime contract)."""
	dt: datetime = get_datetime(ts)
	if dt.tzinfo is None:
		dt = dt.replace(tzinfo=ZoneInfo(get_system_timezone()))
	return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
