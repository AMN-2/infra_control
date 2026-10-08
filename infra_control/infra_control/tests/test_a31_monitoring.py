"""Integration (needs a site): metric storage, rollup, retention and the metrics.series API (A3.1)."""

from __future__ import annotations

import json
from datetime import timedelta

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from infra_control.api import metrics as metrics_api
from infra_control.core.enums import Resolution
from infra_control.install import after_install
from infra_control.monitoring import rollup

SERVER = "SRV-MON-TEST"


class TestA31Monitoring(FrappeTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		after_install()
		if not frappe.db.exists("Provider Account", "DO-MON-TEST"):
			frappe.get_doc(
				{
					"doctype": "Provider Account",
					"label": "DO-MON-TEST",
					"provider": "digitalocean",
					"api_token": "dop_v1_" + "0" * 64,
					"is_staging": 1,
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Server", SERVER):
			frappe.get_doc(
				{
					"doctype": "Server",
					"hostname": "mon-01.fra1",
					"provider_account": "DO-MON-TEST",
					"role": "all",
					"status": "Active",
				}
			).insert(ignore_permissions=True)
		cls._server_name = frappe.db.get_value("Server", {"hostname": "mon-01.fra1"}, "name")

	def tearDown(self) -> None:
		for name in frappe.get_all("Server Metric", filters={"server": self._server_name}, pluck="name"):
			frappe.delete_doc("Server Metric", name, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDown()

	def _write_minute(self, ts: object, cpu: float, backlog: int = 0) -> None:
		frappe.get_doc(
			{
				"doctype": "Server Metric",
				"server": self._server_name,
				"ts": ts,
				"resolution": "1m",
				"cpu": cpu,
				"ram": cpu,
				"disk": cpu,
				"load1": cpu / 100,
				"queue_backlog": backlog,
			}
		).insert(ignore_permissions=True)

	def test_rollup_folds_minutes_into_an_hour_and_is_idempotent(self) -> None:
		base = now_datetime().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
		for i, cpu in enumerate([10.0, 20.0, 30.0]):
			self._write_minute(add_to_date(base, minutes=i), cpu, backlog=i * 5)
		rollup.rollup_resolution(Resolution.ONE_HOUR)
		hourly = frappe.get_all(
			"Server Metric",
			filters={"server": self._server_name, "resolution": "1h"},
			fields=["cpu", "queue_backlog"],
		)
		self.assertEqual(len(hourly), 1)
		self.assertEqual(hourly[0]["cpu"], 20.0)  # average
		self.assertEqual(hourly[0]["queue_backlog"], 10)  # max of 0,5,10

		# A second rollup over the same data does not duplicate the hour bucket.
		rollup.rollup_resolution(Resolution.ONE_HOUR)
		self.assertEqual(
			frappe.db.count("Server Metric", {"server": self._server_name, "resolution": "1h"}), 1
		)

	def test_retention_purges_only_rows_past_their_window(self) -> None:
		fresh = add_to_date(now_datetime(), days=-1)
		stale = add_to_date(now_datetime(), days=-10)
		self._write_minute(fresh, 10.0)
		self._write_minute(stale, 20.0)
		deleted = rollup.purge_old_metrics()
		self.assertEqual(deleted["1m"], 1)  # the 10-day-old 1m row, not the fresh one
		remaining = frappe.get_all("Server Metric", filters={"server": self._server_name}, fields=["cpu"])
		self.assertEqual([r["cpu"] for r in remaining], [10.0])

	def test_metrics_series_returns_the_contract_shape(self) -> None:
		base = now_datetime().replace(second=0, microsecond=0) - timedelta(minutes=5)
		for i, cpu in enumerate([18.2, 21.0, 35.7]):
			self._write_minute(add_to_date(base, minutes=i), cpu)
		frappe.local.response = frappe._dict()
		metrics_api.series(
			server=self._server_name,
			metric="cpu",
			**{"from": base.isoformat(), "to": add_to_date(base, minutes=5).isoformat(), "resolution": "1m"},
		)
		result = dict(frappe.local.response)
		self.assertEqual(result.get("http_status_code"), 200)
		self.assertEqual(result["server"], self._server_name)
		self.assertEqual(result["metric"], "cpu")
		self.assertEqual(result["resolution"], "1m")
		self.assertEqual([p["value"] for p in result["points"]], [18.2, 21.0, 35.7])
		self.assertTrue(all(set(p) == {"ts", "value"} for p in result["points"]))
		# The whole body is JSON-serialisable (what the API handler returns).
		result.pop("http_status_code", None)
		json.dumps(result)
