"""Pure metric aggregation (A3.1): rollups and the resolution the API picks for a time range.

No Frappe here. `Sample` is one reading; the rollup folds many 1m samples into one 1h sample and
many 1h into one 1d. cpu/ram/disk/load1 average, queue_backlog takes the window's max (a backlog
spike matters more than its mean).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from infra_control.core.enums import MetricName, Resolution

AVERAGED: tuple[MetricName, ...] = (MetricName.CPU, MetricName.RAM, MetricName.DISK, MetricName.LOAD1)
MAXED: tuple[MetricName, ...] = (MetricName.QUEUE_BACKLOG,)

# Points kept per resolution before a coarser one is used, and how long each is retained.
BUCKET_SECONDS: dict[Resolution, int] = {
	Resolution.ONE_MINUTE: 60,
	Resolution.ONE_HOUR: 3600,
	Resolution.ONE_DAY: 86400,
}
RETENTION_DAYS: dict[Resolution, int] = {
	Resolution.ONE_MINUTE: 7,
	Resolution.ONE_HOUR: 90,
	Resolution.ONE_DAY: 730,
}
# Each rollup reads the finer resolution below it.
ROLLUP_SOURCE: dict[Resolution, Resolution] = {
	Resolution.ONE_HOUR: Resolution.ONE_MINUTE,
	Resolution.ONE_DAY: Resolution.ONE_HOUR,
}
MAX_SERIES_POINTS = 1000


@dataclass(frozen=True)
class Sample:
	ts: datetime
	cpu: float | None
	ram: float | None
	disk: float | None
	load1: float | None
	queue_backlog: int | None

	def value(self, metric: MetricName) -> float | None:
		v = {
			MetricName.CPU: self.cpu,
			MetricName.RAM: self.ram,
			MetricName.DISK: self.disk,
			MetricName.LOAD1: self.load1,
			MetricName.QUEUE_BACKLOG: self.queue_backlog,
		}[metric]
		return None if v is None else float(v)


def _floor(ts: datetime, seconds: int) -> datetime:
	epoch = int(ts.replace(tzinfo=ts.tzinfo or UTC).timestamp())
	return datetime.fromtimestamp(epoch - (epoch % seconds), UTC)


def _avg(values: list[float]) -> float | None:
	return round(sum(values) / len(values), 2) if values else None


def _max(values: list[float]) -> float | None:
	return max(values) if values else None


def rollup(samples: list[Sample], target: Resolution) -> list[Sample]:
	"""Fold finer samples into `target` buckets. One output `Sample` per bucket, in time order."""
	seconds = BUCKET_SECONDS[target]
	buckets: dict[datetime, list[Sample]] = {}
	for s in samples:
		buckets.setdefault(_floor(s.ts, seconds), []).append(s)
	out: list[Sample] = []
	for bucket_ts in sorted(buckets):
		group = buckets[bucket_ts]

		def fold(metric: MetricName, group: list[Sample] = group) -> float | None:
			present = [v for v in (s.value(metric) for s in group) if v is not None]
			return _max(present) if metric in MAXED else _avg(present)

		backlog = fold(MetricName.QUEUE_BACKLOG)
		out.append(
			Sample(
				ts=bucket_ts,
				cpu=fold(MetricName.CPU),
				ram=fold(MetricName.RAM),
				disk=fold(MetricName.DISK),
				load1=fold(MetricName.LOAD1),
				queue_backlog=None if backlog is None else round(backlog),
			)
		)
	return out


def choose_resolution(frm: datetime, to: datetime, requested: Resolution | None = None) -> Resolution:
	"""The requested resolution, or the coarsest that keeps the range under 1000 points."""
	if requested is not None:
		return requested
	span = max(1.0, (to - frm).total_seconds())
	for res in (Resolution.ONE_MINUTE, Resolution.ONE_HOUR, Resolution.ONE_DAY):
		if span / BUCKET_SECONDS[res] <= MAX_SERIES_POINTS:
			return res
	return Resolution.ONE_DAY


def retention_cutoff(resolution: Resolution, now: datetime) -> datetime:
	return now - timedelta(days=RETENTION_DAYS[resolution])
