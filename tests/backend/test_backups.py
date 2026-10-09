"""A4.2: backup scheduling (pure next-run arithmetic, due detection, job creation on the
fake), retention pruning, and the backups API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from fake_frappe import FakeFrappe
from test_api import call, validate

import infra_control.api as api_pkg
from infra_control.api import _pagination, _serialize
from infra_control.api import backups as backups_api
from infra_control.backups import retention, schedule
from infra_control.core import permissions


def test_next_run_arithmetic() -> None:
	t = datetime(2026, 10, 9, 13, 20)
	assert schedule.next_run_after("hourly", 0, "sun", t) == datetime(2026, 10, 9, 14, 0)
	assert schedule.next_run_after("daily", 2, "sun", t) == datetime(2026, 10, 10, 2, 0)
	assert schedule.next_run_after("daily", 15, "sun", t) == datetime(2026, 10, 9, 15, 0)
	# 2026-10-09 is a Friday: next Sunday 02:00, and next Friday when today's hour has passed.
	assert schedule.next_run_after("weekly", 2, "sun", t) == datetime(2026, 10, 11, 2, 0)
	assert schedule.next_run_after("weekly", 2, "fri", t) == datetime(2026, 10, 16, 2, 0)
	assert schedule.next_run_after("weekly", 23, "fri", t) == datetime(2026, 10, 9, 23, 0)
	assert schedule.is_due({"enabled": 1, "next_run": None}, t)
	assert schedule.is_due({"enabled": 1, "next_run": "2026-10-09 13:00:00"}, t)
	assert not schedule.is_due({"enabled": 1, "next_run": "2026-10-09 14:00:00"}, t)
	assert not schedule.is_due({"enabled": 0, "next_run": None}, t)


def test_to_prune_keeps_the_newest_per_kind() -> None:
	rows = [
		{"name": "a", "kind": "db", "created_at": "2026-10-01"},
		{"name": "b", "kind": "db", "created_at": "2026-10-03"},
		{"name": "c", "kind": "db", "created_at": "2026-10-02"},
		{"name": "f1", "kind": "files", "created_at": "2026-10-01"},
		{"name": "f2", "kind": "files", "created_at": "2026-10-02"},
	]
	assert [r["name"] for r in retention.to_prune(rows, 1)] == ["a", "c", "f1"]
	assert retention.to_prune(rows, 0) == [] and retention.to_prune(rows, 5) == []


@pytest.fixture
def ff(monkeypatch: pytest.MonkeyPatch) -> FakeFrappe:
	f = FakeFrappe()
	for module in (api_pkg, _pagination, _serialize, backups_api, schedule, retention, permissions):
		monkeypatch.setattr(module, "frappe", f)
	monkeypatch.setattr(_serialize, "system_timezone", lambda: "UTC")
	monkeypatch.setattr(backups_api, "now_datetime", f.now)
	monkeypatch.setattr(schedule, "now_datetime", f.now)
	monkeypatch.setattr(
		schedule, "get_datetime", lambda v: v if hasattr(v, "year") else datetime.fromisoformat(str(v))
	)
	f.add(
		"Site",
		name="demo.iq",
		domain="demo.iq",
		status="Active",
		bench="BENCH-0001",
		server="SRV-0001",
		provider="digitalocean",
		provider_account="DO",
	)
	return f


def test_policy_roundtrip_and_backup_list(ff: FakeFrappe) -> None:
	status, body = call(backups_api.policy, site="demo.iq")
	assert status == 200 and body == {"policy": None}
	validate("backups.policy", body)
	status, body = call(
		backups_api.set_policy,
		site="demo.iq",
		frequency="weekly",
		hour=3,
		weekday="sat",
		with_files=False,
		retain=7,
	)
	assert status == 200
	validate("backups.set_policy", body)
	p = body["policy"]
	assert (p["frequency"], p["hour"], p["weekday"], p["with_files"], p["retain"], p["enabled"]) == (
		"weekly",
		3,
		"sat",
		False,
		7,
		True,
	)
	assert p["next_run"] is not None and p["last_run"] is None
	status, body = call(backups_api.set_policy, site="demo.iq", enabled=False)
	assert body["policy"]["enabled"] is False and body["policy"]["frequency"] == "daily"
	assert len(ff.store["Backup Policy"]) == 1
	status, body = call(backups_api.set_policy, site="nope")
	assert status == 404
	for i in range(3):
		ff.add(
			"Backup",
			name=f"BKP-{i}",
			site="demo.iq",
			kind="db" if i < 2 else "files",
			location=f"spaces://b/demo.iq/{i}-database.sql.gz",
			size_mb=1.5,
			created_at=f"2026-10-0{i + 1} 02:00:00",
		)
	status, body = call(backups_api.list, site="demo.iq", kind="db", limit=1)
	assert status == 200
	validate("backups.list", body)
	assert len(body["items"]) == 1 and body["next_cursor"]
	status, body = call(backups_api.list, site="demo.iq", cursor=body["next_cursor"], limit=10)
	assert [b["name"] for b in body["items"]] == ["BKP-1", "BKP-2"]


def test_due_policies_create_backup_jobs_once_and_skip_busy_sites(
	ff: FakeFrappe, monkeypatch: pytest.MonkeyPatch
) -> None:
	created: list[tuple[str, str, dict[str, Any]]] = []

	class _Job:
		name = "JOB-1"

	monkeypatch.setattr(
		schedule.engine,
		"create_job",
		lambda pb, dt, name, params, **kw: created.append((pb, name, params)) or _Job(),
	)
	ff.add(
		"Backup Policy",
		name="demo.iq",
		site="demo.iq",
		enabled=1,
		frequency="daily",
		hour=2,
		weekday="sun",
		with_files=1,
		retain=14,
		next_run=None,
	)
	ff.add(
		"Site",
		name="busy.iq",
		domain="busy.iq",
		status="Active",
		bench="BENCH-0001",
		server="SRV-0001",
		provider="digitalocean",
		provider_account="DO",
	)
	ff.add(
		"Backup Policy",
		name="busy.iq",
		site="busy.iq",
		enabled=1,
		frequency="hourly",
		hour=0,
		weekday="sun",
		with_files=0,
		retain=0,
		next_run=None,
	)
	ff.add(
		"Infra Job",
		name="JOB-9",
		playbook="site.migrate",
		target_doctype="Site",
		target_name="busy.iq",
		status="Running",
	)
	result = schedule.run_due_policies()
	assert result == {"started": 1, "skipped_busy": 1, "failed": 0}
	assert created == [("site.backup", "demo.iq", {"with_files": True})]
	policy = ff.store["Backup Policy"]["demo.iq"]
	assert policy.get("last_job") == "JOB-1" and policy.get("next_run") > ff.now()
	# Not due again until next_run passes.
	assert schedule.run_due_policies()["started"] == 0


def test_retention_deletes_objects_then_records(ff: FakeFrappe, monkeypatch: pytest.MonkeyPatch) -> None:
	deleted: list[str] = []

	class _Spaces:
		def delete(self, key: str) -> None:
			if key.endswith("broken"):
				raise RuntimeError("spaces down")
			deleted.append(key)

	monkeypatch.setattr(retention.settings, "spaces_client", lambda: _Spaces())
	ff.add(
		"Backup Policy",
		name="demo.iq",
		site="demo.iq",
		enabled=1,
		frequency="daily",
		hour=2,
		weekday="sun",
		with_files=1,
		retain=1,
		next_run=None,
	)
	ff.add(
		"Backup",
		name="old",
		site="demo.iq",
		kind="db",
		location="spaces://b/demo.iq/old-database.sql.gz",
		created_at="2026-10-01 02:00:00",
	)
	ff.add(
		"Backup",
		name="broken",
		site="demo.iq",
		kind="db",
		location="spaces://b/demo.iq/broken",
		created_at="2026-10-02 02:00:00",
	)
	ff.add(
		"Backup",
		name="new",
		site="demo.iq",
		kind="db",
		location="spaces://b/demo.iq/new-database.sql.gz",
		created_at="2026-10-03 02:00:00",
	)
	assert retention.prune() == {"deleted": 1, "kept_on_error": 1}
	assert deleted == ["demo.iq/old-database.sql.gz"]
	assert set(ff.store["Backup"]) == {"broken", "new"}
