"""A3.1: the metric collector's decision logic (status, heartbeat, stale -> Down) with the fake."""

from __future__ import annotations

from typing import Any

import pytest
from fake_frappe import FakeFrappe

from infra_control.job_engine import realtime
from infra_control.monitoring import collector
from infra_control.providers import registry


class _MetricsProvider:
	"""A provider that returns scripted metrics; the collector reaches it through the registry."""

	name = "digitalocean"
	metrics: dict[str, Any] = {"cpu": 23.5, "ram": 61.2, "disk": 54.0, "load1": 0.8, "queue_backlog": 3}

	def __init__(self, config: Any = None) -> None:
		self.config = config

	def get_metrics(self, server: str) -> dict[str, Any]:
		return dict(self.metrics)


@pytest.fixture
def ff(monkeypatch: pytest.MonkeyPatch) -> FakeFrappe:
	f = FakeFrappe()
	for module in (collector, realtime, registry):
		monkeypatch.setattr(module, "frappe", f)
	monkeypatch.setattr(collector, "now_datetime", f.now)
	monkeypatch.setattr(collector, "get_system_timezone", lambda: "UTC")
	monkeypatch.setattr(collector, "get_datetime", lambda v: v if hasattr(v, "year") else f.now())
	monkeypatch.setattr(
		collector, "add_to_date", lambda ts, minutes=0: ts + __import__("datetime").timedelta(minutes=minutes)
	)
	monkeypatch.setattr(registry, "get_provider", lambda account: _MetricsProvider())
	f.add("Server", name="SRV-0001", provider_account="DO-STAGING", provider="digitalocean", status="Active")
	return f


def test_collect_one_writes_a_metric_updates_heartbeat_and_emits(ff: FakeFrappe) -> None:
	assert collector.collect_one("SRV-0001", "DO-STAGING") is True
	metrics = list(ff.store.get("Server Metric", {}).values())
	assert len(metrics) == 1
	m = metrics[0]
	assert (m.get("server"), m.get("resolution"), m.get("cpu"), m.get("queue_backlog")) == (
		"SRV-0001",
		"1m",
		23.5,
		3,
	)
	srv = ff.store["Server"]["SRV-0001"]
	assert srv.get("last_heartbeat") is not None and srv.get("status") == "Active"
	hb = [e for e in ff.events if e[0] == "infra:server.heartbeat"][-1][1]
	assert hb["server"] == "SRV-0001" and hb["cpu"] == 23.5 and hb["status"] == "Active"


def test_a_critically_high_resource_degrades_the_server(
	ff: FakeFrappe, monkeypatch: pytest.MonkeyPatch
) -> None:
	monkeypatch.setattr(
		_MetricsProvider,
		"metrics",
		{"cpu": 12.0, "ram": 95.0, "disk": 40.0, "load1": 1.0, "queue_backlog": 0},
	)
	collector.collect_one("SRV-0001", "DO-STAGING")
	assert ff.store["Server"]["SRV-0001"].get("status") == "Degraded"


def test_a_provider_reporting_nothing_is_not_an_error_and_writes_no_metric(
	ff: FakeFrappe, monkeypatch: pytest.MonkeyPatch
) -> None:
	monkeypatch.setattr(
		_MetricsProvider,
		"metrics",
		{"cpu": None, "ram": None, "disk": None, "load1": None, "queue_backlog": 0},
	)
	assert collector.collect_one("SRV-0001", "DO-STAGING") is False
	assert "Server Metric" not in ff.store or ff.store["Server Metric"] == {}


def test_a_reachable_server_recovers_from_down(ff: FakeFrappe) -> None:
	ff.db.set_value("Server", "SRV-0001", "status", "Down")
	collector.collect_one("SRV-0001", "DO-STAGING")
	assert ff.store["Server"]["SRV-0001"].get("status") == "Active"


def test_collect_all_marks_a_stale_server_down(ff: FakeFrappe) -> None:
	from datetime import timedelta

	# A server not heard from for longer than the timeout, with metrics now unavailable.
	old = ff.now() - timedelta(minutes=10)
	ff.db.set_value("Server", "SRV-0001", {"last_heartbeat": old, "status": "Active"})

	class _Dead(_MetricsProvider):
		metrics = {"cpu": None, "ram": None, "disk": None, "load1": None, "queue_backlog": 0}

	import infra_control.monitoring.collector as c

	c.registry.get_provider = lambda account: _Dead()  # type: ignore[attr-defined]
	result = collector.collect_all()
	assert result["downed"] == 1
	assert ff.store["Server"]["SRV-0001"].get("status") == "Down"


def test_tz_aware_provider_timestamp_is_stored_naive_and_emitted_as_utc(
	ff: FakeFrappe, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""DigitalOcean returns UTC-aware timestamps; MariaDB rejects an offset (Phase 3 live run)."""
	from datetime import UTC, datetime

	monkeypatch.setattr(collector, "get_system_timezone", lambda: "Asia/Baghdad")
	aware = datetime(2026, 10, 8, 20, 16, 16, tzinfo=UTC)
	provider = _MetricsProvider()
	provider.metrics = {"cpu": 1.0, "ts": aware}
	monkeypatch.setattr(registry, "get_provider", lambda account: provider)
	assert collector.collect_one("SRV-0001", "DO-STAGING") is True
	stored = next(iter(ff.store["Server Metric"].values())).get("ts")
	assert stored.tzinfo is None and stored == datetime(2026, 10, 8, 23, 16, 16)
	hb = [e for e in ff.events if e[0] == "infra:server.heartbeat"][-1][1]
	assert hb["ts"] == "2026-10-08T20:16:16Z"
