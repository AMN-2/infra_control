"""A4.1 security review: every API endpoint enforces its role for every role (security
requirement: permission tests per role), and controller secrets are on every job's mask list."""

from __future__ import annotations

import importlib
import pkgutil
from types import SimpleNamespace
from typing import Any

import pytest
from fake_frappe import FakeFrappe

import infra_control.api as api_pkg
from infra_control.core import permissions
from infra_control.core.permissions import INFRA_ADMIN, INFRA_OPERATOR, INFRA_VIEWER

ROLE_SETS: dict[str, tuple[str, ...]] = {
	"nobody": ("System Manager",),
	INFRA_VIEWER: (INFRA_VIEWER,),
	INFRA_OPERATOR: (INFRA_OPERATOR,),
	INFRA_ADMIN: (INFRA_ADMIN,),
}
RANK = {"nobody": 0, INFRA_VIEWER: 1, INFRA_OPERATOR: 2, INFRA_ADMIN: 3}


def endpoints() -> list[tuple[str, Any]]:
	out: list[tuple[str, Any]] = []
	for info in pkgutil.iter_modules(api_pkg.__path__):
		if info.name.startswith("_"):
			continue
		module = importlib.import_module(f"infra_control.api.{info.name}")
		for attr in sorted(vars(module)):
			fn = getattr(module, attr)
			if callable(fn) and hasattr(fn, "required_role") and hasattr(fn, "handler"):
				out.append((f"{info.name}.{attr}", fn))
	return out


ENDPOINTS = endpoints()


def test_the_matrix_covers_every_endpoint_in_the_contract() -> None:
	from contracts.test_openapi import REQUIRED_ENDPOINTS  # the contract allowlist

	found = {name for name, _ in ENDPOINTS}
	assert set(REQUIRED_ENDPOINTS) <= found, sorted(set(REQUIRED_ENDPOINTS) - found)


@pytest.mark.parametrize(("name", "fn"), ENDPOINTS, ids=[n for n, _ in ENDPOINTS])
@pytest.mark.parametrize("held", list(ROLE_SETS))
def test_endpoint_refuses_lower_roles_and_admits_the_required_one(
	monkeypatch: pytest.MonkeyPatch, name: str, fn: Any, held: str
) -> None:
	f = FakeFrappe(user="u@x", roles=ROLE_SETS[held])
	f.session = SimpleNamespace(user="u@x")
	monkeypatch.setattr(api_pkg, "frappe", f)
	monkeypatch.setattr(permissions, "frappe", f)
	fn.handler()
	status = f.local.response.get("http_status_code")
	required = str(fn.required_role)
	if RANK[held] < RANK[required]:
		assert status == 403, f"{name}: {held} must be refused (got {status})"
		assert f.local.response["error"]["code"] == "permission_denied"
	else:
		# Admitted: the handler proceeds to validation (400/404/409) or fails deeper in the fake
		# (500); anything but a role refusal.
		assert status != 403, f"{name}: {held} must be admitted"


def test_controller_secrets_are_on_the_mask_list(monkeypatch: pytest.MonkeyPatch) -> None:
	from infra_control.core import secrets

	f = FakeFrappe()
	f.singles["Infra Settings"] = {
		"spaces_key": "AKIASEEDED0001",
		"spaces_secret": "seededspacessecret",
		"telegram_bot_token": "123456:seededtelegramtoken",
		"offsite_secret": "",
	}
	monkeypatch.setattr(secrets, "frappe", f)
	values = secrets.controller_secret_values()
	assert set(values) == {"AKIASEEDED0001", "seededspacessecret", "123456:seededtelegramtoken"}
	from infra_control.job_engine.masking import mask_secrets

	masked = mask_secrets("key=AKIASEEDED0001 token 123456:seededtelegramtoken", values)
	assert "AKIASEEDED0001" not in masked and "seededtelegramtoken" not in masked
