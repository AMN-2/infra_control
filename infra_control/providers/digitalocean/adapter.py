"""`DigitalOceanProvider` (plan sections 4 and 9.2).

Two kinds of work, two kinds of `OpRef`:

- `do_action`  : a DigitalOcean droplet action (reboot, snapshot) polled through `/actions/<id>`.
- `provision`  : `create_server`; the external id is the droplet id. Polling walks the stages
                 create droplet → attach the managed firewall → configure through Ansible
                 (`server_provision.yml`, A2.2) and reports each as a step.
- `ansible`    : everything that needs SSH, delegated to the `PlaybookRunner` (A2.2).

Only `client.py` talks HTTP and only `mapping.py` knows DigitalOcean's status strings. Frappe is
reached solely through `settings.py`, which tests replace.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from typing import Any, Protocol

from infra_control.core.enums import PROVIDER_CAPABILITIES, ServerRole, ServerStatus
from infra_control.core.enums import Provider as ProviderName
from infra_control.core.errors import ProviderError, ValidationError
from infra_control.providers.base import OpRef, OpState, OpStatus, OpStep, Provider, ProviderConfig
from infra_control.providers.digitalocean import mapping, settings, spaces
from infra_control.providers.digitalocean.client import DigitalOceanClient
from infra_control.providers.digitalocean.runner import PlaybookRunner
from infra_control.providers.registry import register

KIND_ACTION = "do_action"
KIND_PROVISION = "provision"
KIND_ANSIBLE = "ansible"
KIND_SYNC = "sync"
DISCOVERY_PLAYBOOK = "inventory_discover.yml"

SSH_KEY_NAME = "infra-control"
"""The DigitalOcean SSH key (account → Security) whose public key gets onto every droplet."""
FIREWALL_NAME = "infra-control-managed"
DEFAULT_IMAGE = "ubuntu-24-04-x64"
DEFAULT_SSH_USER = "frappe"
PROVISION_PLAYBOOK = "server_provision.yml"
DEFAULT_BENCH_PATH = "/home/frappe/frappe-bench"
"""Where server_provision.yml initialises the bench (roles/bench defaults: bench_name)."""

# Playbook files per Provider method (A2.2/A2.3 ship them under ansible/playbooks/).
SITE_PLAYBOOKS: dict[str, str] = {
	"create_site": "site_create.yml",
	"backup_site": "site_backup.yml",
	"restore_site": "site_restore.yml",
	"update_site": "site_migrate.yml",
	"set_maintenance": "site_maintenance.yml",
	"add_domain": "site_add_domain.yml",
	"suspend_site": "site_suspend.yml",
}
BENCH_PLAYBOOKS: dict[str, str] = {"update_bench": "bench_update.yml"}
SERVICE_PLAYBOOK = "service_control.yml"
ALLOWED_SERVICES: frozenset[str] = frozenset({"nginx", "supervisor", "mariadb", "redis"})
ALLOWED_SERVICE_ACTIONS: frozenset[str] = frozenset({"restart", "reload"})


class Records(Protocol):
	"""What a successful operation leaves in the DocTypes (settings.py implements it with Frappe)."""

	def record_server(self, account: str, droplet: dict[str, Any]) -> str: ...
	def record_bench(self, account: str, server: str, path: str) -> str: ...
	def controller_public_key(self) -> str: ...
	def record_site(self, domain: str, bench: str) -> str: ...
	def record_backup(self, site: str, kind: str, location: str, size_mb: float, job_ref: str) -> str: ...
	def record_domain(self, site: str, domain: str) -> None: ...
	def load_backup_set(self, backup: str) -> dict[str, str]: ...
	def spaces_client(self) -> spaces.SpacesClient | None: ...
	def reconcile(self, account: str, provider: str, inventory: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class _Pending:
	"""Work to record once an Ansible operation succeeds (kept per adapter instance)."""

	kind: str
	site: str
	extra: dict[str, Any]


# Files a Frappe backup produces, by Backup.kind, and the name each gets in Spaces.
BACKUP_FILES: dict[str, tuple[str, str]] = {
	"database": ("db", "database.sql.gz"),
	"public": ("files", "files.tar"),
	"private": ("files", "private-files.tar"),
}


@dataclass
class _Sync:
	"""An inventory.sync in flight: the API half is done, the host half (discovery) runs."""

	servers: list[dict[str, Any]]
	"""Normalized droplets (mapping.normalize_droplet), all of them."""
	hosts: dict[str, str]
	"""inventory hostname (= hostname) -> droplet id, for the servers discovery was sent to."""
	started_at: datetime
	result: dict[str, Any] | None = None


@dataclass
class _Provision:
	"""Per-droplet provisioning progress kept for the lifetime of the adapter instance."""

	droplet_id: str
	hostname: str
	firewall_done: bool = False
	configure: OpRef | None = None
	started_at: datetime | None = None
	droplet_active_at: datetime | None = None
	firewall_at: datetime | None = None


def render_cloud_init(hostname: str, ssh_user: str, ssh_public_key: str) -> str:
	template = resources.files("infra_control.providers.digitalocean").joinpath("cloud_init.yaml").read_text()
	return template.format(hostname=hostname, ssh_user=ssh_user, ssh_public_key=ssh_public_key.strip())


def firewall_rules(controller_ip: str) -> dict[str, Any]:
	"""SSH only from the controller (plan 13.2); HTTP/HTTPS from everywhere; all outbound."""
	return {
		"inbound_rules": [
			{"protocol": "tcp", "ports": "22", "sources": {"addresses": [f"{controller_ip}/32"]}},
			{"protocol": "tcp", "ports": "80", "sources": {"addresses": ["0.0.0.0/0", "::/0"]}},
			{"protocol": "tcp", "ports": "443", "sources": {"addresses": ["0.0.0.0/0", "::/0"]}},
		],
		"outbound_rules": [
			{"protocol": "tcp", "ports": "0", "destinations": {"addresses": ["0.0.0.0/0", "::/0"]}},
			{"protocol": "udp", "ports": "0", "destinations": {"addresses": ["0.0.0.0/0", "::/0"]}},
			{"protocol": "icmp", "destinations": {"addresses": ["0.0.0.0/0", "::/0"]}},
		],
	}


@register
class DigitalOceanProvider(Provider):
	name = "digitalocean"
	capabilities = PROVIDER_CAPABILITIES[ProviderName.DIGITALOCEAN]

	def __init__(
		self,
		config: ProviderConfig,
		*,
		client: DigitalOceanClient | None = None,
		runner: PlaybookRunner | None = None,
		settings_loader: Callable[[], settings.ControllerSettings] = settings.load_controller_settings,
		server_loader: Callable[[str], dict[str, Any]] = settings.load_server,
		site_loader: Callable[[str], dict[str, Any]] = settings.load_site,
		bench_loader: Callable[[str], dict[str, Any]] = settings.load_bench,
		records: Records | None = None,
		clock: Callable[[], float] = time.time,
	) -> None:
		super().__init__(config)
		self.client = client or DigitalOceanClient(config.api_token)
		self.runner: PlaybookRunner = runner or settings.default_runner()
		self._settings_loader = settings_loader
		self._server_loader = server_loader
		self._site_loader = site_loader
		self._bench_loader = bench_loader
		self._clock = clock
		self._records: Records = records or _SettingsRecords()
		self._provisions: dict[str, _Provision] = {}
		self._pending: dict[str, _Pending] = {}
		self._syncs: dict[str, _Sync] = {}

	# --- helpers ---------------------------------------------------------------------------
	def _settings(self) -> settings.ControllerSettings:
		return self._settings_loader()

	def _server(self, name: str) -> dict[str, Any]:
		return self._server_loader(name)

	def _ansible_for_site(self, method: str, site: str, extra: dict[str, Any]) -> OpRef:
		s = self._site_loader(site)
		if not s.get("server"):
			raise ProviderError("Site has no server on DigitalOcean", {"site": site})
		server = self._server(str(s["server"]))
		extra_vars = {"site": s["domain"], "bench_path": s.get("bench_path"), **extra}
		return self.runner.start(server, SITE_PLAYBOOKS[method], extra_vars)

	def _ssh_key(self) -> dict[str, Any]:
		"""The account's SSH key holding the controller's public key.

		Matched by key material first (the name a human typed does not matter), then by the name
		`infra-control` as a fallback when the controller's public key cannot be read."""
		keys = self.client.list_ssh_keys()
		mine = _key_material(self._records.controller_public_key())
		if mine:
			for key in keys:
				if _key_material(str(key.get("public_key", ""))) == mine:
					return key
		for key in keys:
			if key.get("name") == SSH_KEY_NAME:
				return key
		raise ProviderError(
			"The controller's SSH public key is not on this DigitalOcean account",
			{"hint": "Add it under Settings → Security (any name; `infra-control` is conventional)"},
		)

	# --- site level (Ansible) --------------------------------------------------------------
	def _spaces(self) -> spaces.SpacesClient:
		client = self._records.spaces_client()
		if client is None:
			raise ProviderError(
				"Spaces is not configured (Infra Settings): backups must leave the server",
				{"fields": ["spaces_bucket", "spaces_region", "spaces_key", "spaces_secret"]},
			)
		return client

	def _backup_targets(self, site: str, with_files: bool) -> tuple[dict[str, str], dict[str, str]]:
		"""Presigned PUT URLs for the server and the spaces:// locations to record, by file."""
		client = self._spaces()
		stamp = datetime.fromtimestamp(self._clock(), UTC).strftime("%Y%m%d_%H%M%S")
		names = ["database", "public", "private"] if with_files else ["database"]
		urls: dict[str, str] = {}
		locations: dict[str, str] = {}
		for name in names:
			key = f"{site}/{stamp}-{BACKUP_FILES[name][1]}"
			urls[name] = spaces.presign_put(client, key)
			locations[name] = spaces.location(client.config.bucket, key)
		return urls, locations

	def _start_site(
		self, method: str, site: str, extra: dict[str, Any], pending: _Pending | None = None
	) -> OpRef:
		ref = self._ansible_for_site(method, site, extra)
		if pending is not None:
			self._pending[ref.external_id] = pending
		return ref

	def create_site(self, site: str, bench: str, apps: list[str] | None = None, **kw: Any) -> OpRef:
		b = self._bench_loader(bench)
		if not b.get("server"):
			raise ProviderError("Bench has no server on DigitalOcean", {"bench": bench})
		server = self._server(str(b["server"]))
		extra_vars = {"site": site, "bench_path": b.get("path"), "apps": list(apps or []), **kw}
		ref = self.runner.start(server, SITE_PLAYBOOKS["create_site"], extra_vars)
		self._pending[ref.external_id] = _Pending("site", site, {"bench": bench})
		return ref

	def update_bench(
		self,
		bench: str,
		apps: list[str] | None = None,
		branch: str = "",
		migrate: bool = True,
		build: bool = True,
	) -> OpRef:
		"""`bench.update`: the playbook pulls fast-forward only and, with `migrate`, backs up every
		site before migrating (plan 13.7: the job fails if a backup fails)."""
		b = self._bench_loader(bench)
		if not b.get("server"):
			raise ProviderError("Bench has no server on DigitalOcean", {"bench": bench})
		server = self._server(str(b["server"]))
		extra_vars = {
			"bench_path": b.get("path"),
			"apps": list(apps or []),
			"branch": branch or "",
			"migrate": bool(migrate),
			"build": bool(build),
		}
		return self.runner.start(server, BENCH_PLAYBOOKS["update_bench"], extra_vars)

	def backup_site(self, site: str, with_files: bool = True) -> OpRef:
		urls, locations = self._backup_targets(site, with_files)
		return self._start_site(
			"backup_site",
			site,
			{"with_files": bool(with_files), "backup_urls": urls},
			_Pending("backup", site, {"locations": locations}),
		)

	def restore_site(self, site: str, backup_ref: str) -> OpRef:
		client = self._spaces()
		files = self._records.load_backup_set(backup_ref)
		if "db" not in files:
			raise ProviderError("The backup has no database file", {"backup": backup_ref})
		urls: dict[str, str] = {}
		for location in files.values():
			_bucket, key = spaces.parse_location(location)
			name = next((n for n, (_k, suffix) in BACKUP_FILES.items() if key.endswith(f"-{suffix}")), None)
			if name:
				urls[name] = spaces.presign_get(client, key)
		return self._start_site("restore_site", site, {"restore_urls": urls})

	def update_site(self, site: str, **kw: Any) -> OpRef:
		"""`site.migrate`: the playbook backs up first and fails before migrating if that fails."""
		urls, locations = self._backup_targets(site, with_files=False)
		return self._start_site(
			"update_site",
			site,
			{**kw, "backup_urls": urls},
			_Pending("backup", site, {"locations": locations}),
		)

	def set_maintenance(self, site: str, on: bool) -> OpRef:
		return self._start_site("set_maintenance", site, {"maintenance_on": bool(on)})

	def add_domain(self, site: str, domain: str) -> OpRef:
		s = self._site_loader(site)
		server = self._server(str(s["server"])) if s.get("server") else {}
		dns = self._ensure_dns(domain, str(server.get("public_ip") or ""))
		return self._start_site(
			"add_domain",
			site,
			{"domain": domain, "dns_managed": dns},
			_Pending("domain", site, {"domain": domain}),
		)

	def suspend_site(self, site: str, suspended: bool) -> OpRef:
		return self._start_site("suspend_site", site, {"suspended": bool(suspended)})

	def _ensure_dns(self, domain: str, ip: str) -> bool:
		"""A record for `domain` → the server, when its zone is a DigitalOcean domain on this
		account. Returns False (and changes nothing) when the zone lives elsewhere."""
		if not ip:
			return False
		zones = sorted((str(z.get("name", "")) for z in self.client.list_domains()), key=len, reverse=True)
		zone = next((z for z in zones if z and (domain == z or domain.endswith(f".{z}"))), None)
		if zone is None:
			return False
		host = "@" if domain == zone else domain[: -(len(zone) + 1)]
		records = self.client.list_domain_records(zone, record_type="A", name=domain)
		if any(r.get("data") == ip for r in records):
			return True
		for r in records:  # a stale A record for this name points somewhere else
			self.client.delete_domain_record(zone, r["id"])
		self.client.create_domain_record(zone, {"type": "A", "name": host, "data": ip, "ttl": 300})
		return True

	def _record(self, op: OpRef, status: OpStatus) -> None:
		"""Leave the operation's result in the DocTypes once, on success."""
		pending = self._pending.get(op.external_id)
		if pending is None or status.state is not OpState.SUCCESS:
			if status.state.terminal:
				self._pending.pop(op.external_id, None)
			return
		self._pending.pop(op.external_id)
		if pending.kind == "site":
			self._records.record_site(pending.site, str(pending.extra["bench"]))
		elif pending.kind == "domain":
			self._records.record_domain(pending.site, str(pending.extra["domain"]))
		elif pending.kind == "backup":
			client = self._spaces()
			for name, location in dict(pending.extra["locations"]).items():
				_bucket, key = spaces.parse_location(location)
				size = spaces.object_size(client, key)
				if size is None:
					continue  # not uploaded (e.g. a site without private files)
				self._records.record_backup(
					pending.site,
					BACKUP_FILES[name][0],
					location,
					round(size / (1024 * 1024), 2),
					op.external_id,
				)

	# --- servers (API + Ansible) -----------------------------------------------------------
	def create_server(self, **kw: Any) -> OpRef:
		hostname = str(kw.get("hostname") or "").strip()
		region = str(kw.get("region") or "").strip()
		size = str(kw.get("size") or "").strip()
		if not (hostname and region and size):
			raise ValidationError("hostname, region and size are required", {"field": "params"})
		role = ServerRole(str(kw.get("role") or ServerRole.ALL))
		extra_tags = [str(t) for t in (kw.get("tags") or [])]
		key = self._ssh_key()
		spec: dict[str, Any] = {
			"name": hostname,
			"region": region,
			"size": size,
			"image": str(kw.get("image") or DEFAULT_IMAGE),
			"ssh_keys": [key["id"]],
			"backups": False,
			"ipv6": True,
			"monitoring": True,
			"tags": mapping.tags_for(role, extra_tags, staging=self.config.is_staging),
			"user_data": render_cloud_init(hostname, DEFAULT_SSH_USER, str(key.get("public_key", ""))),
		}
		created = self.client.create_droplet(spec)
		droplet = created.get("droplet") or {}
		droplet_id = str(droplet.get("id") or "")
		if not droplet_id:
			raise ProviderError("DigitalOcean did not return a droplet id", {"keys": sorted(created)})
		self._provisions[droplet_id] = _Provision(droplet_id, hostname, started_at=datetime.now(UTC))
		return OpRef(self.name, KIND_PROVISION, droplet_id)

	def reboot_server(self, server: str) -> OpRef:
		s = self._server(server)
		action = self.client.droplet_action(s["provider_ref"], "reboot")
		return OpRef(self.name, KIND_ACTION, str(action["id"]))

	def snapshot_server(self, server: str) -> OpRef:
		s = self._server(server)
		stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
		action = self.client.droplet_action(s["provider_ref"], "snapshot", name=f"{s['hostname']}-{stamp}")
		return OpRef(self.name, KIND_ACTION, str(action["id"]))

	def control_service(self, server: str, service: str, action: str) -> OpRef:
		if service not in ALLOWED_SERVICES or action not in ALLOWED_SERVICE_ACTIONS:
			raise ValidationError("Unsupported service or action", {"service": service, "action": action})
		return self.runner.start(
			self._server(server), SERVICE_PLAYBOOK, {"service": service, "action": action}
		)

	def run_playbook(
		self,
		server: str,
		playbook_file: str,
		extra_vars: dict[str, Any] | None = None,
		resume_task: str | None = None,
	) -> OpRef:
		return self.runner.start(
			self._server(server), playbook_file, dict(extra_vars or {}), start_at_task=resume_task or None
		)

	def get_metrics(self, server: str) -> dict[str, Any]:
		"""cpu/ram/disk/load1 from DigitalOcean Monitoring over the last 10 minutes.
		`queue_backlog` needs the host; the collector (A3.1) adds it from the Ansible facts."""
		s = self._server(server)
		droplet_id = str(s["provider_ref"])
		end = int(self._clock())
		start = end - 600
		cpu = mapping.cpu_percent(self.client.droplet_metric("cpu", droplet_id, start, end))
		mem_total = mapping.latest_value(self.client.droplet_metric("memory_total", droplet_id, start, end))
		mem_avail = mapping.latest_value(
			self.client.droplet_metric("memory_available", droplet_id, start, end)
		)
		fs_size = mapping.latest_value(self.client.droplet_metric("filesystem_size", droplet_id, start, end))
		fs_free = mapping.latest_value(self.client.droplet_metric("filesystem_free", droplet_id, start, end))
		load1 = mapping.latest_value(self.client.droplet_metric("load_1", droplet_id, start, end))
		return {
			"cpu": cpu,
			"ram": mapping.percent_used(mem_total, mem_avail),
			"disk": mapping.percent_used(fs_size, fs_free),
			"load1": None if load1 is None else round(load1, 2),
			"ts": datetime.fromtimestamp(end, UTC),
		}

	# --- lifecycle -------------------------------------------------------------------------
	def sync_inventory(self) -> OpRef | dict[str, Any]:
		"""Two halves. API: droplets tagged `infra-control` become the server list. Hosts: the
		discovery playbook lists benches and sites on every reachable server (one Ansible run, in
		parallel), then `Records.reconcile` creates and updates documents and reports drift
		findings. Without reachable servers the API half is reconciled at once."""
		servers = [mapping.normalize_droplet(d) for d in self.client.list_droplets(tag=mapping.MANAGED_TAG)]
		targets: list[dict[str, Any]] = []
		hosts: dict[str, str] = {}
		for srv in servers:
			if srv["status"] is not ServerStatus.ACTIVE or not srv.get("public_ip"):
				continue
			host = str(srv["hostname"])
			targets.append(
				{
					"name": host,
					"hostname": host,
					"public_ip": srv["public_ip"],
					"ssh_user": DEFAULT_SSH_USER,
					"ssh_port": 22,
					"role": str(srv["role"]),
				}
			)
			hosts[host] = str(srv["provider_ref"])
		if not targets:
			return self._records.reconcile(
				self.config.account,
				self.name,
				{"servers": servers, "benches": [], "sites": [], "unreachable": [], "discovered": []},
			)
		ref = self.runner.start_many(targets, DISCOVERY_PLAYBOOK, {})
		self._syncs[ref.external_id] = _Sync(servers, hosts, datetime.now(UTC))
		return OpRef(self.name, KIND_SYNC, ref.external_id)

	def _sync_status(self, op: OpRef) -> OpStatus:
		from infra_control.inventory.plan import normalize_discovery

		run = OpRef(self.name, KIND_ANSIBLE, op.external_id)
		inner = self.runner.status(run)
		sync = self._syncs.get(op.external_id)
		if sync is None:
			# A fresh adapter instance (worker restart): the server list is fetched again.
			servers = [
				mapping.normalize_droplet(d) for d in self.client.list_droplets(tag=mapping.MANAGED_TAG)
			]
			sync = _Sync(
				servers, {str(s_["hostname"]): str(s_["provider_ref"]) for s_ in servers}, datetime.now(UTC)
			)
			self._syncs[op.external_id] = sync
		api_step = OpStep(
			"List servers at DigitalOcean",
			OpState.SUCCESS,
			output=f"{len(sync.servers)} droplets tagged {mapping.MANAGED_TAG}\n",
			started_at=sync.started_at,
			ended_at=sync.started_at,
		)
		steps: list[OpStep] = [api_step, *inner.steps]
		if not inner.state.terminal or inner.state is not OpState.SUCCESS:
			return OpStatus(inner.state, tuple(steps), error=inner.error)
		if sync.result is None:
			unreachable = self.runner.unreachable(run)
			benches: list[dict[str, Any]] = []
			sites: list[dict[str, Any]] = []
			discovered: list[str] = []
			for host, payload in self.runner.read_results(run).items():
				ref = sync.hosts.get(host)
				if ref is None or not isinstance(payload, dict):
					continue
				discovered.append(ref)
				b, s_ = normalize_discovery(ref, host, payload)
				benches.extend(b)
				sites.extend(s_)
			sync.result = self._records.reconcile(
				self.config.account,
				self.name,
				{
					"servers": sync.servers,
					"benches": benches,
					"sites": sites,
					"unreachable": unreachable,
					"discovered": discovered,
				},
			)
		summary = sync.result
		lines = [f"{k}: {v}" for k, v in summary.items() if isinstance(v, int)]
		for f in summary.get("findings") or []:
			lines.append(f"finding {f.get('kind')}: {f.get('doctype')} {f.get('name')}: {f.get('detail')}")
		steps.append(
			OpStep(
				"Reconcile documents",
				OpState.SUCCESS,
				output="\n".join(lines) + "\n",
				started_at=datetime.now(UTC),
				ended_at=datetime.now(UTC),
			)
		)
		return OpStatus(OpState.SUCCESS, tuple(steps))

	def cancel(self, op: OpRef) -> bool:
		if op.kind in (KIND_ANSIBLE, KIND_SYNC):
			return self.runner.cancel(OpRef(self.name, KIND_ANSIBLE, op.external_id))
		if op.kind == KIND_PROVISION:
			p = self._provisions.get(op.external_id)
			return bool(p and p.configure and self.runner.cancel(p.configure))
		return False  # a droplet action cannot be cancelled once accepted

	def get_status(self, op: OpRef) -> OpStatus:
		if op.kind == KIND_ACTION:
			return self._action_status(op)
		if op.kind == KIND_PROVISION:
			return self._provision_status(op)
		if op.kind == KIND_ANSIBLE:
			status = self.runner.status(op)
			self._record(op, status)
			return status
		if op.kind == KIND_SYNC:
			return self._sync_status(op)
		raise ProviderError("Unknown DigitalOcean operation kind", {"kind": op.kind})

	def _action_status(self, op: OpRef) -> OpStatus:
		action = self.client.get_action(op.external_id)
		state = mapping.action_state(str(action.get("status", "")))
		title = str(action.get("type", "action")).replace("_", " ").capitalize()
		step = OpStep(
			title,
			state,
			output=f"action {op.external_id} {action.get('status', '')}\n",
			started_at=mapping.parse_time(action.get("started_at")),
			ended_at=mapping.parse_time(action.get("completed_at")),
		)
		error = f"DigitalOcean action {op.external_id} errored" if state is OpState.FAILED else None
		return OpStatus(state=state, steps=(step,), error=error)

	def _provision_status(self, op: OpRef) -> OpStatus:
		p = self._provisions.get(op.external_id)
		if p is None:  # fresh adapter instance (worker restart): rebuild what we can
			droplet = self.client.get_droplet(op.external_id)
			p = _Provision(
				op.external_id,
				str(droplet.get("name", "")),
				started_at=mapping.parse_time(droplet.get("created_at")),
			)
			self._provisions[op.external_id] = p
		droplet = self.client.get_droplet(p.droplet_id)
		status = mapping.server_status(str(droplet.get("status", "")))
		now = datetime.now(UTC)
		steps: list[OpStep] = []

		# 1. droplet
		if status is ServerStatus.PROVISIONING:
			steps.append(
				OpStep(
					"Create droplet",
					OpState.RUNNING,
					output="waiting for the droplet to become active\n",
					started_at=p.started_at,
				)
			)
			steps.append(OpStep("Attach managed firewall", OpState.QUEUED))
			steps.append(OpStep("Configure server", OpState.QUEUED))
			return OpStatus(OpState.RUNNING, tuple(steps))
		if status is not ServerStatus.ACTIVE:
			steps.append(
				OpStep(
					"Create droplet",
					OpState.FAILED,
					output=f"droplet is {status}\n",
					started_at=p.started_at,
					ended_at=now,
				)
			)
			return OpStatus(OpState.FAILED, tuple(steps), error=f"Droplet {p.droplet_id} is {status}")
		p.droplet_active_at = p.droplet_active_at or now
		ip = mapping.public_ip(droplet) or ""
		steps.append(
			OpStep(
				"Create droplet",
				OpState.SUCCESS,
				output=f"droplet {p.droplet_id} active, ip {ip}\n",
				started_at=p.started_at,
				ended_at=p.droplet_active_at,
			)
		)

		# 2. firewall
		if not p.firewall_done:
			fw = self._ensure_firewall(int(p.droplet_id))
			p.firewall_done = True
			p.firewall_at = now
			steps.append(
				OpStep(
					"Attach managed firewall",
					OpState.SUCCESS,
					output=f"firewall {fw}\n",
					started_at=p.droplet_active_at,
					ended_at=now,
				)
			)
		else:
			steps.append(
				OpStep(
					"Attach managed firewall",
					OpState.SUCCESS,
					started_at=p.droplet_active_at,
					ended_at=p.firewall_at,
				)
			)

		# 3. configure through Ansible
		if p.configure is None:
			server = {
				"name": p.hostname,
				"hostname": p.hostname,
				"provider_ref": p.droplet_id,
				"public_ip": ip,
				"private_ip": mapping.public_ip(droplet, "private"),
				"ssh_user": DEFAULT_SSH_USER,
				"ssh_port": 22,
				"role": str(mapping.role_from_tags([str(t) for t in droplet.get("tags") or []])),
			}
			# A provisioned server ends with an initialised, production-ready bench (plan 9.2, exit
			# gate: "a new DO server reaches a working site in one action").
			p.configure = self.runner.start(
				server, PROVISION_PLAYBOOK, {"hostname": p.hostname, "bench_init": True}
			)
		inner = self.runner.status(p.configure)
		if inner.steps:
			steps.extend(inner.steps)
		else:
			steps.append(OpStep("Configure server", inner.state, started_at=p.firewall_at))
		created = None
		if inner.state is OpState.SUCCESS:
			server_name = self._records.record_server(self.config.account, mapping.normalize_droplet(droplet))
			self._records.record_bench(self.config.account, server_name, DEFAULT_BENCH_PATH)
			created = ("Server", p.droplet_id)
		return OpStatus(inner.state, tuple(steps), error=inner.error, created=created)

	def _ensure_firewall(self, droplet_id: int) -> str:
		"""Find or create the managed firewall, keep its rules current, attach the droplet."""
		controller_ip = self._settings().controller_ip
		if not controller_ip:
			raise ProviderError(
				"Infra Settings.controller_ip is empty; refusing to open SSH to the world", {}
			)
		rules = firewall_rules(controller_ip)
		existing = next((f for f in self.client.list_firewalls() if f.get("name") == FIREWALL_NAME), None)
		if existing is None:
			fw = self.client.create_firewall(
				{"name": FIREWALL_NAME, **rules, "droplet_ids": [droplet_id], "tags": []}
			)
			return str(fw.get("id", ""))
		fw_id = str(existing.get("id", ""))
		if existing.get("inbound_rules") != rules["inbound_rules"]:
			self.client.update_firewall(fw_id, {"name": FIREWALL_NAME, **rules})
		attached = {int(d) for d in (existing.get("droplet_ids") or []) if str(d).isdigit()}
		if droplet_id not in attached:
			self.client.add_droplets_to_firewall(fw_id, [droplet_id])
		return fw_id


