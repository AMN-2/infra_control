"""A2.3: site operations on DigitalOcean. Adapter behaviour (presigned URLs, DNS, recording on
success) and the structure of the shipped site playbooks (backup before migrate, no secrets in
logs). No network, no Frappe site, no Ansible process."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import responses
import yaml
from test_digitalocean import SERVER, FakeRecords, _FakeRunner, adapter, url

from infra_control.core.errors import NotFound, ProviderError
from infra_control.providers.base import OpState
from infra_control.providers.digitalocean.adapter import BENCH_PLAYBOOKS, SITE_PLAYBOOKS
from infra_control.providers.digitalocean.ansible import default_playbooks_dir

PLAYBOOKS = default_playbooks_dir()
STAMP = "19700112_134640"  # the adapter clock in test_digitalocean is 1_000_000 s


def finish(runner: _FakeRunner) -> None:
	"""Make the fake runner report success on the next poll."""
	runner.polls = 5


# --- adapter ---------------------------------------------------------------------------------
def test_backup_hands_the_server_presigned_urls_and_records_each_uploaded_file() -> None:
	runner, records = _FakeRunner(), FakeRecords()
	a = adapter(runner, records=records)
	ref = a.call("backup_site", site="demo.iq", with_files=True)
	extra = runner.started[0][2]
	assert sorted(extra["backup_urls"]) == ["database", "private", "public"]
	assert extra["backup_urls"]["database"].startswith(
		f"https://signed/put_object/demo.iq/{STAMP}-database.sql.gz?"
	)
	assert "AK" not in str(extra) and "SK" not in str(extra)

	assert a.get_status(ref).state is OpState.RUNNING
	assert records.calls == []
	# The server uploaded the database and public files; this site has no private files.
	records.s3.objects[f"demo.iq/{STAMP}-database.sql.gz"] = 96 * 1024 * 1024
	records.s3.objects[f"demo.iq/{STAMP}-files.tar"] = 10 * 1024 * 1024
	finish(runner)
	assert a.get_status(ref).state is OpState.SUCCESS
	assert records.calls == [
		("backup", ("demo.iq", "db", f"spaces://scq-backups/demo.iq/{STAMP}-database.sql.gz", 96.0)),
		("backup", ("demo.iq", "files", f"spaces://scq-backups/demo.iq/{STAMP}-files.tar", 10.0)),
	]
	a.get_status(ref)  # a later poll never records twice
	assert len(records.calls) == 2


def test_backups_refuse_to_run_without_spaces() -> None:
	a = adapter(_FakeRunner(), records=FakeRecords(with_spaces=False))
	with pytest.raises(ProviderError, match="backups must leave the server"):
		a.call("backup_site", site="demo.iq")
	with pytest.raises(ProviderError, match="backups must leave the server"):
		a.call("update_site", site="demo.iq")


def test_migrate_carries_a_database_backup_and_records_it() -> None:
	runner, records = _FakeRunner(), FakeRecords()
	a = adapter(runner, records=records)
	ref = a.call("update_site", site="demo.iq", skip_search_index=True)
	server, playbook, extra = runner.started[0]
	assert playbook == "site_migrate.yml" and server["name"] == "SRV-0001"
	assert list(extra["backup_urls"]) == ["database"] and extra["skip_search_index"] is True
	records.s3.objects[f"demo.iq/{STAMP}-database.sql.gz"] = 1024 * 1024
	finish(runner)
	a.get_status(ref)
	assert [c[0] for c in records.calls] == ["backup"]


def test_failed_operations_record_nothing() -> None:
	runner, records = _FakeRunner(final=OpState.FAILED), FakeRecords()
	a = adapter(runner, records=records)
	ref = a.call("create_site", site="new.iq", bench="BENCH-0001", apps=[])
	finish(runner)
	assert a.get_status(ref).state is OpState.FAILED
	assert records.calls == []


def test_create_site_records_the_site_on_success() -> None:
	runner, records = _FakeRunner(), FakeRecords()
	a = adapter(runner, records=records)
	ref = a.call("create_site", site="new.iq", bench="BENCH-0001", apps=["erpnext"], admin_password="x" * 16)
	assert runner.started[0][2]["admin_password"] == "x" * 16  # masked by the engine, no_log in the play
	finish(runner)
	a.get_status(ref)
	assert records.calls == [("site", ("new.iq", "BENCH-0001"))]


def test_restore_downloads_through_presigned_get_urls() -> None:
	runner, records = _FakeRunner(), FakeRecords()
	records.backup_sets["BKP-7"] = {
		"db": "spaces://scq-backups/demo.iq/20261007_020011-database.sql.gz",
		"files": "spaces://scq-backups/demo.iq/20261007_020011-files.tar",
	}
	a = adapter(runner, records=records)
	a.call("restore_site", site="demo.iq", backup_ref="BKP-7")
	urls = runner.started[0][2]["restore_urls"]
	assert sorted(urls) == ["database", "public"]
	assert urls["database"].startswith("https://signed/get_object/demo.iq/20261007_020011-database.sql.gz")

	records.backup_sets["BKP-8"] = {"files": "spaces://scq-backups/demo.iq/x-files.tar"}
	with pytest.raises(ProviderError, match="no database file"):
		a.call("restore_site", site="demo.iq", backup_ref="BKP-8")


def test_restore_of_an_unknown_backup_is_not_found() -> None:
	records = FakeRecords()

	def missing(name: str) -> dict[str, str]:
		raise NotFound("Backup", name)

	records.load_backup_set = missing  # type: ignore[method-assign]  # replacing one fake method
	with pytest.raises(NotFound):
		adapter(_FakeRunner(), records=records).call("restore_site", site="demo.iq", backup_ref="nope")


@responses.activate
def test_add_domain_creates_the_a_record_when_the_zone_is_on_the_account() -> None:
	responses.get(url("domains"), json={"domains": [{"name": "iq"}, {"name": "client-a.iq"}], "links": {}})
	responses.get(
		url("domains/client-a.iq/records"),
		json={"domain_records": [{"id": 1, "type": "A", "name": "erp", "data": "10.0.0.1"}], "links": {}},
	)
	responses.delete(url("domains/client-a.iq/records/1"), status=204)
	responses.post(url("domains/client-a.iq/records"), json={"domain_record": {"id": 2}})
	runner, records = _FakeRunner(), FakeRecords()
	a = adapter(runner, records=records)
	ref = a.call("add_domain", site="demo.iq", domain="erp.client-a.iq")
	methods = [(c.request.method, (c.request.url or "").split("?")[0]) for c in responses.calls]
	assert ("DELETE", url("domains/client-a.iq/records/1")) in methods  # the longest zone wins
	created = next(c for c in responses.calls if c.request.method == "POST").request.body
	assert created is not None and b'"name": "erp"' in created and SERVER["public_ip"].encode() in created
	assert runner.started[0][2] == {
		"site": "demo.iq",
		"bench_path": "/home/frappe/v15",
		"domain": "erp.client-a.iq",
		"dns_managed": True,
	}
	finish(runner)
	a.get_status(ref)
	assert records.calls == [("domain", ("demo.iq", "erp.client-a.iq"))]


@responses.activate
def test_add_domain_leaves_dns_alone_for_foreign_zones_and_existing_records() -> None:
	responses.get(url("domains"), json={"domains": [{"name": "example.org"}], "links": {}})
	runner = _FakeRunner()
	adapter(runner).call("add_domain", site="demo.iq", domain="shop.client-b.com")
	assert runner.started[0][2]["dns_managed"] is False
	assert [c.request.method for c in responses.calls] == ["GET"]

	responses.reset()
	responses.get(url("domains"), json={"domains": [{"name": "client-a.iq"}], "links": {}})
	responses.get(
		url("domains/client-a.iq/records"),
		json={
			"domain_records": [{"id": 3, "type": "A", "name": "@", "data": SERVER["public_ip"]}],
			"links": {},
		},
	)
	runner = _FakeRunner()
	adapter(runner).call("add_domain", site="demo.iq", domain="client-a.iq")
	assert runner.started[0][2]["dns_managed"] is True
	assert [c.request.method for c in responses.calls] == ["GET", "GET"]


# --- the shipped playbooks -----------------------------------------------------------------------
def load(name: str) -> list[dict[str, Any]]:
	data = yaml.safe_load((PLAYBOOKS / name).read_text())
	assert isinstance(data, list)
	return data


def all_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
	out: list[dict[str, Any]] = []
	for t in tasks or []:
		out.append(t)
		for key in ("block", "rescue", "always"):
			out.extend(all_tasks(t.get(key) or []))
	return out


def task_files() -> list[Path]:
	return [*PLAYBOOKS.glob("site_*.yml"), *(PLAYBOOKS / "tasks").glob("*.yml")]


def test_every_site_method_has_its_playbook() -> None:
	for method, playbook in {**SITE_PLAYBOOKS, **BENCH_PLAYBOOKS}.items():
		assert (PLAYBOOKS / playbook).is_file(), method


def test_update_bench_runs_on_the_bench_server_with_its_path() -> None:
	runner = _FakeRunner()
	a = adapter(runner)
	ref = a.call("update_bench", bench="BENCH-0001", apps=["erpnext"], branch="version-15")
	server, playbook, extra = runner.started[0]
	assert playbook == "bench_update.yml" and server["name"] == "SRV-0001"
	assert extra == {
		"bench_path": "/home/frappe/v15",
		"apps": ["erpnext"],
		"branch": "version-15",
		"migrate": True,
		"build": True,
	}
	finish(runner)
	assert a.get_status(ref).state is OpState.SUCCESS


def test_bench_update_backs_up_before_migrating_and_never_resets() -> None:
	"""Plan 13.7 for updates: backup first, fail if it fails; the pull is fast-forward only."""
	names = [t.get("name", "") for t in tasks_in(PLAYBOOKS / "bench_update.yml")]
	assert names.index("Backup every site before migrating") < names.index("bench migrate")
	argv = [
		str(t.get("ansible.builtin.command", {}).get("argv", ""))
		for t in tasks_in(PLAYBOOKS / "bench_update.yml")
	]
	assert any("--ff-only" in a for a in argv) and not any("reset" in a or "--force" in a for a in argv)


SECRET_MARKERS = (
	"admin_password",
	"backup_urls[",
	"restore_urls[",
	"db_admin.stdout",
	"db-root-password",
	"openssl rand",
)


def tasks_in(path: Path) -> list[dict[str, Any]]:
	"""Every task in a playbook (plays with `tasks`) or a task file (a list of tasks)."""
	doc = yaml.safe_load(path.read_text()) or []
	out: list[dict[str, Any]] = []
	for item in doc:
		if isinstance(item, dict):
			out.extend(all_tasks(item["tasks"]) if "hosts" in item else all_tasks([item]))
	return out


def test_tasks_that_touch_secrets_are_no_log() -> None:
	"""Presigned URLs, the admin password and the database admin password must never reach the
	job events (and so the job log)."""
	offenders = []
	for path in [*task_files(), *(PLAYBOOKS.parent / "roles").rglob("tasks/*.yml")]:
		for t in tasks_in(path):
			if "block" in t or "ansible.builtin.debug" in t:
				continue
			body = yaml.safe_dump({k: v for k, v in t.items() if k != "name"})
			if any(m in body for m in SECRET_MARKERS) and not t.get("no_log"):
				offenders.append(f"{path.name}: {t.get('name')}")
	assert offenders == []


def test_migrate_backs_up_before_touching_the_site() -> None:
	(play,) = load("site_migrate.yml")
	names = [t.get("name") for t in play["tasks"]]
	assert names.index("Backup before migrating") < names.index("Migrate under maintenance")
	backup = play["tasks"][names.index("Backup before migrating")]
	assert backup["ansible.builtin.include_tasks"] == "tasks/backup_upload.yml"
	assert "ignore_errors" not in backup and "failed_when" not in backup
	migrate = play["tasks"][names.index("Migrate under maintenance")]
	assert [t["name"] for t in migrate["always"]] == ["Disable maintenance mode"]


def test_backup_tasks_fail_hard() -> None:
	tasks = yaml.safe_load((PLAYBOOKS / "tasks" / "backup_upload.yml").read_text())
	for t in tasks:
		assert not t.get("ignore_errors"), t["name"]
	upload = next(t for t in tasks if t["name"] == "Upload to Spaces")
	assert "--fail" in upload["ansible.builtin.command"]["argv"]


def test_site_playbooks_run_as_frappe_with_preflight() -> None:
	for path in PLAYBOOKS.glob("site_*.yml"):
		(play,) = load(path.name)
		assert play["become_user"] == "frappe", path.name
		assert play["tasks"][0]["ansible.builtin.include_tasks"] == "tasks/site_preflight.yml", path.name


def test_site_playbooks_can_find_system_binaries() -> None:
	"""Live gate JOB-00008: nginx lives in /usr/sbin, which the play PATH left out."""
	for path in PLAYBOOKS.glob("site_*.yml"):
		(play,) = load(path.name)
		dirs = play["environment"]["PATH"].split(":")
		assert "/usr/sbin" in dirs and "/home/frappe/.local/bin" in dirs, path.name
