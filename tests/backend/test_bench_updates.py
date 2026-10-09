"""ADR 0009: app update checks against GitHub, the version refs, discovery of commit/remote,
and the bulk preflight."""

from __future__ import annotations

import importlib.util
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import responses
from fake_frappe import FakeFrappe
from test_api import call, validate

import infra_control.api as api_pkg
from infra_control.api import _inventory_helpers as helpers
from infra_control.api import _pagination as pagination
from infra_control.api import _serialize as ser
from infra_control.api import benches, bulk
from infra_control.benches import updates
from infra_control.bulk import preflight
from infra_control.core import audit, permissions
from infra_control.integrations.github import API_BASE, GitHubClient, github_repo_of, major_of_branch
from infra_control.job_engine import engine
from infra_control.providers import registry

REPO = Path(__file__).resolve().parents[2]


# --- GitHub helpers ------------------------------------------------------------------------
def test_remote_parsing_and_branch_major() -> None:
	assert github_repo_of("https://github.com/frappe/erpnext.git") == "frappe/erpnext"
	assert github_repo_of("git@github.com:frappe/hrms") == "frappe/hrms"
	assert github_repo_of("https://gitlab.com/x/y.git") is None
	assert github_repo_of(None) is None
	assert major_of_branch("version-15") == 15
	assert major_of_branch("v14") == 14
	assert major_of_branch("develop") is None


@responses.activate
def test_anonymous_client_and_upstream_queries() -> None:
	gh = GitHubClient(None, sleep=lambda s: None)
	responses.get(f"{API_BASE}/repos/frappe/erpnext/commits/version-15", json={"sha": "f6e5d4c3b2a1deadbeef"})
	responses.get(
		f"{API_BASE}/repos/frappe/erpnext/compare/0badc0ffee11...version-15",
		json={"ahead_by": 12, "behind_by": 0},
	)
	responses.get(
		f"{API_BASE}/repos/frappe/erpnext/tags",
		json=[{"name": "v15.95.2"}, {"name": "v15.101.0"}, {"name": "v16.0.0-beta"}, {"name": "v14.80.1"}],
	)
	assert gh.branch_head("frappe/erpnext", "version-15") == "f6e5d4c3b2a1"
	assert gh.commits_behind("frappe/erpnext", "0badc0ffee11", "version-15") == 12
	assert gh.latest_tag("frappe/erpnext", 15) == "v15.101.0"
	assert gh.latest_tag("frappe/erpnext") == "v15.101.0"  # v16.0.0-beta is not a plain version tag
	assert "Authorization" not in responses.calls[0].request.headers


class _Gh:
	def __init__(self) -> None:
		self.calls: list[str] = []

	def branch_head(self, repo: str, branch: str) -> str:
		self.calls.append(f"head {repo} {branch}")
		return "f6e5d4c3b2a1"

	def commits_behind(self, repo: str, commit: str, branch: str) -> int:
		self.calls.append(f"compare {repo} {commit} {branch}")
		return 3

	def latest_tag(self, repo: str, major: int | None = None) -> str | None:
		return f"v{major}.101.0" if major else None

	def get_repo(self, repo: str) -> dict[str, Any]:
		return {
			"full_name": repo,
			"name": repo.split("/")[1],
			"owner": repo.split("/")[0],
			"private": False,
			"default_branch": "develop",
			"clone_url": f"https://github.com/{repo}.git",
			"description": None,
			"pushed_at": None,
		}

	def list_refs(self, repo: str) -> list[dict[str, Any]]:
		return [
			{"name": "version-15", "kind": "branch", "sha": "f6e5d4c3b2a1"},
			{"name": "v15.101.0", "kind": "tag", "sha": "aaaa"},
		]


