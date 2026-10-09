"""Install and migrate hooks: roles and built-in alert rules. Idempotent."""

from __future__ import annotations

import json
from typing import Any

import frappe

from infra_control.core.enums import AlertRuleKind, Capability, Risk, Severity, TargetDoctype
from infra_control.core.permissions import ROLES

_EMPTY_SCHEMA: dict[str, Any] = {"type": "object", "additionalProperties": False, "properties": {}}


def _schema(required: list[str], **props: dict[str, Any]) -> dict[str, Any]:
	return {"type": "object", "additionalProperties": False, "required": required, "properties": props}


def _pb(
	key: str, title: str, description: str, target: TargetDoctype, risk: Risk, **kw: Any
) -> dict[str, Any]:
	return {
		"key": key,
		"title": title,
		"description": description,
		"target_doctype": target,
		"risk": risk,
		**kw,
	}


# The v1 playbook catalogue (plan section 9.2; creation targets per ADR 0001). The executor
# wiring (ansible_file / provider_method bodies) lands in A1.3 and Phase 2; the catalogue itself
# is data the UI and `playbooks.list` need from day one.
PLAYBOOKS: tuple[dict[str, Any], ...] = (
	_pb(
		"server.provision",
		"Provision server",
		"Create a droplet, run cloud-init and the base, mariadb, redis, nginx and bench roles. Creates the Server document.",
		TargetDoctype.PROVIDER_ACCOUNT,
		Risk.MEDIUM,
		creates="Server",
		required_capability=Capability.SERVER,
		provider_method="create_server",
		params_schema=_schema(
			["hostname", "region", "size"],
			hostname={"type": "string", "pattern": "^[a-z0-9.-]{3,63}$"},
			region={"type": "string"},
			size={"type": "string"},
			role={"type": "string", "enum": ["app", "db", "proxy", "all"], "default": "all"},
			tags={"type": "array", "items": {"type": "string"}, "default": []},
		),
	),
	_pb(
		"server.reboot",
		"Reboot server",
		"Reboot the droplet. Requires typed confirmation.",
		TargetDoctype.SERVER,
		Risk.HIGH,
		required_capability=Capability.SERVER,
		provider_method="reboot_server",
	),
	_pb(
		"server.snapshot",
		"Snapshot server",
		"Take a DigitalOcean snapshot; the action is polled until it completes.",
		TargetDoctype.SERVER,
		Risk.LOW,
		required_capability=Capability.SNAPSHOT,
		provider_method="snapshot_server",
	),
	_pb(
		"server.apt_security",
		"Apply security updates",
		"Unattended security updates via apt.",
		TargetDoctype.SERVER,
		Risk.MEDIUM,
		required_capability=Capability.SSH,
		ansible_file="server_apt_security.yml",
	),
	_pb(
		"server.logs",
		"Read logs",
		"Tail a log on the server (nginx, MariaDB, Redis, supervisor, system journal, bench, Frappe, database queries, one site), optionally filtered. Read-only.",
		TargetDoctype.SERVER,
		Risk.LOW,
		required_capability=Capability.SSH,
		ansible_file="logs_read.yml",
		params_schema=_schema(
			["source"],
			source={
				"type": "string",
				"enum": [
					"nginx_access",
					"nginx_error",
					"mariadb",
					"redis",
					"supervisor",
					"system",
					"bench_web",
					"bench_worker",
					"bench_schedule",
					"bench_error",
					"frappe",
					"database",
					"site",
				],
			},
			bench_path={"type": "string", "default": "/home/frappe/frappe-bench"},
			site={"type": "string", "default": "", "description": "Site domain, for source = site"},
			lines={"type": "integer", "minimum": 1, "maximum": 2000, "default": 200},
			match={"type": "string", "default": "", "description": "Case-insensitive filter"},
		),
	),
	_pb(
		"server.trust_ca",
		"Trust console certificates",
		"Install the controller's console certificate authority on the server so web console sessions can log in with short-lived certificates.",
		TargetDoctype.SERVER,
		Risk.LOW,
		required_capability=Capability.SSH,
		ansible_file="server_trust_ca.yml",
	),
	_pb(
		"server.deprovision",
		"Deprovision server",
		"Destroy the server at the provider. Refused while it still has live sites; the Server record is archived, not deleted. Requires typed confirmation.",
		TargetDoctype.SERVER,
		Risk.HIGH,
		required_capability=Capability.SERVER,
		provider_method="deprovision_server",
	),
	_pb(
		"server.exec",
		"Run command",
		"Run one shell command as the bench user and return its output. Destructive commands are refused; everything is audited.",
		TargetDoctype.SERVER,
		Risk.MEDIUM,
		required_capability=Capability.SSH,
		ansible_file="server_exec.yml",
		params_schema=_schema(
			["command"],
			command={"type": "string", "minLength": 1, "maxLength": 4000},
			cwd={"type": "string", "default": "/home/frappe/frappe-bench"},
			timeout={"type": "integer", "minimum": 1, "maximum": 600, "default": 120},
		),
	),
	_pb(
		"service.control",
		"Control a service",
		"Restart or reload nginx, supervisor, mariadb or redis.",
		TargetDoctype.SERVER,
		Risk.MEDIUM,
		required_capability=Capability.SERVICE_CONTROL,
		provider_method="control_service",
		params_schema=_schema(
			["service", "action"],
			service={"type": "string", "enum": ["nginx", "supervisor", "mariadb", "redis"]},
			action={"type": "string", "enum": ["restart", "reload"]},
		),
	),
	_pb(
		"site.create",
		"Create site",
		"Create a new site on the bench with the given apps. Creates the Site document.",
		TargetDoctype.BENCH,
		Risk.LOW,
		creates="Site",
		required_capability=Capability.SITE,
		provider_method="create_site",
		params_schema=_schema(
			["domain", "admin_password"],
			domain={"type": "string", "format": "hostname"},
			apps={"type": "array", "items": {"type": "string"}, "default": []},
			admin_password={"type": "string", "format": "password", "writeOnly": True, "minLength": 12},
		),
	),
	_pb(
		"site.backup",
		"Backup site",
		"Database and files backup, uploaded offsite.",
		TargetDoctype.SITE,
		Risk.LOW,
		required_capability=Capability.SITE,
		provider_method="backup_site",
		params_schema=_schema([], with_files={"type": "boolean", "default": True}),
	),
	_pb(
		"site.restore",
		"Restore site",
		"Restore a backup over the site. Requires typed confirmation.",
		TargetDoctype.SITE,
		Risk.HIGH,
		required_capability=Capability.SITE,
		provider_method="restore_site",
		params_schema=_schema(["backup"], backup={"type": "string"}),
	),
	_pb(
		"site.migrate",
		"Migrate site",
		"Take a backup, then run bench migrate. Fails if the backup fails.",
		TargetDoctype.SITE,
		Risk.MEDIUM,
		required_capability=Capability.SITE,
		provider_method="update_site",
		params_schema=_schema([], skip_search_index={"type": "boolean", "default": False}),
	),
	_pb(
		"bench.update",
		"Update bench apps",
		"Pull new app code on the bench (fast-forward only), install requirements, then back up and migrate every site on it, build assets and restart.",
		TargetDoctype.BENCH,
		Risk.MEDIUM,
		required_capability=Capability.SSH,
		provider_method="update_bench",
		params_schema=_schema(
			[],
			apps={
				"type": "array",
				"items": {"type": "string"},
				"default": [],
				"description": "Apps to pull; empty = every app on the bench",
			},
			branch={
				"type": "string",
				"default": "",
				"description": "Switch the selected apps to this branch first",
			},
			migrate={
				"type": "boolean",
				"default": True,
				"description": "Back up and migrate every site on the bench",
			},
			build={"type": "boolean", "default": True},
		),
	),
	_pb(
		"bench.add_app",
		"Add app to bench",
		"bench get-app from a git repository (optionally a branch) and build its assets. Already present = no-op.",
		TargetDoctype.BENCH,
		Risk.MEDIUM,
		required_capability=Capability.SSH,
		provider_method="add_app",
		params_schema=_schema(
			["app", "repo"],
			app={"type": "string", "pattern": "^[a-z][a-z0-9_]{1,63}$"},
			repo={
				"type": "string",
				"format": "uri",
				"description": "https:// or git@ URL of the app",
				"x-picker": "git_repo",
			},
			branch={"type": "string", "default": "", "description": "Branch or tag", "x-picker": "git_ref"},
			connection={
				"type": "string",
				"default": "",
				"description": "Git Connection whose token clones a private repository",
				"x-picker": "git_connection",
			},
		),
	),
	_pb(
		"site.install_app",
		"Install app on site",
		"Back up, then bench install-app for an app already on the bench. Fails if the backup fails.",
		TargetDoctype.SITE,
		Risk.MEDIUM,
		required_capability=Capability.SITE,
		provider_method="install_app",
		params_schema=_schema(["app"], app={"type": "string", "pattern": "^[a-z][a-z0-9_]{1,63}$"}),
	),
	_pb(
		"site.delete",
		"Delete site",
		"Take a last database and files backup offsite (fails if that fails), then drop the site and its vhost. The Site record is archived, not deleted. Requires typed confirmation.",
		TargetDoctype.SITE,
		Risk.HIGH,
		required_capability=Capability.SITE,
		provider_method="delete_site",
	),
	_pb(
		"site.maintenance",
		"Maintenance mode",
		"Turn maintenance mode on or off.",
		TargetDoctype.SITE,
		Risk.LOW,
		required_capability=Capability.SITE,
		provider_method="set_maintenance",
		params_schema=_schema(["on"], on={"type": "boolean"}),
	),
	_pb(
		"site.add_domain",
		"Add custom domain",
		"Add a domain with nginx, certbot and DNS (DigitalOcean) or via Press (Frappe Cloud).",
		TargetDoctype.SITE,
		Risk.LOW,
		required_capability=Capability.SITE,
		provider_method="add_domain",
		params_schema=_schema(["domain"], domain={"type": "string", "format": "hostname"}),
	),
	_pb(
		"site.suspend",
		"Suspend site",
		"Suspend or unsuspend the site (Frappe Cloud: deactivate/activate, see Q7).",
		TargetDoctype.SITE,
		Risk.MEDIUM,
		required_capability=Capability.SITE,
		provider_method="suspend_site",
		params_schema=_schema(["suspended"], suspended={"type": "boolean"}),
	),
	_pb(
		"metrics.collect",
		"Collect metrics",
		"Scheduled every minute; writes Server Metric rows.",
		TargetDoctype.SERVER,
		Risk.LOW,
		required_capability=Capability.METRICS,
		provider_method="get_metrics",
	),
	_pb(
		"inventory.sync",
		"Sync inventory",
		"Scheduled hourly; compares provider inventory with the DocTypes and raises drift alerts.",
		TargetDoctype.PROVIDER_ACCOUNT,
		Risk.LOW,
		required_capability=None,
		provider_method="sync_inventory",
	),
)

