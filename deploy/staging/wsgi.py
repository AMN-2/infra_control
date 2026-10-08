"""WSGI entry for the staging control plane's own gunicorn (deploy/staging/README.md).

The bench's main gunicorn serves other sites and is not restarted for staging work, so the
staging site gets a dedicated gunicorn on 127.0.0.1 with fresh code. The edge proxy in front of
it sets `X-Frappe-Site-Name`, which Frappe uses to pick the site. `/assets` and `/files` are
served here because no nginx sits in front.
"""

import os

import frappe.app

frappe.app._sites_path = os.environ.get("FRAPPE_SITES_PATH", os.getcwd())
application = frappe.app.application_with_statics()
