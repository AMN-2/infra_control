"""The engine's realtime payload builders produce exactly what contracts/events promise."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from infra_control.job_engine import realtime

pytestmark = pytest.mark.contract


def _validator(contracts_dir: Path, event_index: dict[str, str], event: str) -> Draft202012Validator:
	with (contracts_dir / "events" / event_index[event]).open() as fh:
		return Draft202012Validator(json.load(fh), format_checker=FormatChecker())


@pytest.mark.parametrize(
	"built",
	[
		realtime.job_updated("JOB-00042", "Running", 40),
		realtime.job_updated("JOB-00042", "Success", 250),
		realtime.job_step("JOB-00042", 2, "bench migrate", "Running"),
		realtime.job_log("JOB-00042", 2, "x" * 10_000),
		realtime.bulk_updated("BULK-0007", "Running", 1, 3, 1),
		realtime.inventory_changed("Site", "demo.smartchoice-iq.com", "created"),
		realtime.server_heartbeat("SRV-0001", "Active", 23.456, 61.2, 54.0, "2026-10-07T09:30:40Z"),
		realtime.alert_fired("ALERT-1", "RULE-1", "Server", "SRV-0001", "critical"),
		realtime.alert_resolved("ALERT-1", "RULE-1", "Server", "SRV-0001", "critical"),
	],
)
def test_builders_validate(
	built: tuple[str, dict[str, object]], contracts_dir: Path, event_index: dict[str, str]
) -> None:
	event, payload = built
	errors = list(_validator(contracts_dir, event_index, event).iter_errors(payload))
	assert not errors, [e.message for e in errors]


def test_log_chunk_is_cut_to_4kb_and_progress_clamped() -> None:
	assert len(realtime.job_log("J", 0, "y" * 5000)[1]["chunk"]) == 4096
	assert realtime.job_updated("J", "Running", -5)[1]["progress"] == 0
	assert realtime.job_updated("J", "Success", 250)[1]["progress"] == 100
