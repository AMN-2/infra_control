"""A0.2 contract tests: contracts/openapi.yaml is valid, complete and self-consistent."""

from __future__ import annotations

import re
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate as validate_openapi

pytestmark = pytest.mark.contract

BASE = "/api/method/infra_control.api."

# Plan section 6.1, plus the reviewer's additions from the PR #4 contracts review
# (benches.list, benches.get, bulk.cancel).
REQUIRED_ENDPOINTS: dict[str, str] = {
	"overview.summary": "get",
	"inventory.topology": "get",
	"servers.list": "get",
	"servers.get": "get",
	"sites.list": "get",
	"sites.get": "get",
	"benches.list": "get",
	"benches.get": "get",
	"metrics.series": "get",
	"playbooks.list": "get",
	"jobs.run": "post",
	"jobs.cancel": "post",
	"jobs.retry": "post",
	"jobs.list": "get",
	"jobs.get": "get",
	"bulk.create": "post",
	"bulk.pause": "post",
	"bulk.resume": "post",
	"bulk.cancel": "post",
	"bulk.list": "get",
	"bulk.get": "get",
	"alerts.list": "get",
	"alerts.ack": "post",
	"alert_rules.list": "get",
	"alert_rules.get": "get",
	"alert_rules.create": "post",
	"alert_rules.update": "post",
	"alert_rules.delete": "post",
	"audit.list": "get",
	"search.query": "get",
}

# Plan section 5 unified enums.
UNIFIED_ENUMS: dict[str, list[str]] = {
	"ServerStatus": ["Provisioning", "Active", "Degraded", "Down", "Archived"],
	"SiteStatus": ["Pending", "Active", "Maintenance", "Suspended", "Broken", "Archived"],
	"JobStatus": ["Queued", "Running", "Success", "Failed", "Cancelled"],
	"StepStatus": ["Queued", "Running", "Success", "Failed", "Cancelled", "Skipped"],
	"Capability": [
		"site",
		"bench",
		"server",
		"ssh",
		"snapshot",
		"service_control",
		"metrics",
		"custom_playbook",
		"managed_backup",
		"managed_update",
	],
	"Provider": ["digitalocean", "frappe_cloud"],
}

