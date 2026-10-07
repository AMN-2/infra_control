"""A1.1: DocType JSONs match the plan's data model and the contract's enums; audit log is immutable."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from infra_control.core import enums

RESERVED = {
	"doctype",
	"name",
	"owner",
	"creation",
	"modified",
	"modified_by",
	"docstatus",
	"idx",
	"parent",
	"parentfield",
	"parenttype",
}

PLAN_DOCTYPES = {
	"Infra Settings",
	"Provider Account",
	"Server",
	"Bench",
	"Site",
	"Playbook",
	"Infra Job",
	"Infra Job Step",
	"Bulk Operation",
	"Server Metric",
	"Alert Rule",
	"Alert",
	"Backup",
	"Infra Audit Log",
}
CHILD_TABLES = {"Server Tag", "Bench App", "Site Domain", "Bulk Operation Target", "Alert Rule Channel"}

# DocType field -> contract enum schema name.
SELECT_ENUMS: dict[tuple[str, str], str] = {
	("Server", "status"): "ServerStatus",
	("Site", "status"): "SiteStatus",
	("Infra Job", "status"): "JobStatus",
	("Infra Job Step", "status"): "StepStatus",
	("Bulk Operation", "status"): "BulkStatus",
	("Bulk Operation", "phase"): "BulkPhase",
	("Bulk Operation", "failure_policy"): "FailurePolicy",
	("Bulk Operation Target", "status"): "BulkTargetStatus",
	("Alert", "status"): "AlertStatus",
	("Alert", "severity"): "Severity",
	("Alert Rule", "severity"): "Severity",
	("Alert Rule", "kind"): "AlertRuleKind",
	("Alert Rule Channel", "channel"): "AlertChannel",
	("Playbook", "risk"): "Risk",
	("Playbook", "target_doctype"): "TargetDoctype",
	("Provider Account", "provider"): "Provider",
	("Server", "role"): "ServerRole",
	("Server Metric", "resolution"): "Resolution",
	("Backup", "kind"): "BackupKind",
	("Infra Audit Log", "result"): "AuditResult",
}
# Optional selects: a leading blank option is allowed.
OPTIONAL_SELECT_ENUMS: dict[tuple[str, str], str] = {
	("Playbook", "required_capability"): "Capability",
	("Alert Rule", "metric"): "MetricName",
	("Alert Rule", "operator"): "Operator",
	("Alert", "metric"): "MetricName",
}


@pytest.fixture(scope="module")
def doctypes(repo_root: Path) -> dict[str, dict[str, Any]]:
	out: dict[str, dict[str, Any]] = {}
	for path in (repo_root / "infra_control" / "infra_control" / "doctype").glob("*/*.json"):
		with path.open() as fh:
			d = json.load(fh)
		assert d["name"].lower().replace(" ", "_") == path.parent.name == path.stem
		out[d["name"]] = d
	return out


@pytest.fixture(scope="module")
def spec_enums(repo_root: Path) -> dict[str, list[str]]:
	with (repo_root / "contracts" / "openapi.yaml").open() as fh:
		spec = yaml.safe_load(fh)
	return {k: v["enum"] for k, v in spec["components"]["schemas"].items() if "enum" in v}


def test_every_plan_doctype_exists(doctypes: dict[str, dict[str, Any]]) -> None:
	assert PLAN_DOCTYPES <= set(doctypes), PLAN_DOCTYPES - set(doctypes)
	assert set(doctypes) == PLAN_DOCTYPES | CHILD_TABLES, "unexpected doctype"
	for name in CHILD_TABLES:
		assert doctypes[name].get("istable") == 1, name


def test_module_engine_and_controller(doctypes: dict[str, dict[str, Any]], repo_root: Path) -> None:
	for name, d in doctypes.items():
		assert d["module"] == "Infra Control", name
		assert d["engine"] == "InnoDB", name
		folder = repo_root / "infra_control" / "infra_control" / "doctype" / name.lower().replace(" ", "_")
		controller = (folder / f"{folder.name}.py").read_text()
		cls = re.sub(r"\W", "", name.title())
		assert f"class {cls}(Document)" in controller, name
		assert (folder / "__init__.py").exists()


def test_no_reserved_fieldnames_and_unique_fields(doctypes: dict[str, dict[str, Any]]) -> None:
	for name, d in doctypes.items():
		names = [f["fieldname"] for f in d["fields"]]
		assert len(names) == len(set(names)), f"{name}: duplicate fieldname"
		assert not (set(names) & RESERVED), f"{name}: reserved fieldname used"
		assert d["field_order"] == names, f"{name}: field_order out of sync"
		for f in d["fields"]:
			if f["fieldtype"] in ("Link", "Table", "Dynamic Link", "Select"):
				assert f.get("options"), f"{name}.{f['fieldname']} needs options"
			if f["fieldtype"] in ("Link", "Table") and f["options"] not in ("DocType", "User", "Role"):
				assert f["options"] in doctypes, f"{name}.{f['fieldname']} links to unknown {f['options']}"


def _select(doctypes: dict[str, dict[str, Any]], doctype: str, field: str) -> list[str]:
	f = next(x for x in doctypes[doctype]["fields"] if x["fieldname"] == field)
	assert f["fieldtype"] == "Select", (doctype, field)
	return str(f["options"]).split("\n")


def test_select_options_match_contract_enums(
	doctypes: dict[str, dict[str, Any]], spec_enums: dict[str, list[str]]
) -> None:
	for (doctype, field), enum in SELECT_ENUMS.items():
		assert _select(doctypes, doctype, field) == spec_enums[enum], (doctype, field)
	for (doctype, field), enum in OPTIONAL_SELECT_ENUMS.items():
		assert _select(doctypes, doctype, field) == ["", *spec_enums[enum]], (doctype, field)


def test_python_enums_match_contract(spec_enums: dict[str, list[str]]) -> None:
	for enum_name, values in spec_enums.items():
		if enum_name in ("ErrorCode", "TopologyNodeType", "SearchResultType"):
			continue
		py = getattr(enums, enum_name, None)
		assert py is not None, f"no Python enum for {enum_name}"
		assert [str(m) for m in py] == values, enum_name


def test_audit_log_is_immutable(doctypes: dict[str, dict[str, Any]]) -> None:
	"""Security requirement 8: no write or delete permission for any role."""
	d = doctypes["Infra Audit Log"]
	assert d["permissions"], "roles must be able to read it"
	for p in d["permissions"]:
		assert p.get("write", 0) == 0 and p.get("delete", 0) == 0 and p.get("create", 0) == 0, p["role"]
	assert all(
		f.get("read_only") == 1
		for f in d["fields"]
		if f["fieldtype"] not in ("Column Break", "Section Break")
	)
	assert d.get("in_create") == 1 and d.get("track_changes") == 0


def test_roles_cover_the_plan(doctypes: dict[str, dict[str, Any]]) -> None:
	roles = {p["role"] for d in doctypes.values() for p in d.get("permissions", [])}
	assert roles == {"Infra Admin", "Infra Operator", "Infra Viewer"}
	for name, d in doctypes.items():
		if d.get("istable"):
			continue
		by_role = {p["role"]: p for p in d["permissions"]}
		assert "Infra Admin" in by_role, name
		if name != "Infra Settings":
			assert by_role["Infra Viewer"] == {
				**by_role["Infra Viewer"],
				"write": 0,
				"create": 0,
				"delete": 0,
			}, name
		if name in ("Infra Audit Log", "Server Metric"):
			assert by_role["Infra Admin"]["delete"] == 0, name


def test_server_metric_is_read_only_for_everyone(doctypes: dict[str, dict[str, Any]]) -> None:
	for p in doctypes["Server Metric"]["permissions"]:
		assert p["write"] == 0 and p["create"] == 0 and p["delete"] == 0


def test_contract_fields_exist_on_doctypes(doctypes: dict[str, dict[str, Any]], repo_root: Path) -> None:
	"""Every property the API returns for an entity is a stored field or an explicitly derived one."""
	with (repo_root / "contracts" / "openapi.yaml").open() as fh:
		schemas = yaml.safe_load(fh)["components"]["schemas"]
	derived: dict[str, set[str]] = {
		"Server": {"capabilities", "bench_count", "site_count", "tags"},
		"Bench": {"capabilities", "site_count", "apps"},
		"Site": {"capabilities", "custom_domains"},
		"Playbook": set(),
		"Job": {"created", "error"},
		"BulkOperation": {"canary_target"},
		"Alert": {"target"},
		"AlertRule": {"channels", "modified_at"},
		"Backup": {"restore_test_ok"},
		"AuditEntry": {"target"},
	}
	doctype_of = {
		"Job": "Infra Job",
		"BulkOperation": "Bulk Operation",
		"AlertRule": "Alert Rule",
		"AuditEntry": "Infra Audit Log",
	}
	for schema, extra in derived.items():
		dt = doctype_of.get(schema, schema)
		fields = {f["fieldname"] for f in doctypes[dt]["fields"]} | {"name"}
		missing = set(schemas[schema]["properties"]) - fields - extra - {"created_at", "modified_at"}
		# BulkOperation / Job / Backup use `creation` for created_at, Alert has fired_at, Backup stores created_at.
		assert not missing, f"{schema}: {sorted(missing)}"
