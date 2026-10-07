"""DigitalOcean vocabulary → unified enums. Nothing outside this package may see DO strings.

Droplet `status`: new | active | off | archive.
Action `status`: in-progress | completed | errored.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from infra_control.core.enums import ServerRole, ServerStatus
from infra_control.providers.base import OpState

MANAGED_TAG = "infra-control"
"""Every droplet this controller manages carries this tag; `sync_inventory` lists by it."""
ROLE_TAG_PREFIX = "role:"
STAGING_TAG = "staging"

_DROPLET_STATUS: dict[str, ServerStatus] = {
	"new": ServerStatus.PROVISIONING,
	"active": ServerStatus.ACTIVE,
	"off": ServerStatus.DOWN,
	"archive": ServerStatus.ARCHIVED,
}
_ACTION_STATUS: dict[str, OpState] = {
	"in-progress": OpState.RUNNING,
	"completed": OpState.SUCCESS,
	"errored": OpState.FAILED,
}


def server_status(droplet_status: str) -> ServerStatus:
	"""Unknown strings are reported as Degraded rather than guessed healthy."""
	return _DROPLET_STATUS.get(droplet_status, ServerStatus.DEGRADED)


def action_state(action_status: str) -> OpState:
	return _ACTION_STATUS.get(action_status, OpState.RUNNING)


def parse_time(value: Any) -> datetime | None:
	"""DO timestamps are ISO 8601 with `Z`; returns an aware UTC datetime or None."""
	if not isinstance(value, str) or not value:
		return None
	try:
		return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
	except ValueError:
		return None


def public_ip(droplet: dict[str, Any], kind: str = "public") -> str | None:
	networks = droplet.get("networks") or {}
	v4 = networks.get("v4") if isinstance(networks, dict) else None
	if not isinstance(v4, list):
		return None
	for net in v4:
		if isinstance(net, dict) and net.get("type") == kind and isinstance(net.get("ip_address"), str):
			return str(net["ip_address"])
	return None


def role_from_tags(tags: list[str]) -> ServerRole:
	for tag in tags:
		if tag.startswith(ROLE_TAG_PREFIX):
			try:
				return ServerRole(tag[len(ROLE_TAG_PREFIX) :])
			except ValueError:
				continue
	return ServerRole.ALL


def tags_for(role: ServerRole | str, extra: list[str] | None = None, *, staging: bool) -> list[str]:
	"""Tags a provisioned droplet gets: the managed marker, its role, staging, then the user's."""
	tags = [MANAGED_TAG, f"{ROLE_TAG_PREFIX}{ServerRole(role)}"]
	if staging:
		tags.append(STAGING_TAG)
	for t in extra or []:
		if t and t not in tags:
			tags.append(t)
	return tags


def normalize_droplet(droplet: dict[str, Any]) -> dict[str, Any]:
	"""A droplet as the inventory sync and the Server DocType see it (unified fields only)."""
	tags = [str(t) for t in (droplet.get("tags") or []) if isinstance(t, str)]
	region = droplet.get("region") or {}
	size = droplet.get("size") or {}
	return {
		"provider_ref": str(droplet.get("id", "")),
		"hostname": str(droplet.get("name", "")),
		"status": server_status(str(droplet.get("status", ""))),
		"public_ip": public_ip(droplet, "public"),
		"private_ip": public_ip(droplet, "private"),
		"region": str(region.get("slug", "")) if isinstance(region, dict) else "",
		"size": str(size.get("slug") or droplet.get("size_slug") or "")
		if isinstance(size, dict)
		else str(droplet.get("size_slug", "")),
		"role": role_from_tags(tags),
		"tags": [t for t in tags if t != MANAGED_TAG and not t.startswith(ROLE_TAG_PREFIX)],
		"created_at": parse_time(droplet.get("created_at")),
	}


def latest_value(series_body: dict[str, Any]) -> float | None:
	"""Last sample of a Prometheus-style `/monitoring/metrics/droplet/*` response.

	Shape: `{"status": "success", "data": {"result": [{"metric": {...}, "values": [[ts, "v"], ...]}]}}`.
	For cpu the result has one series per mode; the caller sums what it needs via `series_by()`.
	"""
	series = series_by(series_body)
	if not series:
		return None
	values = next(iter(series.values()))
	return values[-1][1] if values else None


def series_by(series_body: dict[str, Any], label: str = "mode") -> dict[str, list[tuple[float, float]]]:
	"""`{label_value: [(ts, value), ...]}`; unlabelled series land under `""`."""
	data = series_body.get("data") or {}
	result = data.get("result") if isinstance(data, dict) else None
	out: dict[str, list[tuple[float, float]]] = {}
	if not isinstance(result, list):
		return out
	for entry in result:
		if not isinstance(entry, dict):
			continue
		metric = entry.get("metric") or {}
		key = str(metric.get(label, "")) if isinstance(metric, dict) else ""
		points: list[tuple[float, float]] = []
		for pair in entry.get("values") or []:
			if isinstance(pair, list) and len(pair) == 2:
				try:
					points.append((float(pair[0]), float(pair[1])))
				except (TypeError, ValueError):
					continue
		out[key] = points
	return out


def cpu_percent(cpu_body: dict[str, Any]) -> float | None:
	"""DO reports cumulative CPU seconds per mode. Utilisation over the last interval is
	`1 - Δidle / Δtotal` using the last two samples."""
	series = series_by(cpu_body, "mode")
	if not series or any(len(v) < 2 for v in series.values()):
		return None
	total_delta = 0.0
	idle_delta = 0.0
	for mode, points in series.items():
		delta = points[-1][1] - points[-2][1]
		total_delta += delta
		if mode == "idle":
			idle_delta += delta
	if total_delta <= 0:
		return None
	return round(max(0.0, min(100.0, (1 - idle_delta / total_delta) * 100)), 1)


def percent_used(total: float | None, free: float | None) -> float | None:
	if total is None or free is None or total <= 0:
		return None
	return round(max(0.0, min(100.0, (1 - free / total) * 100)), 1)