# The built-in rules every site has (contracts/openapi.yaml, AlertRuleKind). Users may edit
# severity, channels, enabled and the kind's own parameter, never create or delete them.
BUILTIN_RULES: tuple[dict[str, Any], ...] = (
	{
		"kind": AlertRuleKind.HEARTBEAT,
		"title": "Server heartbeat missing",
		"target_doctype": TargetDoctype.SERVER,
		"for_minutes": 3,
		"severity": Severity.CRITICAL,
		"channels": ["telegram", "email"],
	},
	{
		"kind": AlertRuleKind.SSL_EXPIRY,
		"title": "SSL certificate expiring",
		"target_doctype": TargetDoctype.SITE,
		"threshold": 14,
		"severity": Severity.WARNING,
		"channels": ["email"],
	},
	{
		"kind": AlertRuleKind.DRIFT,
		"title": "Inventory drift",
		"target_doctype": TargetDoctype.PROVIDER_ACCOUNT,
		"severity": Severity.WARNING,
		"channels": ["telegram"],
	},
	{
		"kind": AlertRuleKind.CONTRACT,
		"title": "Press API contract drift",
		"target_doctype": TargetDoctype.PROVIDER_ACCOUNT,
		"severity": Severity.CRITICAL,
		"channels": ["telegram", "email"],
	},
)


