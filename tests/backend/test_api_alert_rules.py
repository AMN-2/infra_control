"""A3.2 API: alert_rules CRUD, contract shapes, and the per-kind update matrix + delete guard."""

from __future__ import annotations

import pytest
from fake_frappe import FakeFrappe
from test_api import call, validate

import infra_control.api as api_pkg
from infra_control.api import _pagination, _serialize, alert_rules
from infra_control.core import audit, permissions


@pytest.fixture
def ff(monkeypatch: pytest.MonkeyPatch) -> FakeFrappe:
	f = FakeFrappe()
	for module in (api_pkg, _pagination, _serialize, alert_rules, audit, permissions):
		monkeypatch.setattr(module, "frappe", f)
	monkeypatch.setattr(_serialize, "system_timezone", lambda: "UTC")
	# Built-in rules (one per non-metric kind) seeded as they are on install.
	f.add(
		"Alert Rule",
		name="RULE-HB",
		title="Heartbeat",
		kind="heartbeat",
		target_doctype="Server",
		severity="critical",
		for_minutes=5,
		enabled=1,
		builtin=1,
	)
	f.add(
		"Alert Rule",
		name="RULE-SSL",
		title="SSL expiry",
		kind="ssl_expiry",
		target_doctype="Site",
		severity="warning",
		threshold=14,
		enabled=1,
		builtin=1,
	)
	return f


def _create(ff: FakeFrappe, **overrides: object) -> tuple[int, dict[str, object]]:
	body: dict[str, object] = {
		"title": "CPU above 90%",
		"metric": "cpu",
		"operator": "gt",
		"threshold": 90,
		"for_minutes": 5,
		"severity": "warning",
		"channels": ["telegram", "email"],
	}
	body.update(overrides)
	return call(alert_rules.create, **body)


def test_create_list_get_roundtrip(ff: FakeFrappe) -> None:
	status, body = _create(ff)
	assert status == 200
	validate("alert_rules.create", body)
	name = body["rule"]["name"]
	assert body["rule"]["kind"] == "metric" and body["rule"]["target_doctype"] == "Server"
	assert body["rule"]["builtin"] is False and body["rule"]["enabled"] is True
	assert body["rule"]["channels"] == ["telegram", "email"]
	assert body["rule"]["threshold"] == 90.0 and body["rule"]["for_minutes"] == 5
	assert body["rule"]["modified_at"].endswith("Z")

	status, page = call(alert_rules.list)
	validate("alert_rules.list", page)
	assert name in [r["name"] for r in page["items"]]

	status, one = call(alert_rules.get, rule=name)
	assert status == 200
	validate("alert_rules.get", one)
	assert one["name"] == name and "rule" not in one  # bare AlertRule, not an envelope

	assert call(alert_rules.get, rule="RULE-NOPE")[0] == 404


def test_create_rejects_non_metric_kind(ff: FakeFrappe) -> None:
	status, body = _create(ff, kind="heartbeat")
	assert status == 400 and body["error"]["code"] == "validation_error"
	assert body["error"]["details"]["field"] == "kind"


def test_create_validates_required_fields_and_enums(ff: FakeFrappe) -> None:
	assert (
		call(
			alert_rules.create,
			metric="cpu",
			operator="gt",
			threshold=1,
			for_minutes=1,
			severity="warning",
			channels=["email"],
		)[0]
		== 400
	)  # no title
	assert _create(ff, metric="nope")[0] == 400
	assert _create(ff, operator="nope")[0] == 400
	assert _create(ff, channels=["sms"])[0] == 400
	assert _create(ff, threshold="x")[0] == 400
	assert _create(ff, for_minutes=5000)[0] == 400


def test_create_requires_admin(ff: FakeFrappe) -> None:
	ff.session.user = "op@x"
	ff.roles["op@x"] = ("Infra Operator",)
	status, body = _create(ff)
	assert status == 403 and body["error"]["details"]["required"] == "Infra Admin"


def test_update_edits_allowed_fields(ff: FakeFrappe) -> None:
	name = _create(ff)[1]["rule"]["name"]
	status, body = call(
		alert_rules.update,
		rule=name,
		title="CPU above 95%",
		threshold=95,
		severity="critical",
		channels=["email"],
		enabled=False,
	)
	assert status == 200
	validate("alert_rules.update", body)
	assert body["rule"]["title"] == "CPU above 95%" and body["rule"]["threshold"] == 95.0
	assert body["rule"]["severity"] == "critical" and body["rule"]["enabled"] is False
	assert body["rule"]["channels"] == ["email"]


def test_update_rejects_field_not_allowed_for_kind(ff: FakeFrappe) -> None:
	# ssl_expiry: only threshold (+ the always-editable fields) may change; metric/operator/for_minutes may not.
	status, body = call(alert_rules.update, rule="RULE-SSL", metric="cpu")
	assert status == 400 and body["error"]["details"]["field"] == "metric"
	assert call(alert_rules.update, rule="RULE-SSL", for_minutes=10)[0] == 400
	# heartbeat: for_minutes allowed, threshold not.
	assert call(alert_rules.update, rule="RULE-HB", threshold=3)[0] == 400
	# ssl_expiry threshold and always-editable fields are accepted.
	status, body = call(alert_rules.update, rule="RULE-SSL", threshold=30, title="SSL soon")
	assert status == 200 and body["rule"]["threshold"] == 30.0 and body["rule"]["title"] == "SSL soon"
	assert call(alert_rules.update, rule="RULE-NOPE", title="x")[0] == 404


def test_delete_metric_rule_but_reject_builtin(ff: FakeFrappe) -> None:
	name = _create(ff)[1]["rule"]["name"]
	status, body = call(alert_rules.delete, rule=name)
	assert status == 200 and body == {"rule": name, "deleted": True}
	assert name not in ff.store.get("Alert Rule", {})
	status, body = call(alert_rules.delete, rule="RULE-HB")
	assert status == 409 and body["error"]["code"] == "invalid_state"
	assert "RULE-HB" in ff.store["Alert Rule"]  # kept
	assert call(alert_rules.delete, rule="RULE-NOPE")[0] == 404


def test_delete_requires_admin(ff: FakeFrappe) -> None:
	name = _create(ff)[1]["rule"]["name"]
	ff.session.user = "op@x"
	ff.roles["op@x"] = ("Infra Operator",)
	status, body = call(alert_rules.delete, rule=name)
	assert status == 403 and body["error"]["details"]["required"] == "Infra Admin"
