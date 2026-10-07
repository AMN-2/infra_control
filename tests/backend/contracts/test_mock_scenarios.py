"""A0.4 contract tests: every mock scenario step is a valid event payload."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

pytestmark = pytest.mark.contract

REQUIRED_SCENARIOS = {"provisioning", "failing-migrate", "bulk-rollout"}  # plan section 6.3


def _scenarios(contracts_dir: Path) -> dict[str, dict[str, Any]]:
	out: dict[str, dict[str, Any]] = {}
	for path in sorted((contracts_dir / "mock" / "scenarios").glob("*.json")):
		with path.open() as fh:
			out[path.name] = json.load(fh)
	return out


def test_plan_scenarios_exist(contracts_dir: Path) -> None:
	names = {s["name"] for s in _scenarios(contracts_dir).values()}
	assert REQUIRED_SCENARIOS <= names


def test_every_step_validates(contracts_dir: Path, event_index: dict[str, str]) -> None:
	validators = {}
	for event, file in event_index.items():
		with (contracts_dir / "events" / file).open() as fh:
			validators[event] = Draft202012Validator(json.load(fh), format_checker=FormatChecker())
	for file, scenario in _scenarios(contracts_dir).items():
		assert scenario["name"] == file.removesuffix(".json")
		assert scenario["description"]
		assert scenario["steps"]
		for i, step in enumerate(scenario["steps"]):
			assert step["event"] in validators, f"{file} step {i}: unknown event {step['event']}"
			assert isinstance(step.get("delay_ms", 0), int) and step.get("delay_ms", 0) >= 0
			errors = list(validators[step["event"]].iter_errors(step["payload"]))
			assert not errors, f"{file} step {i}: {[e.message for e in errors]}"


def test_jobs_end_in_a_terminal_state(contracts_dir: Path) -> None:
	"""Each job a scenario starts must finish with a terminal job.updated so the UI never hangs."""
	for file, scenario in _scenarios(contracts_dir).items():
		last: dict[str, str] = {}
		for step in scenario["steps"]:
			if step["event"] == "infra:job.updated":
				last[step["payload"]["job"]] = step["payload"]["status"]
		for job, status in last.items():
			assert status in {"Success", "Failed", "Cancelled"}, f"{file}: {job} ends in {status}"
