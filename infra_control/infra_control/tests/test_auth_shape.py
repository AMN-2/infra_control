"""Integration (needs a site): the Frappe framework error shapes the contract documents.

contracts/openapi.yaml (`FrappeFrameworkError`) promises how a client tells "re-authenticate" from
"permission denied". This pins the real behaviour of the installed Frappe version so a framework
upgrade that changes it fails CI instead of the UI. Uses a core whitelisted method because the
infra_control API lands in Phase 1.
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_test_client

METHOD = "/api/method/frappe.client.get_count"


class TestAuthShape(FrappeTestCase):
	def setUp(self) -> None:
		self.client = get_test_client()
		self.host = {"Host": frappe.local.site}

	def _get(self, **headers: str):  # returns a werkzeug TestResponse
		return self.client.get(f"{METHOD}?doctype=User", headers={**self.host, **headers})

	def test_guest_gets_403_permission_error_without_envelope(self) -> None:
		response = self._get()
		self.assertEqual(response.status_code, 403)
		body = response.get_json()
		self.assertEqual(body["exc_type"], "PermissionError")
		self.assertNotIn("error", body)

	def test_expired_or_invalid_session_cookie_is_treated_as_guest(self) -> None:
		response = self._get(Cookie="sid=deadbeefdeadbeefdeadbeefdeadbeef")
		self.assertEqual(response.status_code, 403)
		self.assertEqual(response.get_json()["exc_type"], "PermissionError")

	def test_invalid_api_token_gets_401_authentication_error(self) -> None:
		response = self._get(Authorization="token not-a-key:not-a-secret")
		self.assertEqual(response.status_code, 401)
		body = response.get_json()
		self.assertEqual(body["exc_type"], "AuthenticationError")
		self.assertNotIn("error", body)

	def test_csrf_error_is_400(self) -> None:
		self.assertEqual(frappe.CSRFTokenError.http_status_code, 400)
		self.assertEqual(frappe.PermissionError.http_status_code, 403)
		self.assertEqual(frappe.AuthenticationError.http_status_code, 401)