RFC3339_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def _operations(spec: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
	ops = []
	for path, item in spec["paths"].items():
		for method, op in item.items():
			if method in {"get", "post", "put", "patch", "delete"}:
				ops.append((path, method, op))
	return ops


def _validator(spec: dict[str, Any], schema: dict[str, Any]) -> Draft202012Validator:
	# Embed the spec's components so "#/components/..." refs resolve inside one document.
	wrapped = {"$id": "urn:openapi", "components": spec["components"], "allOf": [schema]}
	return Draft202012Validator(wrapped, format_checker=FormatChecker())


def test_spec_is_valid_openapi_31(spec: dict[str, Any]) -> None:
	assert spec["openapi"].startswith("3.1")
	validate_openapi(spec)


def test_every_plan_endpoint_exists_with_the_right_method(spec: dict[str, Any]) -> None:
	for fn, method in REQUIRED_ENDPOINTS.items():
		path = BASE + fn
		assert path in spec["paths"], f"missing endpoint {fn}"
		assert method in spec["paths"][path], f"{fn} must be {method.upper()}"
		assert len([m for m in spec["paths"][path] if m in {"get", "post"}]) == 1, (
			f"{fn} has more than one method"
		)


def test_no_endpoint_outside_the_plan(spec: dict[str, Any]) -> None:
	extra = {p.removeprefix(BASE) for p in spec["paths"]} - set(REQUIRED_ENDPOINTS)
	assert extra == set(), f"endpoints not in plan section 6.1 or the review: {sorted(extra)}"


def test_every_operation_has_id_tag_and_json_200(spec: dict[str, Any]) -> None:
	seen: set[str] = set()
	for path, method, op in _operations(spec):
		assert op.get("operationId"), f"{method} {path} lacks operationId"
		assert op["operationId"] not in seen, f"duplicate operationId {op['operationId']}"
		seen.add(op["operationId"])
		assert op.get("tags"), f"{method} {path} lacks tags"
		assert "200" in op["responses"], f"{method} {path} lacks a 200"
		assert "application/json" in op["responses"]["200"]["content"]
		assert "401" in op["responses"] and "403" in op["responses"], (
			f"{method} {path} must document 401 and 403"
		)
		assert op["responses"].get("429", {}).get("$ref", "").endswith("RateLimited"), (
			f"{method} {path} must document 429 rate_limited"
		)
		if method == "post":
			assert op.get("requestBody", {}).get("required") is True, (
				f"{method} {path} POST needs a required body"
			)


def test_get_endpoints_use_query_parameters_only(spec: dict[str, Any]) -> None:
	for path, method, op in _operations(spec):
		if method == "get":
			assert "requestBody" not in op
			for param in op.get("parameters", []):
				if "$ref" in param:
					continue
				assert param["in"] == "query", f"{path}: {param['name']} must be a query parameter"


def test_list_endpoints_are_cursor_paginated(spec: dict[str, Any]) -> None:
	# playbooks.list is a small catalogue and deliberately not paginated.
	for fn in (f for f in REQUIRED_ENDPOINTS if f.endswith(".list") and f != "playbooks.list"):
		op = spec["paths"][BASE + fn]["get"]
		refs = {p.get("$ref") for p in op.get("parameters", [])}
		assert "#/components/parameters/limit" in refs, f"{fn} lacks limit"
		assert "#/components/parameters/cursor" in refs, f"{fn} lacks cursor"
		schema_ref = op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
		schema = spec["components"]["schemas"][schema_ref.rsplit("/", 1)[1]]
		assert set(schema["required"]) == {"items", "next_cursor"}, f"{fn} page shape"


def test_unified_enums_match_plan_section_5(spec: dict[str, Any]) -> None:
	schemas = spec["components"]["schemas"]
	for name, values in UNIFIED_ENUMS.items():
		assert schemas[name]["enum"] == values, name


def test_error_envelope(spec: dict[str, Any]) -> None:
	err = spec["components"]["schemas"]["Error"]
	assert set(err["required"]) == {"code", "message", "details"}
	codes = set(spec["components"]["schemas"]["ErrorCode"]["enum"])
	assert {
		"capability_missing",
		"confirmation_required",
		"permission_denied",
		"not_found",
		"validation_error",
	} <= codes


def test_capability_missing_is_409_and_confirmation_is_400(spec: dict[str, Any]) -> None:
	run = spec["paths"][BASE + "jobs.run"]["post"]["responses"]
	assert run["409"]["$ref"].endswith("CapabilityMissing")
	assert run["400"]["$ref"].endswith("ValidationOrConfirmation")
	confirmation = spec["components"]["responses"]["ValidationOrConfirmation"]["content"]["application/json"][
		"examples"
	]
	assert confirmation["confirmation_required"]["value"]["error"]["code"] == "confirmation_required"


def test_realtime_event_list_matches_plan(spec: dict[str, Any], event_index: dict[str, str]) -> None:
	assert spec["x-realtime-events"] == list(event_index)


def _examples(spec: dict[str, Any]) -> list[tuple[str, dict[str, Any], Any]]:
	"""Yield (label, schema, value) for every example in responses, request bodies and components."""
	found: list[tuple[str, dict[str, Any], Any]] = []

	def collect(label: str, media: dict[str, Any]) -> None:
		schema = media.get("schema")
		if schema is None:
			return
		if "example" in media:
			found.append((label, schema, media["example"]))
		for ex_name, ex in media.get("examples", {}).items():
			if "$ref" in ex:
				ex = spec["components"]["examples"][ex["$ref"].rsplit("/", 1)[1]]
			found.append((f"{label}#{ex_name}", schema, ex["value"]))

	for path, method, op in _operations(spec):
		label = f"{method} {path.removeprefix(BASE)}"
		for code, resp in op["responses"].items():
			if "$ref" in resp:
				resp = spec["components"]["responses"][resp["$ref"].rsplit("/", 1)[1]]
			for media in resp.get("content", {}).values():
				collect(f"{label} {code}", media)
		for media in op.get("requestBody", {}).get("content", {}).values():
			collect(f"{label} body", media)
	return found


def test_every_example_validates_against_its_schema(spec: dict[str, Any]) -> None:
	examples = _examples(spec)
	assert len(examples) >= 20
	for label, schema, value in examples:
		errors = sorted(_validator(spec, schema).iter_errors(value), key=lambda e: list(e.path))
		assert not errors, f"{label}: " + "; ".join(f"{list(e.path)}: {e.message}" for e in errors[:5])


def test_examples_use_rfc3339_utc_timestamps(spec: dict[str, Any]) -> None:
	def walk(value: Any, path: str) -> None:
		if isinstance(value, dict):
			for k, v in value.items():
				walk(v, f"{path}.{k}")
		elif isinstance(value, list):
			for i, v in enumerate(value):
				walk(v, f"{path}[{i}]")
		elif isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}T", value):
			assert RFC3339_UTC.match(value), f"{path}: {value} is not UTC with Z"

	for label, _schema, value in _examples(spec):
		walk(value, label)


def test_every_component_schema_is_referenced(spec: dict[str, Any]) -> None:
	import yaml

	text = yaml.safe_dump(spec)
	for name in spec["components"]["schemas"]:
		assert f"#/components/schemas/{name}" in text, f"schema {name} is never referenced"


