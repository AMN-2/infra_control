"""WSGI entry for the staging control plane's own gunicorn (deploy/staging/README.md).

The bench's main gunicorn serves other sites and is not restarted for staging work, so the
staging site gets a dedicated gunicorn on 127.0.0.1 with fresh code. This gunicorn serves one
site only, so requests without `X-Frappe-Site-Name` (Frappe's realtime server calling back to
authenticate a socket) get it by default. `/assets` and `/files` are served here because no nginx
sits in front, and the edge proxy's `X-Forwarded-Proto` is honoured so redirects keep https.
"""

import os

import frappe.app
from werkzeug.middleware.proxy_fix import ProxyFix

SITE = os.environ.get("INFRA_SITE", "ops-staging.localhost")
frappe.app._sites_path = os.environ.get("FRAPPE_SITES_PATH", os.getcwd())
_inner = ProxyFix(frappe.app.application_with_statics(), x_proto=1)


def application(environ, start_response):  # type: ignore[no-untyped-def]
	environ.setdefault("HTTP_X_FRAPPE_SITE_NAME", SITE)
	return _inner(environ, start_response)
