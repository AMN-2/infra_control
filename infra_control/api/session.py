"""session.boot: the boot data `/infra` injects into the page, for the in-app login (ADR 0008).

The login screen posts credentials to Frappe's own `/api/method/login` (unchanged), then calls
this to pick up the CSRF token and the Infra roles of the new session without a page reload.
A session without any Infra role is refused like every other endpoint (403 permission_denied),
which the login screen reports as "no access" instead of showing an empty dashboard.
"""

from __future__ import annotations

from typing import Any

from infra_control.api import api
from infra_control.core.boot import build_boot


@api()
def boot() -> dict[str, Any]:
	return build_boot().as_dict()
