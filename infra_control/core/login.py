"""Where an Infra user lands after login.

`/infra` is the home of anyone holding an Infra role. Frappe's login page honours an explicit
`redirect-to`; without one (the user opened `/` or `/login` directly) other apps on a shared
site decide the landing page through their own `on_session_creation` hooks. This hook runs
last (`infra_control` is installed last) and sends Infra users to `/infra` unless they asked
for another page.
"""

from __future__ import annotations

from typing import Any

import frappe

from infra_control.core.permissions import ROLES, user_roles

HOME = "/infra"


def requested_redirect() -> str:
	form: Any = getattr(frappe, "form_dict", None) or {}
	value = form.get("redirect_to") or form.get("redirect-to") or ""
	return str(value).strip()


def on_session_creation(login_manager: Any = None) -> None:
	user = str(frappe.session.user or "")
	if not user or user == "Guest":
		return
	if not any(r in user_roles(user) for r in ROLES):
		return
	wanted = requested_redirect()
	if wanted and not wanted.startswith("/login"):
		return  # the login page redirects there itself
	frappe.cache().hset("redirect_after_login", user, HOME)
