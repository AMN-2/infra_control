"""Post-batch health checks (plan 9.3 step 4).

After each batch the bulk engine confirms every target still answers: an HTTP `GET` on
`/api/method/ping` returning 200, and — best effort — that the site's scheduler is not inactive.
Follows the external-HTTP rule (a bounded timeout, no retry storm) and never raises: any error,
timeout or unreachable host becomes a soft `(False, reason)` the caller logs and folds into the
failure policy. On staging the hosts are often unreachable, so the caller can skip the check with
`params["_skip_health"]`.
"""

from __future__ import annotations

from typing import Any

import frappe
import requests

PING_PATH = "/api/method/ping"
SCHEDULER_PATH = "/api/method/frappe.utils.scheduler.is_scheduler_inactive"
TIMEOUT_SECONDS = 10.0


def check_target(
	target_doctype: str, target_name: str, *, timeout: float = TIMEOUT_SECONDS
) -> tuple[bool, str]:
	"""Return `(ok, detail)` for a Site or Server. Never raises; a failure is always soft."""
	try:
		base = _base_url(target_doctype, target_name)
	except Exception as exc:  # resolving the host must never raise into the caller
		return False, f"could not resolve a URL for {target_doctype} {target_name}: {exc}"
	if not base:
		return False, f"no reachable address for {target_doctype} {target_name}"

	try:
		response = requests.get(f"{base}{PING_PATH}", timeout=timeout)
	except requests.RequestException as exc:
		return False, f"ping failed: {type(exc).__name__}: {exc}"
	if response.status_code != 200:
		return False, f"ping returned HTTP {response.status_code}"

	scheduler = _scheduler_detail(base, timeout)
	return True, f"ping ok{scheduler}"


def _scheduler_detail(base: str, timeout: float) -> str:
	"""Best effort: note an inactive scheduler but never turn it into a hard failure."""
	try:
		response = requests.get(f"{base}{SCHEDULER_PATH}", timeout=timeout)
	except requests.RequestException:
		return ""
	if response.status_code != 200:
		return ""
	try:
		inactive = bool(response.json().get("message"))
	except ValueError:
		return ""
	return ", scheduler inactive" if inactive else ", scheduler active"


def _base_url(target_doctype: str, target_name: str) -> str | None:
	"""Resolve the base URL to probe: a Site's domain over HTTPS, or a Server's public IP."""
	doc: Any = frappe.get_doc(target_doctype, target_name)
	if target_doctype == "Site":
		domain = doc.get("domain") or target_name
		return f"https://{domain}"
	if target_doctype == "Server":
		host = doc.get("public_ip") or doc.get("private_ip")
		return f"http://{host}" if host else None
	return None
