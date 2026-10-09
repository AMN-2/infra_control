"""A4: security posture + 2FA switch, restore-test scheduling, controller off-site backup
helpers, and the adapter's restore test."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fake_frappe import FakeFrappe
from test_api import call, validate
from test_digitalocean import FakeRecords, _FakeRunner, adapter

import infra_control.api as api_pkg
from infra_control.api import security
from infra_control.backups import controller, restore_test
from infra_control.core import audit, permissions, secrets
from infra_control.providers.base import OpState


@pytest.fixture
def ff(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FakeFrappe:
	f = FakeFrappe()
	for module in (api_pkg, security, audit, permissions, secrets, restore_test):
		monkeypatch.setattr(module, "frappe", f, raising=False)
	monkeypatch.setattr(audit, "now_datetime", f.now)
	monkeypatch.setattr(restore_test, "now_datetime", f.now)
	monkeypatch.setattr(restore_test, "get_datetime", lambda v: v)
	key = tmp_path / "id_ed25519"
	key.write_text("k")
	key.chmod(0o600)
	f.conf["infra_ssh_private_key"] = str(key)
	monkeypatch.setenv("INFRA_CONSOLE_CA_DIR", str(tmp_path / "ca"))
	f.singles["System Settings"] = {
		"enable_two_factor_auth": 0,
		"two_factor_method": None,
		"enable_scheduler": 1,
	}
	f.singles["Infra Settings"] = {
		"spaces_bucket": "b",
		"spaces_key": "AKIASEEDED0001",
		"spaces_secret": "seededspacessecret",
	}
	f.add("Role", name="Infra Admin", two_factor_auth=0)
	f.add("Role", name="Infra Operator", two_factor_auth=0)
	f.add("Has Role", name="hr1", parent="ameen@x", parenttype="User", role="Infra Admin")
	f.add("User", name="ameen@x", api_key=None)
	f.add("Site", name="demo.iq", domain="demo.iq", status="Active")
	f.add(
		"DocPerm",
		name="dp1",
		parent="Infra Audit Log",
		parenttype="DocType",
		role="Infra Admin",
		write=0,
		delete=0,
		create=0,
	)
	return f


def test_posture_reports_each_control_and_enable_2fa_flips_it(ff: FakeFrappe) -> None:
	status, body = call(security.posture)
	assert status == 200, body
	validate("security.posture", body)
	by_id = {c["id"]: c for c in body["checks"]}
	assert by_id["2fa"]["status"] == "fail" and by_id["ssh_key"]["status"] == "pass"
	assert by_id["audit_immutable"]["status"] == "pass" and by_id["scheduler"]["status"] == "pass"
	assert by_id["backup_policies"]["status"] == "fail" and by_id["restore_test"]["status"] == "fail"
	assert by_id["controller_backup"]["status"] == "fail" and by_id["masking"]["detail"].startswith(
		"2 controller secret"
	)
	assert "AKIASEEDED0001" not in str(body)
	status, body = call(security.enable_2fa)
	assert status == 200
	validate("security.enable_2fa", body)
	assert body["two_factor"]["enabled"] is True and all(body["two_factor"]["roles"].values())
	assert ff.singles["System Settings"]["two_factor_method"] == "OTP App"
	status, body = call(security.posture)
	assert {c["id"]: c["status"] for c in body["checks"]}["2fa"] == "pass"


def test_restore_test_scheduling_and_age(ff: FakeFrappe, monkeypatch: pytest.MonkeyPatch) -> None:
	created: list[tuple[str, dict[str, Any]]] = []
	monkeypatch.setattr(
		restore_test.engine, "create_job", lambda pb, dt, name, params, **kw: created.append((name, params))
	)
	ff.add("Backup Policy", name="demo.iq", site="demo.iq", enabled=1)
	ff.add("Backup", name="BKP-1", site="demo.iq", kind="db", created_at=datetime(2026, 10, 1))
	ff.add("Backup", name="BKP-2", site="demo.iq", kind="db", created_at=datetime(2026, 10, 5))
	ff.add("Backup", name="BKP-3", site="demo.iq", kind="files", created_at=datetime(2026, 10, 9))
	assert restore_test.latest_db_backup("demo.iq") == "BKP-2"
	assert restore_test.run_monthly() == {"started": 1, "skipped_no_backup": 0, "failed": 0}
	assert created == [("demo.iq", {"backup": "BKP-2"})]
	assert restore_test.days_since_last_ok() is None
	ff.store["Backup"]["BKP-2"]._data.update(
		{"restore_test_result": "ok", "last_restore_test": ff.now() - timedelta(days=12)}
	)
	assert restore_test.days_since_last_ok() == 12


def test_controller_backup_pure_helpers(tmp_path: Path) -> None:
	assert controller.backup_argv("ops.localhost") == [
		"bench",
		"--site",
		"ops.localhost",
		"backup",
		"--with-files",
	]
	now = datetime(2026, 10, 9, tzinfo=UTC)
	keys = [
		("controller/x/20260901/a", now - timedelta(days=38)),
		("controller/x/20261008/b", now - timedelta(days=1)),
	]
	assert controller.keys_to_prune(keys, now, 30) == ["controller/x/20260901/a"]
	old = tmp_path / "old.sql.gz"
	old.write_text("x")
	import os

	os.utime(old, (1_000_000, 1_000_000))
	new = tmp_path / "new.sql.gz"
	new.write_text("y")
	assert controller.newest_files(tmp_path, now - timedelta(days=1)) == [new]


def test_adapter_restore_test_records_the_verdict_either_way() -> None:
	runner, records = _FakeRunner(), FakeRecords()
	records.backup_sets["BKP-1"] = {"db": "spaces://scq-backups/demo.iq/x-database.sql.gz"}
	a = adapter(runner, records=records)
	ref = a.call("restore_test_site", site="demo.iq", backup_ref="BKP-1")
	_server, playbook, extra = runner.started[0]
	assert (
		playbook == "site_restore_test.yml"
		and extra["probe_site"].endswith(".restore.test")
		and "database" in extra["restore_urls"]
	)
	runner.polls = 5
	assert a.get_status(ref).state is OpState.SUCCESS
	assert records.calls[-1] == ("restore_test", ("BKP-1", True))
	runner2, records2 = _FakeRunner(final=OpState.FAILED), FakeRecords()
	records2.backup_sets["BKP-1"] = {"db": "spaces://scq-backups/demo.iq/x-database.sql.gz"}
	b = adapter(runner2, records=records2)
	ref2 = b.call("restore_test_site", site="demo.iq", backup_ref="BKP-1")
	runner2.polls = 5
	assert b.get_status(ref2).state is OpState.FAILED
	assert records2.calls[-1] == ("restore_test", ("BKP-1", False))
