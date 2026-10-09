"""A1.1: core helpers that need no site: errors, audit hashing, role hierarchy."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from infra_control.core import errors
from infra_control.core.audit import params_hash
from infra_control.core.enums import Capability, Risk
from infra_control.core.permissions import (
	INFRA_ADMIN,
	INFRA_OPERATOR,
	INFRA_VIEWER,
	RISK_ROLE,
	effective_roles,
)


def test_error_classes_cover_every_contract_code(repo_root: Path) -> None:
	with (repo_root / "contracts" / "openapi.yaml").open() as fh:
		spec = yaml.safe_load(fh)
	codes = set(spec["components"]["schemas"]["ErrorCode"]["enum"])
	assert {cls.code for cls in errors.ERROR_CLASSES} == codes
	statuses = {cls.code: cls.http_status for cls in errors.ERROR_CLASSES}
	assert statuses["capability_missing"] == 409
	assert statuses["confirmation_required"] == 400
	assert statuses["permission_denied"] == 403
	assert statuses["not_found"] == 404
	assert statuses["rate_limited"] == 429


def test_error_payload_shape() -> None:
	err = errors.NotSupported(Capability.SERVICE_CONTROL, "frappe_cloud")
	assert err.as_payload() == {
		"error": {
			"code": "capability_missing",
			"message": "Provider frappe_cloud lacks capability service_control",
			"details": {"capability": "service_control", "provider": "frappe_cloud"},
		}
	}
	assert errors.ConfirmationRequired("SRV-0001").details == {"expected": "SRV-0001"}
	assert errors.NotFound("Server", "SRV-9999").http_status == 404
	assert errors.RateLimited(30).retry_after == 30


@pytest.mark.parametrize(
	("params", "expected"),
	[
		(None, "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"),  # sha256("{}")
		({}, "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"),
	],
)
def test_params_hash_of_empty_params(params: dict[str, object] | None, expected: str) -> None:
	assert params_hash(params) == expected


def test_params_hash_is_canonical() -> None:
	assert params_hash({"b": 1, "a": [1, 2]}) == params_hash({"a": [1, 2], "b": 1})
	assert params_hash({"a": 1}) != params_hash({"a": 2})
	assert len(params_hash({"x": "é"})) == 64


def test_role_hierarchy() -> None:
	assert effective_roles([INFRA_VIEWER]) == {INFRA_VIEWER}
	assert effective_roles([INFRA_OPERATOR]) == {INFRA_OPERATOR, INFRA_VIEWER}
	assert effective_roles([INFRA_ADMIN]) == {INFRA_ADMIN, INFRA_OPERATOR, INFRA_VIEWER}
	assert effective_roles(["System Manager"]) == frozenset()
	assert effective_roles(["Administrator"]) == {INFRA_ADMIN, INFRA_OPERATOR, INFRA_VIEWER}


def test_high_risk_needs_admin() -> None:
	assert RISK_ROLE[Risk.HIGH] == INFRA_ADMIN
	assert RISK_ROLE[Risk.MEDIUM] == INFRA_OPERATOR
	assert RISK_ROLE[Risk.LOW] == INFRA_OPERATOR


def test_playbook_catalogue_matches_plan_section_9_2() -> None:
	from infra_control.install import PLAYBOOKS

	plan = {
		"server.provision": ("Provider Account", "medium"),
		"server.reboot": ("Server", "high"),
		"server.snapshot": ("Server", "low"),
		"server.apt_security": ("Server", "medium"),
		"service.control": ("Server", "medium"),
		"server.logs": ("Server", "low"),  # A3.8 log reader
		"server.exec": ("Server", "medium"),  # A3.9 command runner
		"server.trust_ca": ("Server", "low"),  # ADR 0007 console CA
		"site.create": ("Bench", "low"),
		"site.backup": ("Site", "low"),
		"site.restore": ("Site", "high"),
		"site.migrate": ("Site", "medium"),
		"site.maintenance": ("Site", "low"),
		"site.add_domain": ("Site", "low"),
		"site.suspend": ("Site", "medium"),
		"site.delete": ("Site", "high"),  # safe deletion
		"server.deprovision": ("Server", "high"),  # safe deletion
		"bench.update": ("Bench", "medium"),  # ADR 0004
		"bench.add_app": ("Bench", "medium"),  # ADR 0004
		"site.install_app": ("Site", "medium"),  # ADR 0004
		"metrics.collect": ("Server", "low"),
		"inventory.sync": ("Provider Account", "low"),
	}
	by_key = {p["key"]: p for p in PLAYBOOKS}
	assert set(by_key) == set(plan)
	for key, (target, risk) in plan.items():
		p = by_key[key]
		assert (str(p["target_doctype"]), str(p["risk"])) == (target, risk), key
		assert p.get("ansible_file") or p.get("provider_method"), key
		schema = p.get("params_schema")
		if schema is not None:
			assert schema["type"] == "object" and schema["additionalProperties"] is False, key
	assert by_key["server.provision"]["creates"] == "Server"
	assert by_key["site.create"]["creates"] == "Site"