@pytest.fixture
def ff(monkeypatch: pytest.MonkeyPatch) -> FakeFrappe:
	f = FakeFrappe(user="op@x", roles=("Infra Operator",))
	f.session = SimpleNamespace(user="op@x")
	for module in (
		api_pkg,
		benches,
		updates,
		bulk,
		preflight,
		audit,
		permissions,
		engine,
		registry,
		ser,
		helpers,
		pagination,
	):
		monkeypatch.setattr(module, "frappe", f, raising=False)
	f.add("Provider Account", name="DO-STAGING", provider="digitalocean", is_staging=1)
	f.add(
		"Server",
		name="SRV-0001",
		hostname="app-01",
		provider="digitalocean",
		provider_account="DO-STAGING",
		status="Active",
		provider_ref="1",
	)
	f.add(
		"Bench",
		name="BENCH-0001",
		title="frappe-bench",
		provider="digitalocean",
		provider_account="DO-STAGING",
		provider_ref="SRV-0001:/home/frappe/frappe-bench",
		server="SRV-0001",
		path="/home/frappe/frappe-bench",
		frappe_version="15.98.1",
		apps=[
			{
				"app": "frappe",
				"version": "15.98.1",
				"branch": "version-15",
				"commit": "a1b2c3d4e5f6",
				"remote": "https://github.com/frappe/frappe",
			},
			{
				"app": "erpnext",
				"version": "15.95.2",
				"branch": "version-15",
				"commit": "f6e5d4c3b2a1",
				"remote": "https://github.com/frappe/erpnext",
			},
			{
				"app": "custom",
				"version": "1.0.0",
				"branch": "main",
				"commit": "123456789abc",
				"remote": "https://gitlab.com/x/custom.git",
			},
		],
	)
	monkeypatch.setattr(ser, "system_timezone", lambda: "UTC")
	monkeypatch.setattr(audit, "now_datetime", lambda: f.now())
	gh = _Gh()
	monkeypatch.setattr(updates, "client", lambda: gh)
	f.gh = gh  # type: ignore[attr-defined]
	return f


def test_check_bench_marks_behind_apps_and_leaves_non_github_unknown(ff: FakeFrappe) -> None:
	rows = updates.check_bench("BENCH-0001")
	by = {r["app"]: r for r in rows}
	assert by["frappe"]["behind"] == 3 and by["frappe"]["latest_tag"] == "v15.101.0"
	assert by["erpnext"]["behind"] == 0  # already at the upstream tip: no compare call
	assert by["custom"]["upstream_commit"] is None and by["custom"]["checked_at"] is None
	assert "compare frappe/erpnext f6e5d4c3b2a1 version-15" not in ff.gh.calls  # type: ignore[attr-defined]
	states = {a["app"]: a["update_state"] for a in (ser.installed_app(r) for r in rows)}
	assert states == {"frappe": "update_available", "erpnext": "up_to_date", "custom": "unknown"}


def test_check_updates_endpoint_returns_the_bench_detail_and_audits(ff: FakeFrappe) -> None:
	status, body = call(benches.check_updates, bench="BENCH-0001")
	assert status == 200, (body, ff.errors[-1:])
	validate("benches.check_updates", body)
	assert {a["app"]: a["update_state"] for a in body["apps"]}["frappe"] == "update_available"
	assert any(r["action"] == "bench.check_updates" for r in ff.get_all("Infra Audit Log", fields=["action"]))
	status, body = call(benches.check_updates, bench="NOPE")
	assert status == 404


def test_refs_endpoint_lists_upstream_versions_and_refuses_non_github(ff: FakeFrappe) -> None:
	status, body = call(benches.refs, bench="BENCH-0001", app="erpnext")
	assert status == 200, body
	validate("benches.refs", body)
	assert [r["name"] for r in body["items"]] == ["version-15", "v15.101.0"]
	status, body = call(benches.refs, bench="BENCH-0001", app="custom")
	assert status == 400
	status, body = call(benches.refs, bench="BENCH-0001", app="missing")
	assert status == 404


def test_benches_list_carries_the_update_fields(ff: FakeFrappe) -> None:
	updates.check_bench("BENCH-0001")
	status, body = call(benches.list)
	assert status == 200, body
	validate("benches.list", body)
	assert body["items"], (body, ff.errors[-1:])
	assert body["items"][0]["apps"][0]["upstream_commit"] == "f6e5d4c3b2a1"


