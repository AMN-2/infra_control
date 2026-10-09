"""ADR 0008: `/infra` sends guests to the in-app login, which renders with guest boot data;
`session.boot` returns the logged-in boot record in the contract's shape."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fake_frappe import FakeFrappe
from test_api import call, validate

import infra_control.api as api_pkg
from infra_control.api import session
from infra_control.core import boot, permissions
from infra_control.core.spa import SpaAssets
from infra_control.www import infra


class _Redirect(Exception):
	http_status_code = 301


def _frappe(monkeypatch: pytest.MonkeyPatch, user: str, path: str) -> FakeFrappe:
	ff = FakeFrappe(user=user, roles=("Infra Operator",) if user != "Guest" else ())
	ff.session = SimpleNamespace(user=user)
	ff.local.request = SimpleNamespace(path=path)
	ff.local.site = "ops.localhost"
	ff.flags = SimpleNamespace()  # type: ignore[attr-defined]
	ff.Redirect = _Redirect  # type: ignore[attr-defined]
	ff.sessions = SimpleNamespace(get_csrf_token=lambda: "tok-123")  # type: ignore[attr-defined]
	for module in (infra, boot, permissions, api_pkg):
		monkeypatch.setattr(module, "frappe", ff, raising=False)
	monkeypatch.setattr(infra, "load_assets", lambda: SpaAssets(entry="/assets/x.js"))
	return ff


def test_guest_on_any_app_path_goes_to_the_in_app_login(monkeypatch: pytest.MonkeyPatch) -> None:
	ff = _frappe(monkeypatch, "Guest", "/infra/servers/SRV-0001")
	with pytest.raises(_Redirect) as exc:
		infra.get_context(SimpleNamespace())
	assert exc.value.http_status_code == 302
	assert ff.flags.redirect_location == "/infra/login?redirect-to=%2Finfra%2Fservers%2FSRV-0001"  # type: ignore[attr-defined]


@pytest.mark.parametrize("path", ["/infra/login", "/infra/login/"])
def test_guest_on_the_login_path_gets_guest_boot(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
	_frappe(monkeypatch, "Guest", path)
	ctx: Any = SimpleNamespace()
	infra.get_context(ctx)
	assert ctx.boot["session_user"] == "Guest"
	assert ctx.boot["roles"] == [] and ctx.boot["csrf_token"] == "" and ctx.csrf_token == ""
	assert ctx.boot["login_alternatives"] is False
	assert ctx.assets.entry == "/assets/x.js"


def test_logged_in_user_gets_full_boot_even_on_the_login_path(monkeypatch: pytest.MonkeyPatch) -> None:
	_frappe(monkeypatch, "op@x", "/infra/login")
	ctx: Any = SimpleNamespace()
	infra.get_context(ctx)
	assert ctx.boot["session_user"] == "op@x" and ctx.boot["csrf_token"] == "tok-123"
	assert ctx.boot["roles"] == ["Infra Operator", "Infra Viewer"]
	assert "login_alternatives" not in ctx.boot


def test_login_alternatives_reflect_social_login_and_ldap(monkeypatch: pytest.MonkeyPatch) -> None:
	ff = _frappe(monkeypatch, "Guest", "/infra/login")
	assert boot.login_alternatives() is False
	ff.add("Social Login Key", name="github", enable_social_login=1)
	assert boot.login_alternatives() is True


def test_session_boot_matches_the_contract(monkeypatch: pytest.MonkeyPatch) -> None:
	_frappe(monkeypatch, "op@x", "/infra/login")
	status, body = call(session.boot)
	assert status == 200, body
	validate("session.boot", body)
	assert body["csrf_token"] == "tok-123" and body["session_user"] == "op@x"
	assert body["roles"] == ["Infra Operator", "Infra Viewer"] and body["socketio_port"] is None


def test_session_boot_refuses_a_session_without_infra_roles(monkeypatch: pytest.MonkeyPatch) -> None:
	ff = _frappe(monkeypatch, "sales@x", "/infra/login")
	ff.roles["sales@x"] = ("Sales User",)
	status, body = call(session.boot)
	assert status == 403 and body["error"]["code"] == "permission_denied"
