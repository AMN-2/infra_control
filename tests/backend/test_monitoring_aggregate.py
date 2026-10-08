"""A3.1: pure metric aggregation (rollup, resolution choice, retention cutoff)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from infra_control.core.enums import Resolution
from infra_control.monitoring.aggregate import (
	MAX_SERIES_POINTS,
	Sample,
	choose_resolution,
	retention_cutoff,
	rollup,
)

BASE = datetime(2026, 10, 7, 9, 0, 0, tzinfo=UTC)


def s(minute: int, cpu: float | None, backlog: int | None = 0) -> Sample:
	return Sample(
		ts=BASE + timedelta(minutes=minute),
		cpu=cpu,
		ram=cpu,
		disk=cpu,
		load1=None if cpu is None else cpu / 100,
		queue_backlog=backlog,
	)


def test_rollup_averages_rates_and_maxes_backlog() -> None:
	samples = [s(0, 10, 5), s(1, 20, 30), s(2, 30, 10), s(61, 90, 1)]
	hourly = rollup(samples, Resolution.ONE_HOUR)
	assert len(hourly) == 2
	first = hourly[0]
	assert first.ts == datetime(2026, 10, 7, 9, 0, tzinfo=UTC)
	assert first.cpu == 20.0 and first.ram == 20.0  # (10+20+30)/3
	assert first.queue_backlog == 30  # max, not mean
	assert first.load1 == 0.2
	assert hourly[1].cpu == 90.0


def test_rollup_ignores_missing_values_in_the_average() -> None:
	hourly = rollup([s(0, 10), s(1, None), s(2, 40)], Resolution.ONE_HOUR)
	assert hourly[0].cpu == 25.0  # (10+40)/2, the gap is skipped


def test_rollup_of_nothing_is_empty() -> None:
	assert rollup([], Resolution.ONE_DAY) == []


def test_daily_buckets_floor_to_midnight_utc() -> None:
	samples = [
		Sample(
			ts=datetime(2026, 10, 7, 23, 30, tzinfo=UTC), cpu=10, ram=10, disk=10, load1=0.1, queue_backlog=0
		),
		Sample(
			ts=datetime(2026, 10, 8, 0, 30, tzinfo=UTC), cpu=20, ram=20, disk=20, load1=0.2, queue_backlog=0
		),
	]
	daily = rollup(samples, Resolution.ONE_DAY)
	assert [d.ts for d in daily] == [datetime(2026, 10, 7, tzinfo=UTC), datetime(2026, 10, 8, tzinfo=UTC)]


def test_choose_resolution_keeps_series_under_the_point_cap() -> None:
	base = datetime(2026, 10, 7, tzinfo=UTC)
	# An hour of 1m points: 60 <= 1000, so 1m.
	assert choose_resolution(base, base + timedelta(hours=1)) is Resolution.ONE_MINUTE
	# A month at 1m would be ~43k points, so 1h (720 <= 1000); at a year, 1d.
	assert choose_resolution(base, base + timedelta(days=30)) is Resolution.ONE_HOUR
	assert choose_resolution(base, base + timedelta(days=365)) is Resolution.ONE_DAY
	# A requested resolution is honoured as-is.
	assert choose_resolution(base, base + timedelta(days=365), Resolution.ONE_MINUTE) is Resolution.ONE_MINUTE


def test_a_week_of_minutes_would_exceed_the_cap_so_coarser_is_chosen() -> None:
	base = datetime(2026, 10, 7, tzinfo=UTC)
	res = choose_resolution(base, base + timedelta(days=7))
	assert res is Resolution.ONE_HOUR
	assert (7 * 86400) / 3600 <= MAX_SERIES_POINTS


def test_retention_cutoff_per_resolution() -> None:
	now = datetime(2026, 10, 8, tzinfo=UTC)
	assert retention_cutoff(Resolution.ONE_MINUTE, now) == now - timedelta(days=7)
	assert retention_cutoff(Resolution.ONE_HOUR, now) == now - timedelta(days=90)
	assert retention_cutoff(Resolution.ONE_DAY, now) == now - timedelta(days=730)
