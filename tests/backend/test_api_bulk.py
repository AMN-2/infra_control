"""A3.4: the bulk API handlers parse input, enforce the contract shapes and drive the engine."""

from __future__ import annotations

import builtins
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from fake_frappe import FakeFrappe
from jsonschema import Draft202012Validator, FormatChecker

import infra_control.api as api_pkg
from infra_control.api import _pagination, _serialize
from infra_control.api import bulk as bulk_api
from infra_control.bulk import engine as bulk_engine
from infra_control.bulk import health
from infra_control.core import audit, permissions
from infra_control.core.enums import BulkStatus
from infra_control.job_engine import engine as jobs
from infra_control.job_engine import realtime

REPO = Path(__file__).resolve().parents[2]
with (REPO / "contracts" / "openapi.yaml").open() as fh:
	SPEC = yaml.safe_load(fh)
BASE = "/api/method/infra_control.api."


def validate(fn: str, payload: dict[str, Any], status: str = "200") -> None:
	op = next(v for k, v in SPEC["paths"][BASE + fn].items() if k in ("get", "post"))
	resp = op["responses"][status]
	if "$ref" in resp:
		resp = SPEC["components"]["responses"][resp["$ref"].rsplit("/", 1)[1]]
	schema = resp["content"]["application/json"]["schema"]
	wrapped = {"$id": "urn:openapi", "components": SPEC["components"], "allOf": [schema]}
	errors = sorted(
		Draft202012Validator(wrapped, format_checker=FormatChecker()).iter_errors(
			json.loads(json.dumps(payload, default=str))
		),
		key=lambda e: list(e.path),
	)
	assert not errors, f"{fn}: " + "; ".join(f"{list(e.path)}: {e.message}" for e in errors[:5])


@pytest.fixture
def ff(monkeypatch: pytest.MonkeyPatch) -> FakeFrappe:
	f = FakeFrappe()
	for module in (
		api_pkg,
		bulk_api,
		bulk_engine,
		_pagination,
		_serialize,
		jobs,
		realtime,
		audit,
		permissions,
		health,
	):
		monkeypatch.setattr(module, "frappe", f, raising=False)
	monkeypatch.setattr(_serialize, "system_timezone", lambda: "UTC")
	monkeypatch.setattr(bulk_engine, "now_datetime", f.now)
	monkeypatch.setattr(audit, "now_datetime", f.now)

	def fake_create_job(playbook: str, target_doctype: str, target_name: str, *a: Any, **kw: Any) -> Any:
		return f.add(
			"Infra Job",
			playbook=playbook,
			target_doctype=target_doctype,
			target_name=target_name,
			status="Queued",
			triggered_by=kw.get("user"),
			bulk_operation=kw.get("bulk_operation"),
		)

	def fake_run_job(job_name: str) -> None:
		f.get_doc("Infra Job", job_name).db_set("status", "Success")

	monkeypatch.setattr(jobs, "create_job", fake_create_job)
	monkeypatch.setattr(jobs, "run_job", fake_run_job)

	f.add(
		"Playbook",
		name="site.migrate",
		key="site.migrate",
		title="Migrate site",
		target_doctype="Site",
		risk="medium",
		enabled=1,
	)
	f.add(
		"Playbook",
		name="site.backup",
		key="site.backup",
		title="Backup site",
		target_doctype="Site",
		risk="low",
		enabled=1,
	)
	f.add("Provider Account", name="DO", provider="digitalocean")
	f.add("Server", name="SRV-1", provider_account="DO", provider="digitalocean")
	for i in (1, 2, 3):
		f.add(
			"Site",
			name=f"s{i}.iq",
			domain=f"s{i}.iq",
			provider_account="DO",
			provider="digitalocean",
			server="SRV-1",
		)
	return f


def call(fn: Any, **kwargs: Any) -> tuple[int, dict[str, Any]]:
	fn.handler(**kwargs)
	body = dict(api_pkg.frappe.local.response)
	status = body.pop("http_status_code")
	api_pkg.frappe.local.response = type(api_pkg.frappe.local.response)({"docs": []})
	return status, body


def _targets() -> list[dict[str, str]]:
	return [{"target_doctype": "Site", "target_name": f"s{i}.iq"} for i in (1, 2, 3)]


