"""Infra users land on `/infra` after login; others and explicit redirects are left alone."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fake_frappe import FakeFrappe

from infra_control.core import login, permissions


def _install(
	monkeypatch: pytest.MonkeyPatch, user: str, roles: tuple[str, ...], form: dict[str, str]
) -> FakeFrappe:
	ff = FakeFrappe(user=user, roles=roles)
	ff.session = SimpleNamespace(user=user)
	ff.form_dict = form  # type: ignore[attr-defined]
	for module in (login, permissions):
		monkeypatch.setattr(module, "frappe", ff, raising=False)
	return ff


@pytest.mark.parametrize(
	("roles", "form", "expected"),
	[
		(("Infra Viewer",), {}, "/infra"),
		(("Infra Admin",), {"redirect-to": "/login"}, "/infra"),
		(("Infra Admin",), {"redirect-to": "/app/user"}, None),
		(("Sales User",), {}, None),
	],
)
def test_landing(
	monkeypatch: pytest.MonkeyPatch,
	roles: tuple[str, ...],
	form: dict[str, str],
	expected: str | None,
) -> None:
	ff = _install(monkeypatch, "u@x", roles, form)
	login.on_session_creation()
	assert ff.cache().hget("redirect_after_login", "u@x") == expected


def test_guest_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
	ff = _install(monkeypatch, "Guest", (), {})
	login.on_session_creation()
	assert ff.cache().hget("redirect_after_login", "Guest") is None
