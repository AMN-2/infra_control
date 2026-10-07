"""Shared fixtures for backend unit and contract tests.

These tests never need a Frappe site. Anything that does is marked `integration` and runs
through `bench --site <site> run-tests --app infra_control` in the bench CI job.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = REPO_ROOT / "contracts"

# Make `.github/scripts` importable for its unit test without turning it into a package.
sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))


@pytest.fixture(scope="session")
def repo_root() -> Path:
	return REPO_ROOT


@pytest.fixture(scope="session")
def contracts_dir() -> Path:
	return CONTRACTS_DIR
