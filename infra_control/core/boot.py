"""Boot data for the SPA (ADR 0008).

`/infra` injects it into the page (`www/infra.py`); the in-app login screen signs in over XHR
and then fetches the same data from `api.session.boot` so the dashboard can start without a
page reload. Guests get a reduced record for the login page: no token, no roles.
"""

from __future__ import annotations

from typing import Any

import frappe
import frappe.sessions

from infra_control.core.permissions import ROLES, user_roles
from infra_control.core.spa import SpaBoot

LOGIN_PATH = "/infra/login"


def dev_socketio_port() -> int | None:
	"""Frappe's dev server (`bench serve`, DEV_SERVER=1) has no nginx routing /socket.io."""
	if not getattr(frappe.local, "dev_server", 0):
		return None
	port = frappe.conf.get("socketio_port")
	return int(port) if port else 9000


def build_boot() -> SpaBoot:
	"""Boot data for the logged-in user. Never call it for Guest."""
	return SpaBoot(
		csrf_token=frappe.sessions.get_csrf_token(),
		site_name=frappe.local.site,
		session_user=frappe.session.user,
		roles=tuple(r for r in ROLES if r in user_roles()),
		socketio_port=dev_socketio_port(),
	)


def guest_boot() -> SpaBoot:
	"""Boot data for the login page: identifies the site and whether Frappe's own login page
	offers other sign-in methods (social login, LDAP) the in-app form cannot."""
	return SpaBoot(
		csrf_token="",
		site_name=frappe.local.site,
		session_user="Guest",
		roles=(),
		socketio_port=dev_socketio_port(),
		extra={"login_alternatives": login_alternatives()},
	)


def login_alternatives() -> bool:
	try:
		if frappe.get_all("Social Login Key", filters={"enable_social_login": 1}, limit=1):
			return True
		enabled: Any = frappe.db.get_value("LDAP Settings", "LDAP Settings", "enabled")
		return bool(int(enabled or 0))
	except Exception:
		return False
