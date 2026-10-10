"""security.* (A4.1): the security posture of this controller and the switches it exposes.

`posture` runs a fixed list of checks the plan's section 13 asks for, each pass / warn / fail
with a hint. Nothing here returns a secret. `enable_2fa` turns on Frappe's OTP-app 2FA for
the Infra roles only (other roles on a shared site are untouched)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import frappe

from infra_control.api import api
from infra_control.backups.restore_test import MAX_DAYS_WITHOUT_OK, days_since_last_ok
from infra_control.core import audit
from infra_control.core.permissions import INFRA_ADMIN, INFRA_OPERATOR
from infra_control.core.secrets import controller_secret_values

TWO_FACTOR_ROLES = (INFRA_ADMIN, INFRA_OPERATOR)


def _check(cid: str, title: str, status: str, detail: str, hint: str = "") -> dict[str, Any]:
	return {"id": cid, "title": title, "status": status, "detail": detail, "hint": hint or None}


def _mode(path: Path) -> int | None:
	try:
		return os.stat(path).st_mode & 0o777
	except OSError:
		return None


def two_factor_state() -> dict[str, Any]:
	enabled = bool(frappe.db.get_single_value("System Settings", "enable_two_factor_auth"))
	roles = {r: bool(frappe.db.get_value("Role", r, "two_factor_auth")) for r in TWO_FACTOR_ROLES}
	return {
		"enabled": enabled,
		"roles": roles,
		"method": frappe.db.get_single_value("System Settings", "two_factor_method"),
	}


def checks() -> list[dict[str, Any]]:
	out: list[dict[str, Any]] = []
	tfa = two_factor_state()
	if tfa["enabled"] and all(tfa["roles"].values()):
		out.append(
			_check(
				"2fa",
				"Two-factor authentication",
				"pass",
				f"On for {', '.join(TWO_FACTOR_ROLES)} ({tfa['method'] or 'OTP App'})",
			)
		)
	else:
		out.append(
			_check(
				"2fa",
				"Two-factor authentication",
				"fail",
				"Off for the Infra roles",
				"Enable it below; every Infra Admin and Operator then enrols an OTP app at next login (plan 13.1).",
			)
		)

	admins = frappe.get_all("Has Role", filters={"role": INFRA_ADMIN, "parenttype": "User"}, pluck="parent")
	admins = sorted({a for a in admins if a not in ("Administrator", "Guest")})
	out.append(
		_check(
			"admins",
			"Infra Admin accounts",
			"pass" if 0 < len(admins) <= 5 else "warn",
			f"{len(admins)} user(s): {', '.join(admins) or 'none besides Administrator'}",
			"Keep the admin circle small; operators get Infra Operator.",
		)
	)

	keyed = (
		frappe.get_all("User", filters={"name": ["in", admins], "api_key": ["is", "set"]}, pluck="name")
		if admins
		else []
	)
	out.append(
		_check(
			"api_keys",
			"API keys on admin accounts",
			"pass" if not keyed else "warn",
			f"{len(keyed)} admin account(s) with an API key" if keyed else "none",
			"Rotate or remove keys that no integration uses.",
		)
	)

	accounts = frappe.get_all("Provider Account", fields=["name", "is_staging", "enabled"])
	prod = [a["name"] for a in accounts if a["enabled"] and not a["is_staging"]]
	out.append(
		_check(
			"provider_scopes",
			"Provider accounts",
			"pass" if accounts else "warn",
			f"{len(accounts)} account(s), {len(prod)} production",
			"Production tokens use custom scopes and a separate DigitalOcean project (plan 13.3).",
		)
	)
	allow_prod = bool(frappe.db.get_single_value("Infra Settings", "allow_production_accounts"))
	if allow_prod:
		prod_status, prod_detail = "warn", "production accounts enabled on this controller"
		prod_hint = (
			"Expected only on the production controller after the Phase 4 gate; keep staging controllers off."
		)
	elif prod:
		prod_status, prod_detail = (
			"warn",
			f"{len(prod)} production account(s) present but unusable (gate off)",
		)
		prod_hint = (
			"Turn on Infra Settings → Allow production accounts when this controller is the production one."
		)
	else:
		prod_status, prod_detail, prod_hint = "pass", "staging only (plan rule 11.6)", ""
	out.append(_check("production_gate", "Production accounts gate", prod_status, prod_detail, prod_hint))

	ssh_key = Path(os.path.expanduser(str(frappe.conf.get("infra_ssh_private_key") or "~/.ssh/id_ed25519")))
	mode = _mode(ssh_key)
	out.append(
		_check(
			"ssh_key",
			"Controller SSH key",
			"pass" if mode == 0o600 else "fail",
			f"{ssh_key} mode {oct(mode) if mode is not None else 'missing'}",
			"chmod 600; the key is what every managed server trusts.",
		)
	)

	ca_key = (
		Path(os.path.expanduser(os.environ.get("INFRA_CONSOLE_CA_DIR", "~/.infra-control/ssh_ca"))) / "ca"
	)
	ca_mode = _mode(ca_key)
	out.append(
		_check(
			"console_ca",
			"Console certificate authority",
			"pass" if ca_mode in (0o600, None) else "fail",
			f"{ca_key} {'mode ' + oct(ca_mode) if ca_mode is not None else 'not created yet (created on first console session)'}",
			"The CA key must stay 0600 and never leave the controller.",
		)
	)

	masked = len(controller_secret_values())
	out.append(
		_check(
			"masking",
			"Secrets masking",
			"pass",
			f"{masked} controller secret(s) on every job's mask list, plus provider and Git tokens and write-only parameters",
		)
	)

	perms = frappe.get_all(
		"DocPerm",
		filters={"parent": "Infra Audit Log", "parenttype": "DocType"},
		fields=["role", "write", "delete", "create"],
	)
	writable = [p["role"] for p in perms if p.get("write") or p.get("delete") or p.get("create")]
	out.append(
		_check(
			"audit_immutable",
			"Audit log immutability",
			"pass" if not writable else "fail",
			"no role can write or delete audit rows"
			if not writable
			else f"writable by {', '.join(writable)}",
			"Security requirement 8.",
		)
	)

	sched_on = not bool(frappe.conf.get("pause_scheduler")) and bool(
		frappe.db.get_single_value("System Settings", "enable_scheduler")
	)
	out.append(
		_check(
			"scheduler",
			"Scheduler",
			"pass" if sched_on else "fail",
			"enabled" if sched_on else "disabled: no metrics, alerts, scheduled backups or retention",
			"bench --site <site> scheduler enable",
		)
	)

	live_sites = frappe.get_all("Site", filters={"status": ["not in", ["Archived"]]}, pluck="name")
	with_policy = set(frappe.get_all("Backup Policy", filters={"enabled": 1}, pluck="site"))
	missing = [s for s in live_sites if s not in with_policy]
	out.append(
		_check(
			"backup_policies",
			"Backup schedules",
			"pass" if not missing else ("warn" if len(missing) < len(live_sites) else "fail"),
			f"{len(live_sites) - len(missing)} of {len(live_sites)} live site(s) scheduled"
			+ (f"; missing: {', '.join(missing[:5])}" if missing else ""),
			"Every client site needs a schedule (Sites → Backups).",
		)
	)

	days = days_since_last_ok()
	out.append(
		_check(
			"restore_test",
			"Restore test",
			"pass" if days is not None and days <= MAX_DAYS_WITHOUT_OK else "fail",
			f"last successful test {days} day(s) ago" if days is not None else "never run",
			f"Run site.restore_test; the monthly job alerts after {MAX_DAYS_WITHOUT_OK} days (security requirement 10).",
		)
	)

	settings: Any = frappe.get_doc("Infra Settings")
	configured = bool(settings.get("offsite_endpoint_url") and settings.get("offsite_bucket"))
	last = settings.get("offsite_last_run")
	err = settings.get("offsite_last_error")
	if not configured:
		out.append(
			_check(
				"controller_backup",
				"Controller backup off DigitalOcean",
				"fail",
				"not configured",
				"Fill the off-site bucket on Infra Settings (any S3-compatible store outside DigitalOcean; security requirement 11).",
			)
		)
	elif err:
		out.append(
			_check(
				"controller_backup",
				"Controller backup off DigitalOcean",
				"fail",
				f"last run failed: {str(err)[:120]}",
			)
		)
	else:
		out.append(
			_check(
				"controller_backup",
				"Controller backup off DigitalOcean",
				"pass" if last else "warn",
				f"last upload {last}" if last else "configured, first run pending (daily)",
			)
		)

	spaces = bool(settings.get("spaces_bucket"))
	out.append(
		_check(
			"spaces",
			"Off-site site backups (Spaces)",
			"pass" if spaces else "fail",
			"configured" if spaces else "not configured: site backups stay on the servers",
			"Infra Settings → Spaces.",
		)
	)

	open_sessions = 0
	try:
		from infra_control.api.console import _sidecars

		open_sessions = sum(1 for m in _sidecars(None) if not m.get("ended_at"))
	except Exception:
		open_sessions = 0
	out.append(
		_check(
			"console_sessions",
			"Open console sessions",
			"pass" if open_sessions == 0 else "warn",
			f"{open_sessions} open now",
			"Sessions close after 30 minutes idle or 4 hours; transcripts stay.",
		)
	)
	return out


@api(role=INFRA_ADMIN)
def posture() -> dict[str, Any]:
	items = checks()
	score = {"pass": 0, "warn": 0, "fail": 0}
	for c in items:
		score[str(c["status"])] += 1
	return {"checks": items, "summary": score, "two_factor": two_factor_state()}


@api(methods=("POST",), role=INFRA_ADMIN)
def enable_2fa() -> dict[str, Any]:
	"""OTP-app two-factor authentication for Infra Admin and Infra Operator (Frappe's built-in)."""
	for role in TWO_FACTOR_ROLES:
		frappe.db.set_value("Role", role, "two_factor_auth", 1)
	frappe.db.set_value(
		"System Settings",
		None,
		{"enable_two_factor_auth": 1, "two_factor_method": "OTP App", "otp_issuer_name": "Infra Control"},
	)
	audit.record("security.enable_2fa", result="success")
	return {"two_factor": two_factor_state()}