def test_create_get_and_drive_to_success(ff: FakeFrappe) -> None:
	status, body = call(
		bulk_api.create,
		playbook="site.migrate",
		targets=_targets(),
		canary_target={"target_doctype": "Site", "target_name": "s1.iq"},
		batch_size=5,
		failure_policy="halt",
		params={"_skip_health": 1},
	)
	assert status == 200
	validate("bulk.create", body)
	name = body["bulk"]["name"]
	assert body["bulk"]["status"] == "Queued" and body["bulk"]["total"] == 3
	assert body["bulk"]["canary_target"] == {"target_doctype": "Site", "target_name": "s1.iq"}
	assert body["bulk"]["batches_total"] == 1

	status, body = call(bulk_api.get, bulk=name)
	validate("bulk.get", body)
	assert {t["target_name"]: t["batch"] for t in body["targets"]} == {"s1.iq": 0, "s2.iq": 1, "s3.iq": 1}

	# Drive to completion through the engine, then the detail reports Success.
	for _ in range(30):
		if BulkStatus(ff.get_doc("Bulk Operation", name).status) in bulk_engine.TERMINAL_BULK_STATUSES:
			break
		bulk_engine.drive(name)
	status, body = call(bulk_api.get, bulk=name)
	validate("bulk.get", body)
	assert body["status"] == "Success" and body["done"] == 3


def test_create_rejects_bad_input(ff: FakeFrappe) -> None:
	# Missing playbook.
	assert (
		call(
			bulk_api.create,
			targets=_targets(),
			canary_target={"target_doctype": "Site", "target_name": "s1.iq"},
		)[0]
		== 400
	)
	# Canary is not one of the targets.
	status, body = call(
		bulk_api.create,
		playbook="site.migrate",
		targets=_targets(),
		canary_target={"target_doctype": "Site", "target_name": "other.iq"},
	)
	assert status == 400 and body["error"]["code"] == "validation_error"
	# batch_size out of range.
	assert (
		call(
			bulk_api.create,
			playbook="site.migrate",
			targets=_targets(),
			canary_target={"target_doctype": "Site", "target_name": "s1.iq"},
			batch_size=999,
		)[0]
		== 400
	)
	# Unknown playbook.
	assert (
		call(
			bulk_api.create,
			playbook="ghost",
			targets=_targets(),
			canary_target={"target_doctype": "Site", "target_name": "s1.iq"},
		)[0]
		== 404
	)


def test_pause_resume_cancel_shapes_and_guards(ff: FakeFrappe) -> None:
	_, body = call(
		bulk_api.create,
		playbook="site.migrate",
		targets=_targets(),
		canary_target={"target_doctype": "Site", "target_name": "s1.iq"},
		params={"_skip_health": 1},
	)
	name = body["bulk"]["name"]
	status, body = call(bulk_api.pause, bulk=name)
	assert status == 200 and body["bulk"]["name"] == name
	validate("bulk.pause", body)
	status, body = call(bulk_api.cancel, bulk=name)
	assert status == 200 and body["bulk"]["status"] == "Cancelled"
	validate("bulk.cancel", body)
	# Resume is invalid from Cancelled.
	status, body = call(bulk_api.resume, bulk=name)
	assert status == 409 and body["error"]["code"] == "invalid_state"


def test_targets_accept_json_strings(ff: FakeFrappe) -> None:
	# Frappe may pass body params as JSON strings; the handler parses them.
	status, body = call(
		bulk_api.create,
		playbook="site.migrate",
		targets=json.dumps(_targets()),
		canary_target=json.dumps({"target_doctype": "Site", "target_name": "s1.iq"}),
		params=json.dumps({"_skip_health": 1}),
	)
	assert status == 200
	validate("bulk.create", body)


def test_list_pages_newest_first_and_filters_by_status(ff: FakeFrappe) -> None:
	names: builtins.list[str] = []
	for canary in ("s1.iq", "s2.iq"):
		status, body = call(
			bulk_api.create,
			playbook="site.backup",
			targets=[{"target_doctype": "Site", "target_name": canary}],
			canary_target={"target_doctype": "Site", "target_name": canary},
		)
		assert status == 200
		names.append(body["bulk"]["name"])
	status, page = call(bulk_api.list)
	assert status == 200
	validate("bulk.list", page)
	assert [b["name"] for b in page["items"]] == list(reversed(names))
	assert page["next_cursor"] is None
	status, page = call(bulk_api.list, status="Success")
	assert status == 200 and page["items"] == []
	status, page = call(bulk_api.list, limit=1)
	assert status == 200 and len(page["items"]) == 1 and page["next_cursor"]
