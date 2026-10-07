"""Integration (needs a site): the real HTTP shape of the read API through Frappe's handler."""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_test_client

from infra_control.install import after_install

BASE = "/api/method/infra_control.api."


class TestA14Api(FrappeTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		after_install()
		frappe.db.commit()
		cls.client = get_test_client()
		cls.host = {"Host": frappe.local.site}

	def _login(self) -> dict[str, str]:
		response = self.client.post(
			"/api/method/login",
			data={"usr": "Administrator", "pwd": frappe.conf.admin_password or "admin"},
			headers=self.host,
		)
		self.assertEqual(response.status_code, 200)
		cookie = next(c for c in response.headers.getlist("Set-Cookie") if c.startswith("sid="))
		return {**self.host, "Cookie": cookie.split(";")[0]}

	def test_success_bodies_are_top_level_json(self) -> None:
		headers = self._login()
		response = self.client.get(f"{BASE}playbooks.list", headers=headers)
		self.assertEqual(response.status_code, 200)
		body = response.get_json()
		self.assertNotIn("message", body)
		self.assertNotIn("docs", body)
		self.assertIn("items", body)
		self.assertTrue(any(p["key"] == "site.migrate" for p in body["items"]))

	def test_error_envelope_and_status(self) -> None:
		headers = self._login()
		response = self.client.get(f"{BASE}servers.get?server=SRV-9999", headers=headers)
		self.assertEqual(response.status_code, 404)
		self.assertEqual(response.get_json()["error"]["code"], "not_found")
		response = self.client.get(f"{BASE}servers.list?status=Nope", headers=headers)
		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.get_json()["error"]["code"], "validation_error")

	def test_guest_gets_frappe_shaped_403(self) -> None:
		response = self.client.get(f"{BASE}overview.summary", headers=self.host)
		self.assertEqual(response.status_code, 403)
		self.assertNotIn("error", response.get_json())