def after_install() -> None:
	ensure_roles()
	ensure_playbooks()
	ensure_builtin_alert_rules()


def after_migrate() -> None:
	ensure_roles()
	ensure_playbooks()
	ensure_builtin_alert_rules()


def ensure_playbooks() -> None:
	"""Upsert the catalogue. Operators may toggle `enabled`; every other field is code-owned."""
	for spec in PLAYBOOKS:
		values = {
			"title": spec["title"],
			"description": spec["description"],
			"target_doctype": str(spec["target_doctype"]),
			"creates": spec.get("creates") or "",
			"risk": str(spec["risk"]),
			"required_capability": str(spec["required_capability"])
			if spec.get("required_capability")
			else "",
			"ansible_file": spec.get("ansible_file") or "",
			"provider_method": spec.get("provider_method") or "",
			"params_schema": json.dumps(spec.get("params_schema") or _EMPTY_SCHEMA),
		}
		if frappe.db.exists("Playbook", spec["key"]):
			doc = frappe.get_doc("Playbook", spec["key"])
			doc.update(values)
			doc.save(ignore_permissions=True)
		else:
			frappe.get_doc({"doctype": "Playbook", "key": spec["key"], "enabled": 1, **values}).insert(
				ignore_permissions=True
			)


def ensure_roles() -> None:
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)


def ensure_builtin_alert_rules() -> None:
	for spec in BUILTIN_RULES:
		kind = str(spec["kind"])
		if frappe.db.exists("Alert Rule", {"kind": kind, "builtin": 1}):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Alert Rule",
				"title": spec["title"],
				"kind": kind,
				"target_doctype": str(spec["target_doctype"]),
				"threshold": spec.get("threshold"),
				"for_minutes": spec.get("for_minutes"),
				"severity": str(spec["severity"]),
				"enabled": 1,
				"builtin": 1,
				"channels": [{"channel": c} for c in spec["channels"]],
			}
		)
		doc.insert(ignore_permissions=True)
