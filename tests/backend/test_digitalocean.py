"""A2.1: DigitalOcean client, mapping, Spaces wrapper and adapter. No network, no Frappe site."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
import responses
from botocore.exceptions import ClientError

from infra_control.core.enums import PROVIDER_CAPABILITIES, Capability, ServerRole, ServerStatus
from infra_control.core.enums import Provider as ProviderName
from infra_control.core.errors import NotFound, NotSupported, ProviderError, RateLimited, ValidationError
from infra_control.providers import registry
from infra_control.providers.base import OpRef, OpState, OpStatus, OpStep, ProviderConfig
from infra_control.providers.digitalocean import mapping
from infra_control.providers.digitalocean.adapter import (
	FIREWALL_NAME,
	KIND_ACTION,
	KIND_ANSIBLE,
	KIND_PROVISION,
	DigitalOceanProvider,
	firewall_rules,
	render_cloud_init,
)
from infra_control.providers.digitalocean.client import API_BASE, DigitalOceanClient
from infra_control.providers.digitalocean.runner import UnavailableRunner
from infra_control.providers.digitalocean.settings import ControllerSettings
from infra_control.providers.digitalocean.spaces import (
	SpacesClient,
	SpacesConfig,
	location,
	parse_location,
)

TOKEN = "dop_v1_" + "a" * 64
CONFIG = ProviderConfig(
	account="DO-STAGING", provider=ProviderName.DIGITALOCEAN, api_token=TOKEN, is_staging=True
)


def url(path: str) -> str:
	return f"{API_BASE}/{path}"


def sent(method: str, path: str) -> list[dict[str, Any]]:
	"""JSON bodies of every request made to `path` with `method`, in order."""
	import json

	out: list[dict[str, Any]] = []
	for c in responses.calls:
		if c.request.method == method and (c.request.url or "").split("?")[0] == url(path):
			raw = c.request.body or b"{}"
			out.append(json.loads(raw if isinstance(raw, (bytes, str)) else b"{}"))
	return out


def client(**kw: Any) -> tuple[DigitalOceanClient, list[float]]:
	slept: list[float] = []
	return DigitalOceanClient(TOKEN, sleep=slept.append, clock=lambda: 1000.0, **kw), slept


# --- client --------------------------------------------------------------------------------
@responses.activate
def test_client_sends_bearer_token_and_timeout() -> None:
	responses.get(url("droplets/1"), json={"droplet": {"id": 1}})
	c, _ = client()
	assert c.get_droplet(1) == {"id": 1}
	req = responses.calls[0].request
	assert req.headers["Authorization"] == f"Bearer {TOKEN}"
	assert TOKEN not in repr(c.__dict__.get("rate_limit"))


@responses.activate
def test_client_retries_5xx_with_jitter_then_succeeds() -> None:
	responses.get(url("actions/9"), status=503)
	responses.get(url("actions/9"), status=502)
	responses.get(url("actions/9"), json={"action": {"id": 9, "status": "completed"}})
	c, slept = client()
	assert c.get_action(9)["status"] == "completed"
	assert len(responses.calls) == 3
	assert len(slept) == 2 and all(0 <= s <= 20 for s in slept)


@responses.activate
def test_client_honours_retry_after_on_429_and_gives_up_bounded() -> None:
	for _ in range(3):
		responses.get(url("actions/9"), status=429, headers={"Retry-After": "7"})
	c, slept = client(max_attempts=3)
	with pytest.raises(RateLimited) as err:
		c.get_action(9)
	assert slept == [7.0, 7.0]
	assert err.value.http_status == 429


@responses.activate
def test_client_maps_4xx_to_provider_errors_without_leaking_the_token() -> None:
	responses.get(url("droplets/404"), status=404, json={"id": "not_found", "message": "gone"})
	responses.post(url("droplets"), status=422, json={"id": "unprocessable_entity", "message": "bad size"})
	c, _ = client()
	with pytest.raises(NotFound):
		c.get_droplet(404)
	with pytest.raises(ProviderError) as err:
		c.create_droplet({"name": "x"})
	assert err.value.details == {"status": 422, "id": "unprocessable_entity", "message": "bad size"}
	assert TOKEN not in str(err.value) + str(err.value.details)


@responses.activate
def test_client_network_errors_are_retried_then_reported() -> None:
	import requests

	responses.get(url("droplets/1"), body=requests.ConnectionError("reset"))
	responses.get(url("droplets/1"), body=requests.ConnectionError("reset"))
	c, slept = client(max_attempts=2)
	with pytest.raises(ProviderError, match="unreachable"):
		c.get_droplet(1)
	assert len(slept) == 1


@responses.activate
def test_client_waits_for_the_rate_limit_window_when_nearly_exhausted() -> None:
	responses.get(
		url("droplets/1"),
		json={"droplet": {"id": 1}},
		headers={"RateLimit-Limit": "5000", "RateLimit-Remaining": "10", "RateLimit-Reset": "1030"},
	)
	responses.get(url("droplets/2"), json={"droplet": {"id": 2}})
	c, slept = client()
	c.get_droplet(1)
	assert c.rate_limit.remaining == 10
	c.get_droplet(2)
	assert slept == [30.0]


@responses.activate
def test_client_follows_pagination() -> None:
	responses.get(
		url("droplets"),
		json={"droplets": [{"id": 1}], "links": {"pages": {"next": url("droplets?page=2&per_page=200")}}},
		match=[responses.matchers.query_param_matcher({"per_page": "200", "tag_name": "infra-control"})],
	)
	responses.get(url("droplets?page=2&per_page=200"), json={"droplets": [{"id": 2}], "links": {}})
	c, _ = client()
	assert [d["id"] for d in c.list_droplets(tag="infra-control")] == [1, 2]


# --- mapping -------------------------------------------------------------------------------
def test_status_mapping_stays_inside_the_package() -> None:
	assert mapping.server_status("new") is ServerStatus.PROVISIONING
	assert mapping.server_status("active") is ServerStatus.ACTIVE
	assert mapping.server_status("off") is ServerStatus.DOWN
	assert mapping.server_status("archive") is ServerStatus.ARCHIVED
	assert mapping.server_status("weird") is ServerStatus.DEGRADED
	assert mapping.action_state("in-progress") is OpState.RUNNING
	assert mapping.action_state("completed") is OpState.SUCCESS
	assert mapping.action_state("errored") is OpState.FAILED


DROPLET = {
	"id": 412345678,
	"name": "app-03.fra1",
	"status": "active",
	"created_at": "2026-10-07T09:00:00Z",
	"region": {"slug": "fra1"},
	"size": {"slug": "s-4vcpu-8gb"},
	"tags": ["infra-control", "role:app", "staging", "client-a"],
	"networks": {
		"v4": [
			{"type": "private", "ip_address": "10.114.0.5"},
			{"type": "public", "ip_address": "164.92.10.13"},
		]
	},
}


def test_normalize_droplet() -> None:
	n = mapping.normalize_droplet(DROPLET)
	assert n == {
		"provider_ref": "412345678",
		"hostname": "app-03.fra1",
		"status": ServerStatus.ACTIVE,
		"public_ip": "164.92.10.13",
		"private_ip": "10.114.0.5",
		"region": "fra1",
		"size": "s-4vcpu-8gb",
		"role": ServerRole.APP,
		"tags": ["staging", "client-a"],
		"created_at": datetime(2026, 10, 7, 9, 0, tzinfo=UTC),
	}
	assert mapping.tags_for("db", ["x", "infra-control"], staging=True) == [
		"infra-control",
		"role:db",
		"staging",
		"x",
	]
	assert mapping.role_from_tags(["role:nope"]) is ServerRole.ALL


def _series(*entries: tuple[str, list[tuple[float, float]]]) -> dict[str, Any]:
	return {
		"status": "success",
		"data": {
			"result": [
				{"metric": {"mode": mode} if mode else {}, "values": [[ts, str(v)] for ts, v in pts]}
				for mode, pts in entries
			]
		},
	}


def test_metric_math() -> None:
	cpu = _series(
		("idle", [(0, 100), (60, 130)]), ("user", [(0, 50), (60, 80)]), ("system", [(0, 10), (60, 20)])
	)
	assert mapping.cpu_percent(cpu) == pytest.approx(57.1, abs=0.1)
	assert mapping.cpu_percent(_series(("idle", [(0, 1)]))) is None
	assert mapping.latest_value(_series(("", [(0, 4.0), (60, 8.0)]))) == 8.0
	assert mapping.latest_value({}) is None
	assert mapping.percent_used(8.0, 2.0) == 75.0
	assert mapping.percent_used(None, 2.0) is None


# --- spaces --------------------------------------------------------------------------------
class _FakeS3:
	def __init__(self) -> None:
		self.objects: dict[str, int] = {}

	def upload_file(self, path: str, bucket: str, key: str) -> None:
		self.objects[key] = 2 * 1024 * 1024

	def download_file(self, bucket: str, key: str, path: str) -> None:
		if key not in self.objects:
			raise ClientError({"Error": {"Code": "404"}}, "GetObject")

	def head_object(self, Bucket: str, Key: str) -> dict[str, Any]:
		if Key not in self.objects:
			raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
		return {}

	def delete_object(self, Bucket: str, Key: str) -> None:
		self.objects.pop(Key, None)

	def get_paginator(self, name: str) -> Any:
		objects = self.objects

		class _P:
			def paginate(self, Bucket: str, Prefix: str) -> list[dict[str, Any]]:
				return [
					{"Contents": [{"Key": k, "Size": v} for k, v in objects.items() if k.startswith(Prefix)]}
				]

		return _P()


def test_spaces_round_trip_and_locations() -> None:
	cfg = SpacesConfig(bucket="scq-backups", region="fra1", key="AK", secret="SK")
	assert "SK" not in repr(cfg) and cfg.endpoint == "https://fra1.digitaloceanspaces.com"
	s3 = _FakeS3()
	sp = SpacesClient(cfg, client=s3)
	loc = sp.upload("/tmp/x.sql.gz", "demo.iq/20261007-x.sql.gz")
	assert loc == "spaces://scq-backups/demo.iq/20261007-x.sql.gz"
	assert parse_location(loc) == ("scq-backups", "demo.iq/20261007-x.sql.gz")
	assert sp.exists("demo.iq/20261007-x.sql.gz") and not sp.exists("nope")
	assert [o.size_mb for o in sp.list("demo.iq/")] == [2.0]
	with pytest.raises(ProviderError):
		sp.download("nope", "/tmp/y")
	sp.delete("demo.iq/20261007-x.sql.gz")
	assert sp.list() == []
	assert location("b", "k") == "spaces://b/k"
	with pytest.raises(ProviderError):
		parse_location("s3://b/k")


# --- adapter -------------------------------------------------------------------------------
class _FakeRunner:
	def __init__(self, final: OpState = OpState.SUCCESS) -> None:
		self.started: list[tuple[dict[str, Any], str, dict[str, Any]]] = []
		self.final = final
		self.polls = 0
		self.cancelled: list[OpRef] = []
		self.results: dict[str, Any] = {}
		self.unreachable_hosts: list[str] = []

	def start(
		self,
		server: dict[str, Any],
		playbook_file: str,
		extra_vars: dict[str, Any] | None = None,
		*,
		start_at_task: str | None = None,
	) -> OpRef:
		self.started.append((server, playbook_file, dict(extra_vars or {})))
		return OpRef("digitalocean", KIND_ANSIBLE, f"run-{len(self.started)}")

	def start_many(
		self,
		servers: list[dict[str, Any]],
		playbook_file: str,
		extra_vars: dict[str, Any] | None = None,
		*,
		start_at_task: str | None = None,
	) -> OpRef:
		self.started.append(
			({"servers": [s["name"] for s in servers]}, playbook_file, dict(extra_vars or {}))
		)
		return OpRef("digitalocean", KIND_ANSIBLE, f"run-{len(self.started)}")

	results: dict[str, Any] = {}
	unreachable_hosts: list[str] = []

	def read_results(self, op: OpRef) -> dict[str, Any]:
		return dict(self.results)

	def unreachable(self, op: OpRef) -> list[str]:
		return list(self.unreachable_hosts)

	def status(self, op: OpRef) -> OpStatus:
		self.polls += 1
		if self.polls < 2:
			return OpStatus(OpState.RUNNING, (OpStep("Role base", OpState.RUNNING),))
		return OpStatus(
			self.final,
			(OpStep("Role base", self.final, output="ok\n"),),
			error=None if self.final is OpState.SUCCESS else "role failed",
		)

	def cancel(self, op: OpRef) -> bool:
		self.cancelled.append(op)
		return True


SERVER = {
	"name": "SRV-0001",
	"hostname": "app-01.fra1",
	"provider_ref": "412345678",
	"public_ip": "164.92.10.11",
	"private_ip": None,
	"ssh_user": "frappe",
	"ssh_port": 22,
	"role": "all",
	"region": "fra1",
	"size": "s-4vcpu-8gb",
}


class FakeS3Presign(_FakeS3):
	def generate_presigned_url(self, method: str, Params: dict[str, str], ExpiresIn: int) -> str:
		return f"https://signed/{method}/{Params['Key']}?X-Amz-Signature=sig&expires={ExpiresIn}"

	def head_object(self, Bucket: str, Key: str) -> dict[str, Any]:
		if Key not in self.objects:
			raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
		return {"ContentLength": self.objects[Key]}


class FakeRecords:
	def __init__(self, with_spaces: bool = True) -> None:
		self.calls: list[tuple[str, tuple[Any, ...]]] = []
		self.s3 = FakeS3Presign()
		self.client = (
			SpacesClient(
				SpacesConfig(bucket="scq-backups", region="fra1", key="AK", secret="SK"), client=self.s3
			)
			if with_spaces
			else None
		)
		self.backup_sets: dict[str, dict[str, str]] = {}
		self.public_key = "ssh-ed25519 AAAA controller infra-control@ops-staging"

	def record_server(self, account: str, droplet: dict[str, Any]) -> str:
		self.calls.append(("server", (account, droplet["provider_ref"])))
		return "SRV-0009"

	def record_site(self, domain: str, bench: str) -> str:
		self.calls.append(("site", (domain, bench)))
		return domain

	def record_bench(self, account: str, server: str, path: str) -> str:
		self.calls.append(("bench", (account, server, path)))
		return "BENCH-0009"

	def controller_public_key(self) -> str:
		return self.public_key

	def record_backup(self, site: str, kind: str, location: str, size_mb: float, job_ref: str) -> str:
		self.calls.append(("backup", (site, kind, location, size_mb)))
		return "BKP-1"

	def record_domain(self, site: str, domain: str) -> None:
		self.calls.append(("domain", (site, domain)))

	def record_bench_app(self, bench: str, app: str, branch: str) -> None:
		self.calls.append(("bench_app", (bench, app, branch)))

	def archive_site(self, site: str) -> None:
		self.calls.append(("archive_site", (site,)))

	def record_restore_test(self, backup: str, ok: bool) -> None:
		self.calls.append(("restore_test", (backup, ok)))

	def archive_server(self, server: str) -> None:
		self.calls.append(("archive_server", (server,)))

	live_sites: list[str] = []

	def live_sites_on_server(self, server: str) -> list[str]:
		return list(self.live_sites)

	def load_backup_set(self, backup: str) -> dict[str, str]:
		return self.backup_sets[backup]

	def spaces_client(self) -> SpacesClient | None:
		return self.client

	def reconcile(self, account: str, provider: str, inventory: dict[str, Any]) -> dict[str, Any]:
		self.calls.append(("reconcile", (account, provider, inventory)))
		return {
			"servers_created": len(inventory["servers"]),
			"benches_created": len(inventory["benches"]),
			"sites_created": len(inventory["sites"]),
			"findings": [
				{"kind": "server_unreachable", "doctype": "Server", "name": h, "detail": "unreachable"}
				for h in inventory.get("unreachable", [])
			],
		}


def adapter(
	runner: Any = None,
	controller_ip: str | None = "203.0.113.10",
	spaces: SpacesConfig | None = None,
	records: FakeRecords | None = None,
) -> DigitalOceanProvider:
	return DigitalOceanProvider(
		CONFIG,
		client=DigitalOceanClient(TOKEN, sleep=lambda s: None, clock=lambda: 1_000_000.0),
		runner=runner or _FakeRunner(),
		settings_loader=lambda: ControllerSettings(controller_ip=controller_ip, spaces=spaces),
		server_loader=lambda name: {**SERVER, "name": name},
		site_loader=lambda name: {
			"name": name,
			"domain": name,
			"bench": "BENCH-0001",
			"bench_path": "/home/frappe/v15",
			"server": "SRV-0001",
		},
		bench_loader=lambda name: {
			"name": name,
			"title": "v15",
			"path": "/home/frappe/v15",
			"server": "SRV-0001",
		},
		records=records or FakeRecords(),
		console_ca_loader=lambda: "ssh-ed25519 AAAATESTCA console-ca",
		clock=lambda: 1_000_000.0,
	)


def test_adapter_registers_with_the_plan_capabilities() -> None:
	assert registry.adapter_class("digitalocean") is DigitalOceanProvider
	assert DigitalOceanProvider.capabilities == PROVIDER_CAPABILITIES[ProviderName.DIGITALOCEAN]
	a = adapter()
	with pytest.raises(NotSupported):
		a.require(Capability.MANAGED_BACKUP)


@responses.activate
def test_reboot_and_snapshot_are_polled_droplet_actions() -> None:
	responses.post(
		url("droplets/412345678/actions"),
		json={"action": {"id": 77, "status": "in-progress", "type": "reboot"}},
	)
	responses.post(
		url("droplets/412345678/actions"),
		json={"action": {"id": 78, "status": "in-progress", "type": "snapshot"}},
	)
	responses.get(
		url("actions/77"),
		json={
			"action": {
				"id": 77,
				"status": "in-progress",
				"type": "reboot",
				"started_at": "2026-10-07T09:00:00Z",
			}
		},
	)
	responses.get(
		url("actions/77"),
		json={
			"action": {
				"id": 77,
				"status": "completed",
				"type": "reboot",
				"started_at": "2026-10-07T09:00:00Z",
				"completed_at": "2026-10-07T09:00:40Z",
			}
		},
	)
	responses.get(url("actions/78"), json={"action": {"id": 78, "status": "errored", "type": "snapshot"}})
	a = adapter()
	ref = a.call("reboot_server", server="SRV-0001")
	assert ref == OpRef("digitalocean", KIND_ACTION, "77")
	assert a.get_status(ref).state is OpState.RUNNING
	done = a.get_status(ref)
	assert done.state is OpState.SUCCESS and done.steps[0].name == "Reboot"
	assert done.steps[0].ended_at == datetime(2026, 10, 7, 9, 0, 40, tzinfo=UTC)
	snap = a.call("snapshot_server", server="SRV-0001")
	snap_body = sent("POST", "droplets/412345678/actions")[-1]
	assert snap_body["type"] == "snapshot" and snap_body["name"].startswith("app-01.fra1-")
	failed = a.get_status(snap)
	assert failed.state is OpState.FAILED and failed.error and "78" in failed.error
	assert a.cancel(ref) is False


@responses.activate
def test_create_server_end_to_end_with_firewall_and_configure() -> None:
	responses.get(
		url("account/keys"),
		json={
			"ssh_keys": [{"id": 5, "name": "infra-control", "public_key": "ssh-ed25519 AAAA controller"}],
			"links": {},
		},
	)
	responses.post(
		url("droplets"),
		json={
			"droplet": {"id": 999, "name": "app-03.fra1", "status": "new"},
			"links": {"actions": [{"id": 1}]},
		},
	)
	responses.get(url("droplets/999"), json={"droplet": {**DROPLET, "id": 999, "status": "new"}})
	responses.get(url("droplets/999"), json={"droplet": {**DROPLET, "id": 999}})
	responses.get(url("firewalls"), json={"firewalls": [], "links": {}})
	responses.post(url("firewalls"), json={"firewall": {"id": "fw-1", "name": FIREWALL_NAME}})
	responses.get(url("droplets/999"), json={"droplet": {**DROPLET, "id": 999}})
	runner, records = _FakeRunner(), FakeRecords()
	a = adapter(runner, records=records)
	ref = a.call(
		"create_server",
		hostname="app-03.fra1",
		region="fra1",
		size="s-4vcpu-8gb",
		role="app",
		tags=["client-a"],
	)
	assert ref == OpRef("digitalocean", KIND_PROVISION, "999")
	spec = sent("POST", "droplets")[0]
	assert spec["ssh_keys"] == [5] and spec["tags"] == ["infra-control", "role:app", "staging", "client-a"]
	assert "disable_root: true" in spec["user_data"] and "ssh-ed25519 AAAA controller" in spec["user_data"]

	first = a.get_status(ref)
	assert first.state is OpState.RUNNING
	assert [(s.name, s.state) for s in first.steps] == [
		("Create droplet", OpState.RUNNING),
		("Attach managed firewall", OpState.QUEUED),
		("Configure server", OpState.QUEUED),
	]
	second = a.get_status(ref)
	assert second.state is OpState.RUNNING
	assert [s.name for s in second.steps[:2]] == ["Create droplet", "Attach managed firewall"]
	fw_body = sent("POST", "firewalls")[0]
	assert fw_body["droplet_ids"] == [999]
	assert fw_body["inbound_rules"][0]["sources"]["addresses"] == ["203.0.113.10/32"]
	assert (
		runner.started[0][1] == "server_provision.yml" and runner.started[0][0]["public_ip"] == "164.92.10.13"
	)
	third = a.get_status(ref)
	assert third.state is OpState.SUCCESS and third.created == ("Server", "999")
	# A2.3: the Server document is recorded so the engine can link the job to it (ADR 0001).
	assert records.calls == [
		("server", ("DO-STAGING", "999")),
		("bench", ("DO-STAGING", "SRV-0009", "/home/frappe/frappe-bench")),
	]
	assert runner.started[0][2] == {
		"hostname": "app-03.fra1",
		"bench_init": True,
		"ca_public_key": "ssh-ed25519 AAAATESTCA console-ca",
	}
	assert a.cancel(ref) is True


@responses.activate
def test_create_server_refuses_without_controller_ip_or_ssh_key() -> None:
	responses.get(url("account/keys"), json={"ssh_keys": [], "links": {}})
	with pytest.raises(ProviderError, match="SSH public key is not on this"):
		adapter().call("create_server", hostname="h.fra1", region="fra1", size="s-1")
	with pytest.raises(ValidationError):
		adapter().call("create_server", hostname="", region="fra1", size="s-1")

	responses.get(
		url("account/keys"),
		json={"ssh_keys": [{"id": 5, "name": "infra-control", "public_key": "k"}], "links": {}},
	)
	responses.post(url("droplets"), json={"droplet": {"id": 7, "status": "new"}})
	responses.get(url("droplets/7"), json={"droplet": {**DROPLET, "id": 7}})
	a = adapter(controller_ip=None)
	ref = a.call("create_server", hostname="h.fra1", region="fra1", size="s-1")
	with pytest.raises(ProviderError, match="controller_ip"):
		a.get_status(ref)


@responses.activate
def test_existing_firewall_is_updated_and_droplet_attached_once() -> None:
	stale = {"id": "fw-1", "name": FIREWALL_NAME, "inbound_rules": [], "droplet_ids": [1]}
	responses.get(url("firewalls"), json={"firewalls": [stale], "links": {}})
	responses.put(url("firewalls/fw-1"), json={"firewall": stale})
	responses.post(url("firewalls/fw-1/droplets"), status=204)
	a = adapter()
	assert a._ensure_firewall(999) == "fw-1"
	assert [c.request.method for c in responses.calls] == ["GET", "PUT", "POST"]
	assert firewall_rules("1.2.3.4")["inbound_rules"][0]["ports"] == "22"


def test_site_and_service_methods_go_through_the_runner() -> None:
	runner = _FakeRunner()
	spaces = SpacesConfig(bucket="b", region="fra1", key="k", secret="s")
	a = adapter(runner, spaces=spaces)
	a.call("backup_site", site="demo.iq", with_files=False)
	a.call("update_site", site="demo.iq")
	a.call("set_maintenance", site="demo.iq", on=True)
	a.call("create_site", site="new.iq", bench="BENCH-0001", apps=["erpnext"])
	a.call("control_service", server="SRV-0001", service="nginx", action="reload")
	files = [r[1] for r in runner.started]
	assert files == [
		"site_backup.yml",
		"site_migrate.yml",
		"site_maintenance.yml",
		"site_create.yml",
		"service_control.yml",
	]
	backup_vars = runner.started[0][2]
	# Presigned upload URLs only: the Spaces keys never reach the server.
	assert backup_vars["with_files"] is False and list(backup_vars["backup_urls"]) == ["database"]
	assert "SK" not in str(backup_vars) and "AK" not in str(backup_vars)
	assert runner.started[3][2]["apps"] == ["erpnext"]
	with pytest.raises(ValidationError):
		a.call("control_service", server="SRV-0001", service="sshd", action="restart")


def test_unavailable_runner_fails_loudly_never_silently() -> None:
	a = adapter(UnavailableRunner())
	with pytest.raises(ProviderError, match="ansible-runner is not installed"):
		a.call("update_site", site="demo.iq")
	with pytest.raises(ProviderError):
		a.get_status(OpRef("digitalocean", KIND_ANSIBLE, "x"))
	with pytest.raises(ProviderError):
		a.get_status(OpRef("digitalocean", "mystery", "x"))


@responses.activate
def test_get_metrics_and_sync_inventory() -> None:
	cpu = _series(
		("idle", [(0, 100), (60, 130)]), ("user", [(0, 50), (60, 80)]), ("system", [(0, 10), (60, 20)])
	)
	for metric, body in [
		("cpu", cpu),
		("memory_total", _series(("", [(60, 8.0)]))),
		("memory_available", _series(("", [(60, 2.0)]))),
		("filesystem_size", _series(("", [(60, 100.0)]))),
		("filesystem_free", _series(("", [(60, 46.0)]))),
		("load_1", _series(("", [(60, 0.8123)]))),
	]:
		responses.get(url(f"monitoring/metrics/droplet/{metric}"), json=body)
	a = adapter()
	m = a.call("get_metrics", server="SRV-0001")
	assert (m["cpu"], m["ram"], m["disk"], m["load1"]) == (pytest.approx(57.1, abs=0.1), 75.0, 54.0, 0.81)
	assert responses.calls[0].request.params["host_id"] == "412345678"


def test_cloud_init_is_key_only() -> None:
	text = render_cloud_init("h.fra1", "frappe", "ssh-ed25519 KEY\n")
	assert "hostname: h.fra1" in text and "- ssh-ed25519 KEY" in text
	assert "PermitRootLogin no" in text and "ssh_pwauth: false" in text


@responses.activate
def test_ssh_key_is_found_by_key_material_not_by_name() -> None:
	"""A2.6: the staging team named the key 'infra-control staging'; the name must not matter."""
	responses.get(
		url("account/keys"),
		json={
			"ssh_keys": [
				{"id": 1, "name": "someone else", "public_key": "ssh-ed25519 BBBB other"},
				{
					"id": 2,
					"name": "infra-control staging",
					"public_key": "ssh-ed25519 AAAA controller laptop",
				},
			],
			"links": {},
		},
	)
	assert adapter()._ssh_key()["id"] == 2

	records = FakeRecords()
	records.public_key = ""  # unreadable controller key: fall back to the conventional name
	responses.get(
		url("account/keys"),
		json={
			"ssh_keys": [{"id": 3, "name": "infra-control", "public_key": "ssh-ed25519 CCCC x"}],
			"links": {},
		},
	)
	assert adapter(records=records)._ssh_key()["id"] == 3


@responses.activate
def test_sync_inventory_reconciles_at_once_when_no_server_is_reachable() -> None:
	# No managed droplets: nothing to discover, reconcile the (empty) API result immediately.
	responses.get(url("droplets"), json={"droplets": [], "links": {}})
	runner, records = _FakeRunner(), FakeRecords()
	a = adapter(runner, records=records)
	result = a.call("sync_inventory")
	assert not isinstance(result, OpRef)
	assert result["servers_created"] == 0
	assert runner.started == []  # no discovery run
	assert records.calls[-1][0] == "reconcile"


@responses.activate
def test_sync_inventory_discovers_hosts_then_reconciles() -> None:
	responses.get(url("droplets"), json={"droplets": [DROPLET], "links": {}})
	responses.get(url("droplets"), json={"droplets": [DROPLET], "links": {}})
	runner, records = _FakeRunner(), FakeRecords()
	a = adapter(runner, records=records)

	ref = a.call("sync_inventory")
	assert isinstance(ref, OpRef) and ref.kind == "sync"
	# The discovery run targets the active, reachable droplet.
	assert runner.started[0][1] == "inventory_discover.yml"
	assert runner.started[0][0] == {"servers": ["app-03.fra1"]}

	# First poll: discovery still running -> the API step plus the inner step, no reconcile.
	running = a.get_status(ref)
	assert running.state is OpState.RUNNING
	assert running.steps[0].name == "List servers at DigitalOcean"
	assert records.calls == []

	# Discovery finished: the runner returns results and one unreachable host.
	runner.results = {
		"app-03.fra1": {
			"benches": [
				{
					"path": "/home/frappe/frappe-bench",
					"frappe_version": "15.1",
					"apps": [],
					"sites": [{"domain": "x.iq", "maintenance_mode": False}],
				}
			]
		}
	}
	runner.unreachable_hosts = ["ghost.fra1"]
	done = a.get_status(ref)
	assert done.state is OpState.SUCCESS
	(call,) = [c for c in records.calls if c[0] == "reconcile"]
	inv = call[1][2]
	assert [b["path"] for b in inv["benches"]] == ["/home/frappe/frappe-bench"]
	assert [s["domain"] for s in inv["sites"]] == ["x.iq"]
	assert inv["unreachable"] == ["ghost.fra1"]
	# The droplet id, not the hostname, identifies the discovered server.
	assert inv["discovered"] == ["412345678"]
	assert done.steps[-1].name == "Reconcile documents"
	# A later poll does not reconcile twice.
	a.get_status(ref)
	assert len([c for c in records.calls if c[0] == "reconcile"]) == 1
	assert a.cancel(ref) is True
