"""A3.2: pure alert rule evaluation (metric sustain, heartbeat age, ssl expiry) and messages."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from infra_control.monitoring import notify
from infra_control.monitoring.rules import (
	CLEAR,
	FIRE,
	NOOP,
	HeartbeatInput,
	MetricInput,
	SslInput,
	evaluate_heartbeat,
	evaluate_metric,
	evaluate_ssl,
)

NOW = datetime(2026, 10, 8, 12, 0, 0, tzinfo=UTC)


def metric_rule(**kw: object) -> dict[str, object]:
	return {"metric": "disk", "operator": "gt", "threshold": 85.0, "for_minutes": 3, **kw}


def samples(*values: float | None, step: int = 1) -> list[tuple[datetime, float | None]]:
	n = len(values)
	return [(NOW - timedelta(minutes=(n - 1 - i) * step), v) for i, v in enumerate(values)]


def test_metric_fires_only_when_the_breach_is_sustained() -> None:
	# Three minutes all above 85 -> fire.
	v = evaluate_metric(metric_rule(), MetricInput("SRV-1", samples(88.0, 90.0, 91.0)), NOW)
	assert v.state == FIRE and v.value == 91.0 and "disk" in v.message

	# A single spike in the window is not sustained -> noop (still breaching latest, but not all).
	v = evaluate_metric(metric_rule(), MetricInput("SRV-1", samples(50.0, 60.0, 91.0)), NOW)
	assert v.state == NOOP

	# Not enough coverage (only one reading) -> noop.
	v = evaluate_metric(metric_rule(), MetricInput("SRV-1", samples(91.0)), NOW)
	assert v.state == NOOP


def test_metric_clears_when_the_latest_reading_is_back_under_threshold() -> None:
	v = evaluate_metric(metric_rule(), MetricInput("SRV-1", samples(91.0, 92.0, 70.0)), NOW)
	assert v.state == CLEAR and v.value == 70.0


def test_metric_with_no_readings_is_noop() -> None:
	assert evaluate_metric(metric_rule(), MetricInput("SRV-1", []), NOW).state == NOOP


def test_metric_operators() -> None:
	rule = metric_rule(metric="load1", operator="gte", threshold=4.0, for_minutes=1)
	assert evaluate_metric(rule, MetricInput("s", samples(4.0)), NOW).state == FIRE
	rule = metric_rule(metric="ram", operator="lt", threshold=10.0, for_minutes=1)
	assert evaluate_metric(rule, MetricInput("s", samples(5.0)), NOW).state == FIRE
	assert evaluate_metric(rule, MetricInput("s", samples(50.0)), NOW).state == CLEAR


def test_heartbeat_fires_after_the_window_and_never_before_first_contact() -> None:
	rule = {"for_minutes": 3}
	assert evaluate_heartbeat(rule, HeartbeatInput("s", None, "Provisioning"), NOW).state == NOOP
	old = NOW - timedelta(minutes=5)
	v = evaluate_heartbeat(rule, HeartbeatInput("s", old, "Active"), NOW)
	assert v.state == FIRE and "5 min" in v.message
	recent = NOW - timedelta(minutes=1)
	assert evaluate_heartbeat(rule, HeartbeatInput("s", recent, "Active"), NOW).state == CLEAR


def test_ssl_fires_inside_the_threshold_window() -> None:
	rule = {"threshold": 14}
	assert evaluate_ssl(rule, SslInput("s", None), NOW).state == NOOP
	soon = NOW + timedelta(days=9)
	v = evaluate_ssl(rule, SslInput("s", soon), NOW)
	assert v.state == FIRE and "9 days" in v.message
	later = NOW + timedelta(days=40)
	assert evaluate_ssl(rule, SslInput("s", later), NOW).state == CLEAR


@pytest.mark.parametrize(
	("severity", "status", "expect"),
	[("critical", "firing", "CRITICAL"), ("warning", "resolved", "RESOLVED"), ("info", "firing", "INFO")],
)
def test_notify_message_format(severity: str, status: str, expect: str) -> None:
	from infra_control.core.enums import AlertStatus

	alert = {
		"rule": "RULE-1",
		"rule_title": "Disk high",
		"severity": severity,
		"target_doctype": "Server",
		"target_name": "SRV-0001",
		"message": "disk gt 85",
	}
	text = notify.format_message(alert, AlertStatus(status))
	assert expect in text and "Disk high" in text and "Server SRV-0001" in text and "disk gt 85" in text
