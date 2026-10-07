"""A0.2 contract tests: contracts/events/*.schema.json are valid, strict and documented."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

pytestmark = pytest.mark.contract

# Plan section 6.2, verbatim.
PLAN_EVENTS = [
	"infra:job.updated",
	"infra:job.step",
	"infra:job.log",
	"infra:bulk.updated",
	"infra:server.heartbeat",
	"infra:alert.fired",
	"infra:alert.resolved",
	"infra:inventory.changed",
]

PLAN_PAYLOAD_KEYS: dict[str, set[str]] = {
	"infra:job.updated": {"job", "status", "progress"},
	"infra:job.step": {"job", "idx", "title", "status"},
	"infra:job.log": {"job", "idx", "chunk"},
	"infra:bulk.updated": {"bulk", "status", "done", "total", "current_batch"},
	"infra:server.heartbeat": {"server", "status", "cpu", "ram", "disk", "ts"},
	"infra:alert.fired": {"alert", "rule", "target", "severity"},
	"infra:alert.resolved": {"alert", "rule", "target", "severity"},
	"infra:inventory.changed": {"doctype", "name", "change"},
}


def _load(contracts_dir: Path, file: str) -> dict[str, Any]:
	with (contracts_dir / "events" / file).open() as fh:
		data: dict[str, Any] = json.load(fh)
	return data


def test_index_covers_exactly_the_plan_events(event_index: dict[str, str], contracts_dir: Path) -> None:
	assert list(event_index) == PLAN_EVENTS
	for file in event_index.values():
		assert (contracts_dir / "events" / file).is_file(), file
	on_disk = {p.name for p in (contracts_dir / "events").glob("*.schema.json")}
	assert on_disk == set(event_index.values()), "schema files without an index entry"


@pytest.mark.parametrize("event", PLAN_EVENTS)
def test_schema_is_strict_and_matches_plan_payload(
	event: str, event_index: dict[str, str], contracts_dir: Path
) -> None:
	schema = _load(contracts_dir, event_index[event])
	Draft202012Validator.check_schema(schema)
	assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
	assert schema["title"] == event
	assert schema["$id"].endswith(event_index[event])
	assert schema["type"] == "object"
	assert schema["additionalProperties"] is False
	assert set(schema["required"]) == PLAN_PAYLOAD_KEYS[event]
	assert set(schema["properties"]) == PLAN_PAYLOAD_KEYS[event]
	assert schema.get("description"), "every event needs a description"


@pytest.mark.parametrize("event", PLAN_EVENTS)
def test_examples_validate(event: str, event_index: dict[str, str], contracts_dir: Path) -> None:
	schema = _load(contracts_dir, event_index[event])
	examples = schema.get("examples", [])
	assert examples, f"{event} needs at least one example"
	validator = Draft202012Validator(schema, format_checker=FormatChecker())
	for example in examples:
		errors = list(validator.iter_errors(example))
		assert not errors, [e.message for e in errors]


def test_job_log_chunk_is_capped_at_4kb(event_index: dict[str, str], contracts_dir: Path) -> None:
	schema = _load(contracts_dir, event_index["infra:job.log"])
	assert schema["properties"]["chunk"]["maxLength"] == 4096


def test_event_enums_match_openapi(
	spec: dict[str, Any], event_index: dict[str, str], contracts_dir: Path
) -> None:
	"""Status enums in events must be the same unified enums the REST API uses."""
	s = spec["components"]["schemas"]
	assert (
		_load(contracts_dir, event_index["infra:job.updated"])["properties"]["status"]["enum"]
		== s["JobStatus"]["enum"]
	)
	assert (
		_load(contracts_dir, event_index["infra:job.step"])["properties"]["status"]["enum"]
		== s["StepStatus"]["enum"]
	)
	assert (
		_load(contracts_dir, event_index["infra:bulk.updated"])["properties"]["status"]["enum"]
		== s["BulkStatus"]["enum"]
	)
	assert (
		_load(contracts_dir, event_index["infra:server.heartbeat"])["properties"]["status"]["enum"]
		== s["ServerStatus"]["enum"]
	)
	assert (
		_load(contracts_dir, event_index["infra:alert.fired"])["properties"]["severity"]["enum"]
		== s["Severity"]["enum"]
	)
