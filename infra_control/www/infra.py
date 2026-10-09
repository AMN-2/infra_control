"""`/infra` and `/infra/<anything>`: the page that boots the Vue SPA (Q-B2).

- Requires a logged-in user; guests are sent to the in-app login (`/infra/login?redirect-to=`,
  ADR 0008), which renders this same page with guest boot data.
- Injects `window.csrf_token` and `window.infra_boot` for the frontend's API client.
- Loads the hashed bundle via the Vite manifest in `infra_control/public/frontend/`.
- Any sub-path renders this same page (`website_route_rules` in hooks.py), so the
  SPA router owns everything under `/infra/`.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

import frappe

from infra_control.core.boot import LOGIN_PATH, build_boot, guest_boot
from infra_control.core.spa import SpaNotBuiltError, load_assets

no_cache = 1
sitemap = 0


def is_login_path(path: str) -> bool:
	return path.rstrip("/") == LOGIN_PATH


def get_context(context: Any) -> None:
	path: str = getattr(getattr(frappe.local, "request", None), "path", None) or "/infra"
	guest = frappe.session.user == "Guest"
	if guest and not is_login_path(path):
		frappe.flags.redirect_location = f"{LOGIN_PATH}?redirect-to={quote_plus(path)}"
		redirect = frappe.Redirect()
		redirect.http_status_code = 302  # temporary: the same URL works once logged in
		raise redirect

	context.no_cache = 1
	context.title = "Infra Control"
	boot = guest_boot() if guest else build_boot()
	context.boot = boot.as_dict()
	context.csrf_token = boot.csrf_token

	try:
		assets = load_assets()
	except SpaNotBuiltError as exc:
		# Developer mode gets the reason on screen; otherwise log and show a neutral page.
		context.assets = None
		context.not_built_reason = str(exc) if frappe.conf.get("developer_mode") else ""
		frappe.log_error(title="Infra Control frontend not built", message=str(exc))
		return
	context.assets = assets
