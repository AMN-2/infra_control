"""A3.2: the alert engine's lifecycle (fire once, dedup, resolve once, drift) with the fake."""

from __future__ import annotations

from datetime import timedelta

import pytest
from fake_frappe import FakeFrappe

from infra_control.monitoring import alerts, rules


@pytest.fixture
def ff(monkeypatch: pytest.MonkeyPatch) -> FakeFrappe:
	f = FakeFrappe()
	for module in (alerts, rules):
		monkeypatch.setattr(module, "frappe", f, raising=False)
	monkeypatch.setattr(alerts, "now_datetime", f.now)
	monkeypatch.setattr(alerts, "get_datetime", lambda v: v)
	sent: list[tuple[str, str]] = []
	monkeypatch.setattr(
		alerts.notify,
		"notify",
		lambda alert, channels, status: sent.append((alert["target_name"], str(status))) or {},
	)
	monkeypatch.setattr(alerts.realtime, "frappe", f, raising=False)
	f.sent = sent  # type: ignore[attr-defined]
	# One metric rule: disk > 85 for 2 minutes, on servers.
	f.add(
		"Alert Rule",
		name="RULE-DISK",
		title="Disk high",
		kind="metric",
		severity="critical",
		target_doctype="Server",
		metric="disk",
		operator="gt",
		threshold=85.0,
		for_minutes=2,
		enabled=1,
	)
	f.add_child(f.get_doc("Alert Rule", "RULE-DISK"), "Alert Rule Channel", channel="telegram")
	f.add("Server", name="SRV-0001", hostname="s1", status="Active")
	return f


def _metric(ff: FakeFrappe, server: str, disk: float, minutes_ago: int) -> None:
	ff.add(
		"Server Metric",
		server=server,
		resolution="1m",
		ts=ff.now() - timedelta(minutes=minutes_ago),
		disk=disk,
	)


def test_a_sustained_breach_fires_once_then_dedups(ff: FakeFrappe) -> None:
	_metric(ff, "SRV-0001", 90.0, 1)
	_metric(ff, "SRV-0001", 92.0, 0)
	first = alerts.evaluate_rules()
	assert first == {"fired": 1, "resolved": 0}
	alert = next(iter(ff.store["Alert"].values()))
	assert alert.get("status") == "firing" and alert.get("severity") == "critical"
	assert ff.sent == [("SRV-0001", "firing")]  # notified once

	# Still breaching on the next pass: no new alert, no new notification.
	_metric(ff, "SRV-0001", 95.0, 0)
	second = alerts.evaluate_rules()
	assert second == {"fired": 0, "resolved": 0}
	assert len(ff.store["Alert"]) == 1
	assert len(ff.sent) == 1


def test_recovery_resolves_the_alert_once(ff: FakeFrappe) -> None:
	_metric(ff, "SRV-0001", 90.0, 1)
	_metric(ff, "SRV-0001", 92.0, 0)
	alerts.evaluate_rules()
	ff.sent.clear()

	# Disk back under threshold -> resolve, notify once.
	_metric(ff, "SRV-0001", 40.0, 0)
	result = alerts.evaluate_rules()
	assert result == {"fired": 0, "resolved": 1}
	alert = next(iter(ff.store["Alert"].values()))
	assert alert.get("status") == "resolved" and alert.get("resolved_at") is not None
	assert ff.sent == [("SRV-0001", "resolved")]

	# A further clear pass does nothing (already resolved).
	assert alerts.evaluate_rules() == {"fired": 0, "resolved": 0}


def test_an_acknowledged_alert_is_not_refired(ff: FakeFrappe) -> None:
	_metric(ff, "SRV-0001", 90.0, 1)
	_metric(ff, "SRV-0001", 92.0, 0)
	alerts.evaluate_rules()
	name = next(iter(ff.store["Alert"]))
	ff.db.set_value("Alert", name, "status", "acknowledged")
	ff.sent.clear()
	_metric(ff, "SRV-0001", 95.0, 0)
	# Still breaching and already open (acknowledged counts as open): no new alert.
	assert alerts.evaluate_rules() == {"fired": 0, "resolved": 0}
	assert len(ff.store["Alert"]) == 1


def test_drift_alert_opens_on_findings_and_resolves_when_clean(ff: FakeFrappe) -> None:
	ff.add(
		"Alert Rule",
		name="RULE-DRIFT",
		title="Inventory drift",
		kind="drift",
		severity="warning",
		target_doctype="Provider Account",
		builtin=1,
		enabled=1,
	)
	findings = [{"kind": "server_missing", "doctype": "Server", "name": "SRV-9", "detail": "gone"}]
	opened = alerts.sync_drift_alerts("DO-STAGING", findings)
	assert opened == {"fired": 1, "resolved": 0}
	drift = next(a for a in ff.store["Alert"].values() if a.get("kind") == "drift")
	assert drift.get("status") == "firing" and "server_missing" in (drift.get("message") or "")

	# A second sync with the same findings refreshes, does not re-fire.
	assert alerts.sync_drift_alerts("DO-STAGING", findings) == {"fired": 0, "resolved": 0}
	# Clean inventory resolves it.
	assert alerts.sync_drift_alerts("DO-STAGING", []) == {"fired": 0, "resolved": 1}
