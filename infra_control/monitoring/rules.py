"""Alert rule evaluation (A3.2, plan 9.4), pure.

`evaluate` decides, for one rule against one target, whether the condition is currently met and
whether it has held long enough to fire (`for_minutes`). It takes already-fetched inputs so it
never touches Frappe; `alerts.py` gathers the inputs and acts on the verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from infra_control.core.enums import AlertRuleKind, MetricName, Operator

# A verdict's `state`.
FIRE = "fire"
CLEAR = "clear"
NOOP = "noop"


@dataclass(frozen=True)
class Verdict:
	state: str
	"""`fire` | `clear` | `noop`"""
	value: float | None = None
	message: str = ""


def _compare(value: float, operator: Operator, threshold: float) -> bool:
	return {
		Operator.GT: value > threshold,
		Operator.GTE: value >= threshold,
		Operator.LT: value < threshold,
		Operator.LTE: value <= threshold,
		Operator.EQ: value == threshold,
	}[operator]


@dataclass(frozen=True)
class MetricInput:
	"""The last `for_minutes` of 1m readings for the rule's metric, newest last."""

	target: str
	samples: list[tuple[datetime, float | None]]


def evaluate_metric(rule: dict[str, Any], data: MetricInput, now: datetime) -> Verdict:
	metric = MetricName(str(rule["metric"]))
	operator = Operator(str(rule["operator"]))
	threshold = float(rule["threshold"])
	for_minutes = int(rule.get("for_minutes") or 0)
	window = [
		v for ts, v in data.samples if v is not None and ts >= now - timedelta(minutes=max(for_minutes, 1))
	]
	if not window:
		return Verdict(NOOP)
	latest = window[-1]
	breaching = all(_compare(v, operator, threshold) for v in window)
	# Enough coverage: at least `for_minutes` readings in the window (one per minute).
	sustained = len(window) >= max(for_minutes, 1)
	if breaching and sustained:
		return Verdict(
			FIRE,
			value=latest,
			message=f"{metric} {operator.value} {threshold:g} for {for_minutes} min (now {latest:g})",
		)
	if not _compare(latest, operator, threshold):
		return Verdict(CLEAR, value=latest, message=f"{metric} back within threshold (now {latest:g})")
	return Verdict(NOOP, value=latest)


@dataclass(frozen=True)
class HeartbeatInput:
	target: str
	last_heartbeat: datetime | None
	status: str


def evaluate_heartbeat(rule: dict[str, Any], data: HeartbeatInput, now: datetime) -> Verdict:
	for_minutes = int(rule.get("for_minutes") or 3)
	if data.last_heartbeat is None:
		return Verdict(NOOP)  # never heard from yet; a fresh provision is not a missing heartbeat
	age = now - data.last_heartbeat
	if age >= timedelta(minutes=for_minutes):
		mins = int(age.total_seconds() // 60)
		return Verdict(FIRE, value=float(mins), message=f"no heartbeat for {mins} min")
	return Verdict(CLEAR, message="heartbeat received")


@dataclass(frozen=True)
class SslInput:
	target: str
	ssl_expiry: datetime | None


def evaluate_ssl(rule: dict[str, Any], data: SslInput, now: datetime) -> Verdict:
	days = float(rule.get("threshold") or 14)
	if data.ssl_expiry is None:
		return Verdict(NOOP)
	remaining = (data.ssl_expiry - now).total_seconds() / 86400
	if remaining <= days:
		return Verdict(
			FIRE, value=round(remaining, 1), message=f"certificate expires in {remaining:.0f} days"
		)
	return Verdict(
		CLEAR, value=round(remaining, 1), message=f"certificate valid for {remaining:.0f} more days"
	)


KIND_EVALUATORS = {
	AlertRuleKind.METRIC: evaluate_metric,
	AlertRuleKind.HEARTBEAT: evaluate_heartbeat,
	AlertRuleKind.SSL_EXPIRY: evaluate_ssl,
}