class _SettingsRecords:
	"""Default `Records`: the Frappe-backed functions in settings.py."""

	def record_server(self, account: str, droplet: dict[str, Any]) -> str:
		return settings.record_server(account, droplet)

	def record_bench(self, account: str, server: str, path: str) -> str:
		return settings.record_bench(account, server, path)

	def controller_public_key(self) -> str:
		return settings.controller_public_key()

	def record_site(self, domain: str, bench: str) -> str:
		return settings.record_site(domain, bench)

	def record_backup(self, site: str, kind: str, location: str, size_mb: float, job_ref: str) -> str:
		return settings.record_backup(site, kind, location, size_mb, job_ref)

	def record_domain(self, site: str, domain: str) -> None:
		settings.record_domain(site, domain)

	def load_backup_set(self, backup: str) -> dict[str, str]:
		return settings.load_backup_set(backup)

	def spaces_client(self) -> spaces.SpacesClient | None:
		client: spaces.SpacesClient | None = settings.spaces_client()
		return client

	def reconcile(self, account: str, provider: str, inventory: dict[str, Any]) -> dict[str, Any]:
		from infra_control.inventory.apply import reconcile

		return reconcile(account, provider, inventory)


def _key_material(public_key: str) -> str:
	"""`ssh-ed25519 AAAA... comment` → `ssh-ed25519 AAAA...` (the comment is not part of the key)."""
	parts = public_key.strip().split()
	return " ".join(parts[:2]) if len(parts) >= 2 else ""
