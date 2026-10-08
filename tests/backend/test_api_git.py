"""ADR 0005 API: connect (verify + store), list without tokens, repos/refs through the client,
disconnect, and the provider layer's token lookup."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from fake_frappe import FakeFrappe
from test_api import call, validate

import infra_control.api as api_pkg
from infra_control.api import _serialize, git
from infra_control.core import audit, permissions
from infra_control.core.errors import NotFound, ValidationError
from infra_control.integrations.github import GitIdentity


class _FakeClient:
	def __init__(self, token: str, **kw: Any) -> None:
		self.token = token

	def whoami(self) -> GitIdentity:
		if self.token != "ghp_good":
			raise ValidationError("GitHub rejected the access token", {"field": "token"})
		return GitIdentity("smartchoice-iq", "Organization", "repo, read:org")

	def list_repos(self, query: str = "", page: int = 1) -> tuple[list[dict[str, Any]], bool]:
		repo = {
			"full_name": "smartchoice-iq/smart_features",
			"name": "smart_features",
			"owner": "smartchoice-iq",
			"private": True,
			"default_branch": "develop",
			"clone_url": "https://github.com/smartchoice-iq/smart_features.git",
			"description": None,
			"pushed_at": "2026-10-08T21:10:00Z",
		}
		return ([repo] if query in ("", "smart") else [], page == 1)

	def get_repo(self, full_name: str) -> dict[str, Any]:
		return self.list_repos()[0][0]

	def list_refs(self, full_name: str) -> list[dict[str, Any]]:
		return [
			{"name": "develop", "kind": "branch", "sha": "1a2b3c4d5e6f"},
			{"name": "v1.2.0", "kind": "tag", "sha": "2b3c4d5e6f70"},
		]


@pytest.fixture
def ff(monkeypatch: pytest.MonkeyPatch) -> FakeFrappe:
	f = FakeFrappe()
	for module in (api_pkg, _serialize, git, audit, permissions):
		monkeypatch.setattr(module, "frappe", f)
	monkeypatch.setattr(_serialize, "system_timezone", lambda: "UTC")
	monkeypatch.setattr(git, "now_datetime", lambda: datetime(2026, 10, 9, 8, 0, 0))
	monkeypatch.setattr(audit, "now_datetime", f.now)
	monkeypatch.setattr(git, "GitHubClient", _FakeClient)
	return f


def test_connect_verifies_stores_and_never_returns_the_token(ff: FakeFrappe) -> None:
	status, body = call(git.connect, label="GH-SMARTCHOICE", token="ghp_good")
	assert status == 200
	validate("git.connect", body)
	c = body["connection"]
	assert (c["login"], c["account_type"], c["scopes"]) == (
		"smartchoice-iq",
		"Organization",
		["repo", "read:org"],
	)
	assert "token" not in c and c["verified_at"] == "2026-10-09T08:00:00Z"
	assert ff.store["Git Connection"]["GH-SMARTCHOICE"].get("token") == "ghp_good"
	status, body = call(git.connections)
	validate("git.connections", body)
	assert [i["name"] for i in body["items"]] == ["GH-SMARTCHOICE"] and "token" not in body["items"][0]
	assert git.token_for("GH-SMARTCHOICE") == "ghp_good"
	# Re-connecting the same label replaces the token after verifying it again.
	status, body = call(git.connect, label="GH-SMARTCHOICE", token="ghp_bad")
	assert status == 400 and body["error"]["code"] == "validation_error"
	assert ff.store["Git Connection"]["GH-SMARTCHOICE"].get("token") == "ghp_good"
	assert [a.get("action") for a in ff.store["Infra Audit Log"].values()] == ["git.connect"]


def test_repos_refs_and_disconnect(ff: FakeFrappe) -> None:
	call(git.connect, label="GH", token="ghp_good")
	status, body = call(git.repos, connection="GH", query="smart")
	assert status == 200
	validate("git.repos", body)
	assert body["items"][0]["full_name"] == "smartchoice-iq/smart_features" and body["next_page"] == 2
	status, body = call(git.repos, connection="GH", query="zzz", page=2)
	assert body == {"items": [], "next_page": None}
	status, body = call(git.refs, connection="GH", repo="smartchoice-iq/smart_features")
	validate("git.refs", body)
	assert [r["kind"] for r in body["items"]] == ["branch", "tag"]
	status, body = call(git.repos, connection="NOPE")
	assert status == 404
	status, body = call(git.disconnect, connection="GH")
	assert status == 200 and body == {"connection": "GH", "deleted": True}
	validate("git.disconnect", body)
	assert "GH" not in ff.store.get("Git Connection", {})
	with pytest.raises(NotFound):
		git.token_for("GH")


def test_disabled_connection_is_refused(ff: FakeFrappe) -> None:
	call(git.connect, label="GH", token="ghp_good")
	ff.store["Git Connection"]["GH"]._data["enabled"] = 0
	status, body = call(git.repos, connection="GH")
	assert status == 400
	with pytest.raises(ValidationError):
		git.token_for("GH")
