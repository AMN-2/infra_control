"""metrics.series: a time series for one metric of one server (contracts/openapi.yaml)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import get_datetime

from infra_control.api import api, enum_param, str_param
from infra_control.core.enums import MetricName, Resolution
from infra_control.core.errors import NotFound, ValidationError
from infra_control.monitoring.aggregate import MAX_SERIES_POINTS, choose_resolution


@api()
def series(
	server: str | None = None,
	metric: str | None = None,
	**params: Any,
) -> dict[str, Any]:
	name = str_param("server", server, required=True)
	metric_name = enum_param("metric", metric, [str(m) for m in MetricName])
	frm_raw = str_param("from", params.get("from"), required=True)
	to_raw = str_param("to", params.get("to"), required=True)
	resolution = enum_param("resolution", params.get("resolution"), [str(r) for r in Resolution])
	assert name and metric_name and frm_raw and to_raw

	if not frappe.db.exists("Server", name):
		raise NotFound("Server", name)
	frm = get_datetime(frm_raw)
	to = get_datetime(to_raw)
	if to <= frm:
		raise ValidationError("`to` must be after `from`", {"field": "to"})

	chosen = choose_resolution(frm, to, Resolution(resolution) if resolution else None)
	rows = frappe.get_all(
		"Server Metric",
		filters={"server": name, "resolution": str(chosen), "ts": ["between", [frm, to]]},
		fields=["ts", metric_name],
		order_by="ts asc",
		limit=MAX_SERIES_POINTS,
	)
	points = [{"ts": _iso(r["ts"]), "value": _value(r.get(metric_name))} for r in rows]
	return {
		"server": name,
		"metric": metric_name,
		"resolution": str(chosen),
		"from": _iso(frm),
		"to": _iso(to),
		"points": points,
	}


def _iso(ts: Any) -> str:
	return str(get_datetime(ts).strftime("%Y-%m-%dT%H:%M:%SZ"))


def _value(value: Any) -> float | None:
	return None if value is None else float(value)
