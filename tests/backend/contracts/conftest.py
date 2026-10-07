from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml


@pytest.fixture(scope="session")
def spec(contracts_dir: Path) -> dict[str, Any]:
	with (contracts_dir / "openapi.yaml").open() as fh:
		loaded: dict[str, Any] = yaml.safe_load(fh)
	return loaded


@pytest.fixture(scope="session")
def event_index(contracts_dir: Path) -> dict[str, str]:
	with (contracts_dir / "events" / "index.json").open() as fh:
		data = json.load(fh)
	events: dict[str, str] = data["events"]
	return events
