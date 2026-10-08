"""Integration (needs a site): `/infra` redirects guests and boots the SPA for users (Q-B2)."""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_test_client

from infra_control.core.permissions import INFRA_ADMIN


def _ensure_login_user(
	email: str = "infra.httptest@example.com",
	password: str = "infra-http-test-9427",  # noqa: S107 (test credential)
) -> tuple[str, str]:
	"""A System User with Infra Admin and a known password, for login in HTTP tests."""
	from frappe.utils.password import update_password

	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Infra HTTP Test",
				"user_type": "System User",
				"send_welcome_email": 0,
				"enabled": 1,
			}
		).insert(ignore_permissions=True)
	user = frappe.get_doc("User", email)
	if not any(r.role == INFRA_ADMIN for r in user.roles):
		user.append("roles", {"role": INFRA_ADMIN})
		user.save(ignore_permissions=True)
	update_password(email, password)
	frappe.db.commit()
	return email, password


class TestInfraPage(FrappeTestCase):
	def setUp(self) -> None:
		self.client = get_test_client()
		# The WSGI app resolves the site from the Host header; without it a bench whose default
		# site is not the test site answers for the wrong site (or 404s).
		self.host = {"Host": frappe.local.site}

	def test_guest_is_redirected_to_login(self) -> None:
		response = self.client.get("/infra/servers/SRV-0001", headers=self.host)
		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.headers["Location"], "/login?redirect-to=%2Finfra%2Fservers%2FSRV-0001")

	def test_logged_in_user_gets_the_page_on_any_subpath(self) -> None:
		sid = self._login(*_ensure_login_user())
		for path in ("/infra", "/infra/", "/infra/jobs/JOB-0001", "/infra/_design"):
			response = self.client.get(path, headers={**self.host, "Cookie": f"sid={sid}"})
			self.assertEqual(response.status_code, 200, path)
			body = response.get_data(as_text=True)
			self.assertIn("window.csrf_token", body)
			self.assertIn("window.infra_boot", body)
			self.assertNotIn("page-content", body, "must not be wrapped in the web base template")

	def _login(self, user: str, password: str) -> str:
		response = self.client.post(
			"/api/method/login", data={"usr": user, "pwd": password}, headers=self.host
		)
		self.assertEqual(response.status_code, 200)
		cookie = next(c for c in response.headers.getlist("Set-Cookie") if c.startswith("sid="))
		return cookie.split(";")[0].split("=", 1)[1]