# ----- PR #4 review items ---------------------------------------------------------------


def test_creation_flows_are_explicit(spec: dict[str, Any]) -> None:
	s = spec["components"]["schemas"]
	assert s["TargetDoctype"]["enum"] == ["Server", "Site", "Bench", "Provider Account"]
	assert "created" in s["Job"]["required"] and "cancel_requested" in s["Job"]["required"]
	assert "creates" in s["Playbook"]["required"]
	playbooks = {p["key"]: p for p in spec["components"]["examples"]["PlaybookList"]["value"]["items"]}
	assert playbooks["server.provision"]["target_doctype"] == "Provider Account"
	assert playbooks["server.provision"]["creates"] == "Server"
	assert playbooks["site.create"]["target_doctype"] == "Bench"
	assert playbooks["site.create"]["creates"] == "Site"
	run_examples = spec["paths"][BASE + "jobs.run"]["post"]["requestBody"]["content"]["application/json"][
		"examples"
	]
	assert {"provision_server", "create_site"} <= set(run_examples)


def test_alert_rule_kinds_cover_every_builtin_rule(spec: dict[str, Any]) -> None:
	s = spec["components"]["schemas"]
	assert s["AlertRuleKind"]["enum"] == ["metric", "heartbeat", "ssl_expiry", "drift", "contract"]
	rules = spec["components"]["examples"]["AlertRulePage"]["value"]["items"]
	assert {r["kind"] for r in rules} == set(s["AlertRuleKind"]["enum"]), "one example per kind"
	validator = _validator(spec, {"$ref": "#/components/schemas/AlertRule"})
	for rule in rules:
		assert not list(validator.iter_errors(rule)), rule["name"]
	# The conditions bite: a heartbeat rule with a metric is invalid; a user-created builtin is invalid.
	bad = dict(next(r for r in rules if r["kind"] == "heartbeat"), metric="cpu")
	assert list(validator.iter_errors(bad))
	bad = dict(next(r for r in rules if r["kind"] == "metric"), builtin=True)
	assert list(validator.iter_errors(bad))
	# Only metric rules are creatable.
	assert s["AlertRuleInput"]["properties"]["kind"]["const"] == "metric"


def test_server_has_hostname_used_for_labels(spec: dict[str, Any]) -> None:
	s = spec["components"]["schemas"]
	assert "hostname" in s["Server"]["required"]
	assert "hostname" in s["TopologyNode"]["properties"]["label"]["description"]
	assert "hostname" in s["SearchResult"]["properties"]["title"]["description"]
	ex = spec["components"]["examples"]
	servers = {x["name"]: x["hostname"] for x in ex["ServerPage"]["value"]["items"]}
	for node in ex["Topology"]["value"]["nodes"]:
		if node["type"] == "server":
			assert node["label"] == servers[node["ref"]]


def test_auth_failure_shapes_are_distinguishable(spec: dict[str, Any]) -> None:
	forbidden = spec["components"]["responses"]["Forbidden"]["content"]["application/json"]
	examples = {k: v["value"] for k, v in forbidden["examples"].items()}
	assert "error" in examples["permission_denied"] and "error" not in examples["reauthenticate"]
	assert examples["reauthenticate"]["exc_type"] == "PermissionError"
	unauthorized = spec["components"]["responses"]["Unauthorized"]["content"]["application/json"]
	assert unauthorized["example"]["exc_type"] == "AuthenticationError"
	fw = spec["components"]["schemas"]["FrappeFrameworkError"]
	assert set(fw["properties"]["exc_type"]["enum"]) == {
		"AuthenticationError",
		"PermissionError",
		"CSRFTokenError",
	}


def test_benches_include_frappe_cloud_with_null_server(spec: dict[str, Any]) -> None:
	ex = spec["components"]["examples"]
	assert any(b["server"] is None for b in ex["BenchPage"]["value"]["items"])
	assert ex["BenchDetail"]["value"]["server"] is None


def test_bulk_cancel_and_overview_unresolved(spec: dict[str, Any]) -> None:
	cancel = spec["paths"][BASE + "bulk.cancel"]["post"]
	assert cancel["responses"]["409"]["$ref"].endswith("InvalidState")
	assert "Cancelled" in spec["components"]["schemas"]["BulkStatus"]["enum"]
	alerts = spec["components"]["schemas"]["OverviewSummary"]["properties"]["alerts"]
	assert "unresolved" in alerts["required"] and "firing" not in alerts["properties"]
	bulk_confirm = spec["components"]["schemas"]["BulkCreateRequest"]["properties"]["confirm"]["description"]
	assert "<playbook key>:<number of targets>" in bulk_confirm
