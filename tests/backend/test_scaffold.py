"""A0.1: the app skeleton matches the plan's repository layout (section 8)."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

PACKAGES = [
	"infra_control",
	"infra_control.api",
	"infra_control.core",
	"infra_control.job_engine",
	"infra_control.providers",
	"infra_control.providers.digitalocean",
	"infra_control.providers.frappe_cloud",
	"infra_control.monitoring",
	"infra_control.bulk",
]


@pytest.mark.parametrize("package", PACKAGES)
def test_package_imports(package: str) -> None:
	assert importlib.import_module(package) is not None


def test_app_identity(repo_root: Path) -> None:
	hooks = importlib.import_module("infra_control.hooks")
	assert hooks.app_name == "infra_control"
	assert hooks.app_title == "Infra Control"
	assert (repo_root / "infra_control" / "modules.txt").read_text().strip() == "Infra Control"
	assert (repo_root / "infra_control" / "py.typed").exists()


def test_no_legacy_name(repo_root: Path) -> None:
	"""The scaffold typo (inf-ta) must not survive in code or config (docs may mention it)."""
	legacy = "inf" + "ta_control"  # split so this file does not match itself
	offenders: list[str] = []
	for path in repo_root.rglob("*"):
		parts = path.relative_to(repo_root).parts
		if not path.is_file() or any(p in {".git", "node_modules", "frontend", "__pycache__"} for p in parts):
			continue
		if path.suffix in {".py", ".toml", ".yml", ".yaml", ".txt", ".json", ".cfg"}:
			if legacy in path.read_text(errors="ignore"):
				offenders.append(str(path.relative_to(repo_root)))
	assert offenders == []
