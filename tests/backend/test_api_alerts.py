"""A3.2 API: alerts.list (firing-first ordering + cursor) and alerts.ack, in the contract shape."""

from __future__ import annotations

from datetime import timedelta

import pytest
from fake_frappe import FakeFrappe
from test_api import call, validate

import infra_control.api as api_pkg
from infra_control.api import _pagination, _serialize, alerts
from infra_control.core import audit, permissions


@pytest.fixture
def ff(monkeypatch: pytest.MonkeyPatch) -> FakeFrappe:
	f = FakeFrappe()
	for module in (api_pkg, _pagination, _serialize, alerts, audit, permissions):
		monkeypatch.setattr(module, "frappe", f)
	monkeypatch.setattr(_serialize, "system_timezone", lambda: "UTC")
	monkeypatch.setattr(alerts, "now_datetime", f.now)
	monkeypatch.setattr(audit, "now_datetime", f.now)
	f.add("Alert Rule", name="RULE-0003", title="Disk high", kind="metric", severity="warning")
	t = f.clock
	# fired_at chosen so firing-first (not newest overall) is observable: the acknowledged alert
	# is the newest of all, yet must sort after both firing alerts.
	specs = [
		("ALERT-FOLD", "firing", "warning", "SRV-1", t + timedelta(minutes=1)),
		("ALERT-FNEW", "firing", "critical", "SRV-2", t + timedelta(minutes=3)),
		("ALERT-ACK", "acknowledged", "info", "SRV-3", t + timedelta(minutes=5)),
		("ALERT-RES", "resolved", "warning", "SRV-4", t + timedelta(minutes=2)),
	]
	for name, status, severity, target, fired_at in specs:
		f.add(
			"Alert",
			name=name,
			rule="RULE-0003",
			rule_title="Disk high",
			kind="metric",
			severity=severity,
			status=status,
			target_doctype="Server",
			target_name=target,
			metric="disk",
			value=90.0,
			message="Disk usage high",
			fired_at=fired_at,
		)
	return f


def test_list_orders_firing_first_then_newest(ff: FakeFrappe) -> None:
	status, body = call(alerts.list)
	assert status == 200
	validate("alerts.list", body)
	assert [a["name"] for a in body["items"]] == ["ALERT-FNEW", "ALERT-FOLD", "ALERT-ACK", "ALERT-RES"]
	assert body["next_cursor"] is None


def test_list_cursor_paginates_across_the_rank_boundary(ff: FakeFrappe) -> None:
	status, page1 = call(alerts.list, limit=2)
	validate("alerts.list", page1)
	assert [a["name"] for a in page1["items"]] == ["ALERT-FNEW", "ALERT-FOLD"] and page1["next_cursor"]
	status, page2 = call(alerts.list, limit=2, cursor=page1["next_cursor"])
	assert [a["name"] for a in page2["items"]] == ["ALERT-ACK", "ALERT-RES"]
	assert page2["next_cursor"] is None
	status, bad = call(alerts.list, cursor=_pagination.encode_cursor({"n": "x"}))
	assert status == 400 and bad["error"]["code"] == "invalid_cursor"


def test_list_filters_by_status_severity_and_target(ff: FakeFrappe) -> None:
	assert [a["name"] for a in call(alerts.list, status="firing")[1]["items"]] == ["ALERT-FNEW", "ALERT-FOLD"]
	assert [a["name"] for a in call(alerts.list, status="resolved")[1]["items"]] == ["ALERT-RES"]
	assert [a["name"] for a in call(alerts.list, severity="critical")[1]["items"]] == ["ALERT-FNEW"]
	assert [a["name"] for a in call(alerts.list, target_name="SRV-3")[1]["items"]] == ["ALERT-ACK"]
	assert call(alerts.list, status="nope")[0] == 400


def test_ack_sets_fields_and_audits(ff: FakeFrappe) -> None:
	status, body = call(alerts.ack, alert="ALERT-FOLD")
	assert status == 200
	validate("alerts.ack", body)
	assert body["alert"]["status"] == "acknowledged"
	assert body["alert"]["acknowledged_by"] == ff.session.user
	assert body["alert"]["acknowledged_at"] is not None
	assert ff.store["Alert"]["ALERT-FOLD"].status == "acknowledged"
	actions = [a.get("action") for a in ff.store.get("Infra Audit Log", {}).values()]
	assert actions == ["alerts.ack"]


def test_ack_rejects_non_firing(ff: FakeFrappe) -> None:
	status, body = call(alerts.ack, alert="ALERT-RES")
	assert status == 409 and body["error"]["code"] == "invalid_state"
	status, body = call(alerts.ack, alert="ALERT-ACK")
	assert status == 409 and body["error"]["code"] == "invalid_state"


def test_ack_missing_is_404(ff: FakeFrappe) -> None:
	status, body = call(alerts.ack, alert="ALERT-NOPE")
	assert status == 404 and body["error"]["code"] == "not_found"


def test_ack_requires_operator_role(ff: FakeFrappe) -> None:
	ff.session.user = "viewer@x"
	ff.roles["viewer@x"] = ("Infra Viewer",)
	status, body = call(alerts.ack, alert="ALERT-FOLD")
	assert status == 403 and body["error"]["details"]["required"] == "Infra Operator"
