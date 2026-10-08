"""A2.5: the hourly scheduler enqueues one inventory.sync per enabled account, skips busy ones."""

from __future__ import annotations

from typing import Any

import pytest
from fake_frappe import FakeFrappe

from infra_control.core.errors import ValidationError
from infra_control.inventory import schedule


@pytest.fixture
def ff(monkeypatch: pytest.MonkeyPatch) -> FakeFrappe:
	f = FakeFrappe()
	monkeypatch.setattr(schedule, "frappe", f)
	monkeypatch.setattr(schedule.engine, "frappe", f)
	f.add("Provider Account", name="DO-STAGING", enabled=1)
	f.add("Provider Account", name="FC-STAGING", enabled=1)
	f.add("Provider Account", name="OLD", enabled=0)
	return f


def test_one_job_per_enabled_account_skipping_busy_ones(
	ff: FakeFrappe, monkeypatch: pytest.MonkeyPatch
) -> None:
	# DO-STAGING already has a running sync; FC-STAGING is free; OLD is disabled.
	ff.add("Infra Job", name="JOB-1", playbook="inventory.sync", target_name="DO-STAGING", status="Running")
	created: list[tuple[str, str, str]] = []

	def fake_create(playbook: str, dt: str, name: str, *a: Any, **kw: Any) -> Any:
		created.append((playbook, dt, name))
		return ff.add(
			"Infra Job", name=f"JOB-new-{name}", playbook=playbook, target_name=name, status="Queued"
		)

	monkeypatch.setattr(schedule.engine, "create_job", fake_create)
	names = schedule.sync_all_providers()
	assert created == [("inventory.sync", "Provider Account", "FC-STAGING")]
	assert names == ["JOB-new-FC-STAGING"]


def test_one_failing_account_does_not_stop_the_rest(ff: FakeFrappe, monkeypatch: pytest.MonkeyPatch) -> None:
	def fake_create(playbook: str, dt: str, name: str, *a: Any, **kw: Any) -> Any:
		if name == "DO-STAGING":
			raise ValidationError("boom", {})
		return ff.add("Infra Job", name=f"JOB-{name}", playbook=playbook, target_name=name, status="Queued")

	monkeypatch.setattr(schedule.engine, "create_job", fake_create)
	names = schedule.sync_all_providers()
	assert names == ["JOB-FC-STAGING"]
	assert any("not scheduled for DO-STAGING" in e for e in ff.errors)
