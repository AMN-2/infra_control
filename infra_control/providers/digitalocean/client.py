"""`DigitalOceanClient`: the one HTTP client for the DigitalOcean API (plan section 4.3 rule 4).

- Timeout on every request, bounded retries with full jitter on 5xx and 429 (honouring
  `Retry-After` / `RateLimit-Reset`), and rate-limit awareness: when fewer than
  `RATE_LIMIT_FLOOR` requests remain in the hour the client sleeps until the window resets
  instead of burning the remainder (DO allows 5,000 requests per hour per token).
- Pagination is followed transparently by `list_all()`.
- Nothing here knows about DocTypes or unified enums; `mapping.py` does the translation.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import requests

from infra_control.core.errors import NotFound, ProviderError, RateLimited

API_BASE = "https://api.digitalocean.com/v2"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_ATTEMPTS = 5
BACKOFF_BASE_SECONDS = 0.5
BACKOFF_CAP_SECONDS = 20.0
RATE_LIMIT_FLOOR = 50
PAGE_SIZE = 200
RETRY_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

JsonDict = dict[str, Any]


@dataclass
class RateLimitState:
	limit: int | None = None
	remaining: int | None = None
	reset_at: float | None = None
	"""Unix time at which the window resets, from `RateLimit-Reset`."""


class DigitalOceanClient:
	def __init__(
		self,
		token: str,
		*,
		base_url: str = API_BASE,
		timeout: float = DEFAULT_TIMEOUT_SECONDS,
		session: requests.Session | None = None,
		sleep: Callable[[float], None] = time.sleep,
		clock: Callable[[], float] = time.time,
		max_attempts: int = MAX_ATTEMPTS,
	) -> None:
		self._base = base_url.rstrip("/")
		self._timeout = timeout
		self._session = session or requests.Session()
		self._session.headers.update(
			{
				"Authorization": f"Bearer {token}",
				"Content-Type": "application/json",
				"Accept": "application/json",
				"User-Agent": "infra-control/0.1",
			}
		)
		self._sleep = sleep
		self._clock = clock
		self._max_attempts = max(1, max_attempts)
		self.rate_limit = RateLimitState()

	# --- transport ------------------------------------------------------------------------
	def request(self, method: str, path: str, **kwargs: Any) -> JsonDict:
		"""One API call with retries. Returns the decoded JSON body (`{}` for 204)."""
		url = path if path.startswith("http") else f"{self._base}/{path.lstrip('/')}"
		self._respect_rate_limit()
		last_error: str = ""
		for attempt in range(1, self._max_attempts + 1):
			try:
				response = self._session.request(method, url, timeout=self._timeout, **kwargs)
			except requests.RequestException as exc:
				last_error = f"{type(exc).__name__}: {exc}"
				if attempt == self._max_attempts:
					break
				self._sleep(self._backoff(attempt))
				continue
			self._record_rate_limit(response)
			if response.status_code in RETRY_STATUSES and attempt < self._max_attempts:
				self._sleep(self._retry_delay(response, attempt))
				continue
			return self._finish(response, method, path)
		raise ProviderError(
			f"DigitalOcean unreachable after {self._max_attempts} attempts",
			{"path": path, "error": last_error},
		)

	def _finish(self, response: requests.Response, method: str, path: str) -> JsonDict:
		if response.status_code == 429:
			retry_after = int(float(response.headers.get("Retry-After", "60")))
			raise RateLimited(retry_after, "DigitalOcean rate limit exceeded")
		if response.status_code == 404:
			raise NotFound("DigitalOcean resource", path)
		if response.status_code >= 400:
			body = _safe_json(response)
			raise ProviderError(
				f"DigitalOcean {method} {path} failed with {response.status_code}",
				{"status": response.status_code, "id": body.get("id"), "message": body.get("message")},
			)
		if response.status_code == 204 or not response.content:
			return {}
		return _safe_json(response)

	def _record_rate_limit(self, response: requests.Response) -> None:
		h = response.headers
		try:
			if "RateLimit-Limit" in h:
				self.rate_limit.limit = int(h["RateLimit-Limit"])
			if "RateLimit-Remaining" in h:
				self.rate_limit.remaining = int(h["RateLimit-Remaining"])
			if "RateLimit-Reset" in h:
				self.rate_limit.reset_at = float(h["RateLimit-Reset"])
		except ValueError:
			pass

	def _respect_rate_limit(self) -> None:
		rl = self.rate_limit
		if rl.remaining is None or rl.reset_at is None or rl.remaining >= RATE_LIMIT_FLOOR:
			return
		wait = rl.reset_at - self._clock()
		if wait > 0:
			self._sleep(min(wait, 3600.0))
		rl.remaining = None

	def _retry_delay(self, response: requests.Response, attempt: int) -> float:
		if response.status_code == 429:
			header = response.headers.get("Retry-After")
			if header:
				try:
					return max(0.0, float(header))
				except ValueError:
					pass
			if self.rate_limit.reset_at is not None:
				return max(0.0, min(self.rate_limit.reset_at - self._clock(), 3600.0))
		return self._backoff(attempt)

	@staticmethod
	def _backoff(attempt: int) -> float:
		"""Full-jitter exponential backoff."""
		return random.uniform(0, min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * 2**attempt))  # noqa: S311

	# --- helpers --------------------------------------------------------------------------
	def get(self, path: str, **params: Any) -> JsonDict:
		return self.request("GET", path, params={k: v for k, v in params.items() if v is not None})

	def post(self, path: str, body: JsonDict | None = None) -> JsonDict:
		return self.request("POST", path, json=body or {})

	def put(self, path: str, body: JsonDict | None = None) -> JsonDict:
		return self.request("PUT", path, json=body or {})

	def delete(self, path: str) -> None:
		self.request("DELETE", path)

	def list_all(self, path: str, key: str, **params: Any) -> Iterator[JsonDict]:
		"""Follows `links.pages.next` until the collection is exhausted."""
		page = self.get(path, per_page=PAGE_SIZE, **params)
		while True:
			items = page.get(key) or []
			if isinstance(items, list):
				for item in items:
					if isinstance(item, dict):
						yield item
			links = page.get("links") or {}
			pages = links.get("pages") if isinstance(links, dict) else None
			next_url = pages.get("next") if isinstance(pages, dict) else None
			if not next_url:
				return
			page = self.request("GET", str(next_url))

	# --- droplets -------------------------------------------------------------------------
	def list_droplets(self, tag: str | None = None) -> list[JsonDict]:
		return list(self.list_all("droplets", "droplets", tag_name=tag))

	def get_droplet(self, droplet_id: int | str) -> JsonDict:
		body = self.get(f"droplets/{droplet_id}")
		return _expect_dict(body, "droplet")

	def create_droplet(self, spec: JsonDict) -> JsonDict:
		"""`spec` is the API body (name, region, size, image, ssh_keys, user_data, tags, ...).

		Returns `{"droplet": {...}, "links": {"actions": [{"id": ...}]}}` as the API does: the
		create action id is what the adapter polls."""
		return self.post("droplets", spec)

	def delete_droplet(self, droplet_id: int | str) -> None:
		self.delete(f"droplets/{droplet_id}")

	def droplet_action(self, droplet_id: int | str, action_type: str, **extra: Any) -> JsonDict:
		body = self.post(f"droplets/{droplet_id}/actions", {"type": action_type, **extra})
		return _expect_dict(body, "action")

	def get_action(self, action_id: int | str) -> JsonDict:
		return _expect_dict(self.get(f"actions/{action_id}"), "action")

	def list_droplet_actions(self, droplet_id: int | str) -> list[JsonDict]:
		return list(self.list_all(f"droplets/{droplet_id}/actions", "actions"))

	# --- account resources ----------------------------------------------------------------
	def list_ssh_keys(self) -> list[JsonDict]:
		return list(self.list_all("account/keys", "ssh_keys"))

	def list_regions(self) -> list[JsonDict]:
		return list(self.list_all("regions", "regions"))

	def list_sizes(self) -> list[JsonDict]:
		return list(self.list_all("sizes", "sizes"))

	# --- firewalls ------------------------------------------------------------------------
	def list_firewalls(self) -> list[JsonDict]:
		return list(self.list_all("firewalls", "firewalls"))

	def create_firewall(self, spec: JsonDict) -> JsonDict:
		return _expect_dict(self.post("firewalls", spec), "firewall")

	def update_firewall(self, firewall_id: str, spec: JsonDict) -> JsonDict:
		return _expect_dict(self.put(f"firewalls/{firewall_id}", spec), "firewall")

	def add_droplets_to_firewall(self, firewall_id: str, droplet_ids: list[int]) -> None:
		self.post(f"firewalls/{firewall_id}/droplets", {"droplet_ids": droplet_ids})

	# --- DNS ------------------------------------------------------------------------------
	def list_domain_records(
		self, domain: str, record_type: str | None = None, name: str | None = None
	) -> list[JsonDict]:
		return list(self.list_all(f"domains/{domain}/records", "domain_records", type=record_type, name=name))

	def create_domain_record(self, domain: str, spec: JsonDict) -> JsonDict:
		return _expect_dict(self.post(f"domains/{domain}/records", spec), "domain_record")

	def delete_domain_record(self, domain: str, record_id: int | str) -> None:
		self.delete(f"domains/{domain}/records/{record_id}")

	def list_domains(self) -> list[JsonDict]:
		return list(self.list_all("domains", "domains"))

	# --- monitoring -----------------------------------------------------------------------
	def droplet_metric(self, metric: str, droplet_id: int | str, start: int, end: int) -> JsonDict:
		"""`metric` is one of the `/v2/monitoring/metrics/droplet/<metric>` paths (cpu, memory_total,
		memory_available, filesystem_size, filesystem_free, load_1). Returns the raw Prometheus-style body."""
		return self.get(
			f"monitoring/metrics/droplet/{metric}", host_id=str(droplet_id), start=str(start), end=str(end)
		)


def _safe_json(response: requests.Response) -> JsonDict:
	try:
		data: Any = response.json()
	except ValueError:
		return {}
	return data if isinstance(data, dict) else {}


def _expect_dict(body: JsonDict, key: str) -> JsonDict:
	value = body.get(key)
	if not isinstance(value, dict):
		raise ProviderError(f"DigitalOcean response lacks `{key}`", {"keys": sorted(body)})
	return value
