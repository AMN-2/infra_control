"""A3.4: the bulk serializers produce exactly the shapes in contracts/openapi.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker

from infra_control.api import _serialize as ser

pytestmark = pytest.mark.contract


@pytest.fixture(scope="module")
def spec(contracts_dir: Path) -> dict[str, Any]:
	with (contracts_dir / "openapi.yaml").open() as fh:
		loaded: dict[str, Any] = yaml.safe_load(fh)
	return loaded


def _validate(spec: dict[str, Any], schema_name: str, value: Any) -> None:
	wrapped = {
		"$id": "urn:openapi",
		"components": spec["components"],
		"allOf": [{"$ref": f"#/components/schemas/{schema_name}"}],
	}
	errors = sorted(
		Draft202012Validator(wrapped, format_checker=FormatChecker()).iter_errors(value),
		key=lambda e: list(e.path),
	)
	assert not errors, f"{schema_name}: " + "; ".join(f"{list(e.path)}: {e.message}" for e in errors[:5])


def _bulk_row() -> dict[str, Any]:
	return {
		"name": "BULK-0007",
		"playbook": "site.migrate",
		"playbook_title": "Migrate site",
		"status": "Running",
		"phase": "batches",
		"failure_policy": "halt",
		"batch_size": 2,
		"canary_doctype": "Site",
		"canary_name": "demo.smartchoice-iq.com",
		"total": 3,
		"done": 1,
		"failed": 0,
		"current_batch": 1,
		"batches_total": 1,
		"triggered_by": "ameen@smartchoice-iq.com",
		"creation": "2026-10-07 12:40:00",
		"started_at": "2026-10-07 12:40:03",
		"ended_at": None,
	}


@pytest.fixture(autouse=True)
def _utc(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(ser, "system_timezone", lambda: "UTC")


def test_bulk_matches_bulkoperation_and_envelope(spec: dict[str, Any]) -> None:
	out = ser.bulk(_bulk_row())
	_validate(spec, "BulkOperation", out)
	assert out["canary_target"] == {"target_doctype": "Site", "target_name": "demo.smartchoice-iq.com"}
	assert out["created_at"] == "2026-10-07T12:40:00Z" and out["ended_at"] is None
	_validate(spec, "BulkEnvelope", {"bulk": out})


def test_bulk_target_matches_schema(spec: dict[str, Any]) -> None:
	for row, expected_job in (
		(
			{
				"target_doctype": "Site",
				"target_name": "demo.iq",
				"status": "Success",
				"job": "JOB-1",
				"batch": 0,
			},
			"JOB-1",
		),
		(
			{"target_doctype": "Site", "target_name": "erp.iq", "status": "Pending", "job": None, "batch": 2},
			None,
		),
	):
		out = ser.bulk_target(row)
		_validate(spec, "BulkTarget", out)
		assert out["job"] == expected_job


def test_bulk_detail_with_targets(spec: dict[str, Any]) -> None:
	out = ser.bulk(_bulk_row())
	out["targets"] = [
		ser.bulk_target(
			{
				"target_doctype": "Site",
				"target_name": "demo.iq",
				"status": "Success",
				"job": "JOB-1",
				"batch": 0,
			}
		),
		ser.bulk_target(
			{
				"target_doctype": "Site",
				"target_name": "erp.iq",
				"status": "Running",
				"job": "JOB-2",
				"batch": 1,
			}
		),
	]
	_validate(spec, "BulkOperationDetail", out)