# --- discovery script ------------------------------------------------------------------------
def _discover_module() -> Any:
	path = REPO / "ansible" / "playbooks" / "files" / "discover_bench.py"
	spec = importlib.util.spec_from_file_location("discover_bench", path)
	assert spec and spec.loader
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def test_discovery_reports_commit_and_token_free_remote(tmp_path: Path) -> None:
	bench = tmp_path / "frappe-bench"
	app = bench / "apps" / "erpnext"
	(app / "erpnext").mkdir(parents=True)
	(app / "erpnext" / "__init__.py").write_text('__version__ = "15.95.2"\n')
	git = app / ".git"
	(git / "refs" / "heads").mkdir(parents=True)
	(git / "HEAD").write_text("ref: refs/heads/version-15\n")
	(git / "refs" / "heads" / "version-15").write_text("f6e5d4c3b2a1deadbeefcafe\n")
	(git / "config").write_text(
		'[core]\n\tbare = false\n[remote "upstream"]\n\turl = https://x-access-token:ghp_secret@github.com/frappe/erpnext.git\n\tfetch = +refs/heads/*:refs/remotes/upstream/*\n'
	)
	(bench / "sites").mkdir()
	(bench / "sites" / "apps.txt").write_text("erpnext\n")
	mod = _discover_module()
	rows = mod.apps_of(str(bench))
	assert rows == [
		{
			"app": "erpnext",
			"version": "15.95.2",
			"branch": "version-15",
			"commit": "f6e5d4c3b2a1",
			"remote": "https://github.com/frappe/erpnext.git",
		}
	]
	# packed refs and a detached HEAD
	os.remove(git / "refs" / "heads" / "version-15")
	(git / "packed-refs").write_text("# pack-refs\n0123456789abcdef refs/heads/version-15\n")
	assert mod.app_commit(str(app)) == "0123456789ab"
	(git / "HEAD").write_text("deadbeefdeadbeef\n")
	assert mod.app_commit(str(app)) == "deadbeefdead"


# --- bulk preflight ------------------------------------------------------------------------
def test_preflight_reports_each_check_per_target(ff: FakeFrappe) -> None:
	ff.add(
		"Playbook",
		name="site.migrate",
		title="Migrate site",
		target_doctype="Site",
		risk="medium",
		enabled=1,
		required_capability="ssh",
		description="x",
	)
	ff.add(
		"Playbook",
		name="bench.update",
		title="Update bench apps",
		target_doctype="Bench",
		risk="medium",
		enabled=1,
		required_capability="ssh",
		description="x",
	)
	ff.add(
		"Site",
		name="a.iq",
		domain="a.iq",
		provider="digitalocean",
		provider_account="DO-STAGING",
		bench="BENCH-0001",
		server="SRV-0001",
		status="Active",
		last_backup=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=3),
	)
	ff.add(
		"Site",
		name="b.iq",
		domain="b.iq",
		provider="digitalocean",
		provider_account="DO-STAGING",
		bench="BENCH-0001",
		server="SRV-0001",
		status="Broken",
		last_backup=None,
	)
	status, body = call(
		bulk.preflight,
		playbook="site.migrate",
		targets=[
			{"target_doctype": "Site", "target_name": "a.iq"},
			{"target_doctype": "Site", "target_name": "b.iq"},
			{"target_doctype": "Site", "target_name": "ghost.iq"},
			{"target_doctype": "Bench", "target_name": "BENCH-0001"},
		],
	)
	assert status == 200, body
	validate("bulk.preflight", body)
	by = {i["target_name"]: i for i in body["items"]}
	assert (
		by["a.iq"]["ok"] is True and {c["id"]: c["status"] for c in by["a.iq"]["checks"]}["backup"] == "pass"
	)
	checks_b = {c["id"]: c["status"] for c in by["b.iq"]["checks"]}
	assert by["b.iq"]["ok"] is False and checks_b["status"] == "fail" and checks_b["backup"] == "warn"
	assert by["ghost.iq"]["ok"] is False and by["ghost.iq"]["checks"][0]["id"] == "exists"
	assert {c["id"]: c["status"] for c in by["BENCH-0001"]["checks"]}["playbook_target"] == "fail"
	assert body["summary"] == {"ok": 1, "warn": 0, "fail": 3}
	status, body = call(
		bulk.preflight,
		playbook="bench.update",
		targets=[{"target_doctype": "Bench", "target_name": "BENCH-0001"}],
	)
	assert status == 200 and body["items"][0]["ok"] is True
	status, body = call(
		bulk.preflight, playbook="nope", targets=[{"target_doctype": "Site", "target_name": "a.iq"}]
	)
	assert status == 404
