"""Scheduler entry point (hooks.py cron, every minute): crash recovery for the job engine."""

from __future__ import annotations

from infra_control.bulk.engine import requeue_running
from infra_control.job_engine.engine import fail_stale_jobs


def run() -> None:
	fail_stale_jobs()
	# A Running bulk whose driver died is re-enqueued; the driver is idempotent (A3.4).
	requeue_running()
