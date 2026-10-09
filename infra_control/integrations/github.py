"""GitHub REST client for the Git Connection feature (ADR 0005).

Read-only: who the token belongs to, the repositories it can see, and a repository's branches
and tags. External HTTP rules (AGENTS.md): timeout, bounded retries with jitter on 5xx/429,
rate-limit aware. The token never appears in errors or logs.
"""

from __future__ import annotations

import random
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import requests

from infra_control.core.errors import NotFound, ProviderError, RateLimited, ValidationError

API_BASE = "https://api.github.com"
DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_ATTEMPTS = 3
RETRY_STATUSES = frozenset({500, 502, 503, 504})
PER_PAGE = 50
JsonDict = dict[str, Any]


@dataclass(frozen=True)
class GitIdentity:
	login: str
	account_type: str
	scopes: str


class GitHubClient:
	def __init__(
		self,
		token: str | None,
		*,
		base_url: str = API_BASE,
		timeout: float = DEFAULT_TIMEOUT_SECONDS,
		session: requests.Session | None = None,
		sleep: Callable[[float], None] = time.sleep,
		max_attempts: int = MAX_ATTEMPTS,
	) -> None:
		# `None` is the anonymous client (public repositories, 60 requests/hour); an empty
		# string is a mistake.
		if token is not None and not token.strip():
			raise ValidationError("A GitHub access token is required", {"field": "token"})
		self._base = base_url.rstrip("/")
		self._timeout = timeout
		self._session = session or requests.Session()
		self._session.headers.update(
			{
				"Accept": "application/vnd.github+json",
				"X-GitHub-Api-Version": "2022-11-28",
				"User-Agent": "infra-control/0.1",
			}
		)
		if token is not None:
			self._session.headers["Authorization"] = f"Bearer {token.strip()}"
		self._sleep = sleep
		self._max_attempts = max(1, max_attempts)

	# --- transport ------------------------------------------------------------------------
	def request(self, method: str, path: str, **kwargs: Any) -> tuple[Any, dict[str, str]]:
		url = path if path.startswith("http") else f"{self._base}/{path.lstrip('/')}"
		last_error = ""
		for attempt in range(1, self._max_attempts + 1):
			try:
				response = self._session.request(method, url, timeout=self._timeout, **kwargs)
			except requests.RequestException as exc:
				last_error = type(exc).__name__
				if attempt == self._max_attempts:
					break
				self._sleep(self._backoff(attempt))
				continue
			if response.status_code in RETRY_STATUSES and attempt < self._max_attempts:
				self._sleep(self._backoff(attempt))
				continue
			return self._finish(response, method, path), dict(response.headers)
		raise ProviderError(
			f"GitHub unreachable after {self._max_attempts} attempts", {"path": path, "error": last_error}
		)

	@staticmethod
	def _finish(response: requests.Response, method: str, path: str) -> Any:
		if response.status_code in (403, 429) and response.headers.get("X-RateLimit-Remaining") == "0":
			reset = response.headers.get("X-RateLimit-Reset")
			retry_after = max(1, int(float(reset) - time.time())) if reset else 60
			raise RateLimited(retry_after, "GitHub rate limit exceeded")
		if response.status_code == 401:
			raise ValidationError("GitHub rejected the access token", {"field": "token"})
		if response.status_code == 404:
			raise NotFound("GitHub resource", path)
		if response.status_code >= 400:
			body: Any = {}
			try:
				body = response.json()
			except ValueError:
				body = {}
			message = body.get("message") if isinstance(body, dict) else None
			raise ProviderError(
				f"GitHub {method} {path} failed with {response.status_code}",
				{"status": response.status_code, "message": message},
			)
		if response.status_code == 204 or not response.content:
			return {}
		try:
			return response.json()
		except ValueError:
			raise ProviderError("GitHub returned a non-JSON body", {"path": path}) from None

	@staticmethod
	def _backoff(attempt: int) -> float:
		return random.uniform(0, min(8.0, 0.5 * 2**attempt))  # noqa: S311

	# --- queries --------------------------------------------------------------------------
	def whoami(self) -> GitIdentity:
		body, headers = self.request("GET", "user")
		if not isinstance(body, dict) or not body.get("login"):
			raise ProviderError("GitHub did not return the token's user", {})
		return GitIdentity(
			login=str(body["login"]),
			account_type=str(body.get("type") or "User"),
			scopes=str(headers.get("X-OAuth-Scopes") or headers.get("x-oauth-scopes") or ""),
		)

	def list_repos(self, query: str = "", page: int = 1) -> tuple[list[JsonDict], bool]:
		"""Repositories the token can see (own, collaborator, organisation), newest first.
		Returns (repos, has_more). `query` filters by name client-side within the page set."""
		body, headers = self.request(
			"GET",
			"user/repos",
			params={
				"affiliation": "owner,collaborator,organization_member",
				"sort": "updated",
				"per_page": PER_PAGE,
				"page": page,
			},
		)
		rows = body if isinstance(body, list) else []
		has_more = 'rel="next"' in str(headers.get("Link") or headers.get("link") or "")
		q = query.strip().lower()
		out = [self._repo(r) for r in rows if isinstance(r, dict)]
		if q:
			out = [r for r in out if q in str(r["full_name"]).lower()]
		return out, has_more

	def get_repo(self, full_name: str) -> JsonDict:
		owner, name = _split(full_name)
		body, _ = self.request("GET", f"repos/{owner}/{name}")
		if not isinstance(body, dict):
			raise ProviderError("GitHub returned an unexpected repository body", {})
		return self._repo(body)

	def list_refs(self, full_name: str) -> list[JsonDict]:
		"""Branches then tags, each `{name, kind, sha}` (first 100 of each)."""
		owner, name = _split(full_name)
		refs: list[JsonDict] = []
		branches, _ = self.request("GET", f"repos/{owner}/{name}/branches", params={"per_page": 100})
		for b in branches if isinstance(branches, list) else []:
			if isinstance(b, dict) and b.get("name"):
				refs.append(
					{
						"name": str(b["name"]),
						"kind": "branch",
						"sha": str((b.get("commit") or {}).get("sha") or "")[:12],
					}
				)
		tags, _ = self.request("GET", f"repos/{owner}/{name}/tags", params={"per_page": 100})
		for t in tags if isinstance(tags, list) else []:
			if isinstance(t, dict) and t.get("name"):
				refs.append(
					{
						"name": str(t["name"]),
						"kind": "tag",
						"sha": str((t.get("commit") or {}).get("sha") or "")[:12],
					}
				)
		return refs

	def branch_head(self, full_name: str, branch: str) -> str:
		"""Short SHA at the tip of `branch`."""
		owner, name = _split(full_name)
		body, _ = self.request("GET", f"repos/{owner}/{name}/commits/{branch}")
		sha = str(body.get("sha") or "") if isinstance(body, dict) else ""
		if not sha:
			raise ProviderError("GitHub returned no commit for the branch", {"branch": branch})
		return sha[:12]

	def commits_behind(self, full_name: str, local_commit: str, branch: str) -> int:
		"""How many commits `branch` has that `local_commit` lacks (0 = up to date)."""
		owner, name = _split(full_name)
		body, _ = self.request("GET", f"repos/{owner}/{name}/compare/{local_commit}...{branch}")
		if not isinstance(body, dict):
			raise ProviderError("GitHub returned an unexpected compare body", {})
		return int(body.get("ahead_by") or 0)

	def latest_tag(self, full_name: str, major: int | None = None) -> str | None:
		"""Highest version-like tag (optionally of one major, e.g. 15 for `version-15`)."""
		owner, name = _split(full_name)
		body, _ = self.request("GET", f"repos/{owner}/{name}/tags", params={"per_page": 100})
		best: tuple[tuple[int, ...], str] | None = None
		for t in body if isinstance(body, list) else []:
			tag = str(t.get("name") or "") if isinstance(t, dict) else ""
			parsed = _version_tuple(tag)
			if parsed is None or (major is not None and parsed[0] != major):
				continue
			if best is None or parsed > best[0]:
				best = (parsed, tag)
		return best[1] if best else None

	@staticmethod
	def _repo(r: JsonDict) -> JsonDict:
		return {
			"full_name": str(r.get("full_name") or ""),
			"name": str(r.get("name") or ""),
			"owner": str((r.get("owner") or {}).get("login") or ""),
			"private": bool(r.get("private")),
			"default_branch": str(r.get("default_branch") or ""),
			"clone_url": str(r.get("clone_url") or ""),
			"description": (str(r["description"]) if r.get("description") else None),
			"pushed_at": (str(r["pushed_at"]) if r.get("pushed_at") else None),
		}


def _version_tuple(tag: str) -> tuple[int, ...] | None:
	m = re.fullmatch(r"v?(\d+(?:\.\d+)*)", tag.strip())
	return tuple(int(x) for x in m.group(1).split(".")) if m else None


def github_repo_of(remote: str | None) -> str | None:
	"""`owner/name` for a GitHub remote (https, ssh or git@), else `None`."""
	if not remote:
		return None
	m = re.search(r"github\.com[/:]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", remote.strip())
	return f"{m.group(1)}/{m.group(2)}" if m else None


def major_of_branch(branch: str | None) -> int | None:
	"""`version-15` -> 15, `v15` -> 15; anything else -> None."""
	if not branch:
		return None
	m = re.fullmatch(r"(?:version-|v)(\d+)(?:[.-].*)?", branch.strip())
	return int(m.group(1)) if m else None


def _split(full_name: str) -> tuple[str, str]:
	parts = full_name.strip().strip("/").split("/")
	if len(parts) != 2 or not all(parts):
		raise ValidationError("repo must be owner/name", {"field": "repo"})
	return parts[0], parts[1]


def authenticated_clone_url(clone_url: str, token: str) -> str:
	"""`https://github.com/o/r.git` -> `https://x-access-token:<token>@github.com/o/r.git`.
	The result is a secret: masked in job output and passed to Ansible under no_log."""
	if not clone_url.startswith("https://"):
		raise ValidationError("Only https clone URLs can carry a token", {"field": "repo"})
	return "https://x-access-token:" + token + "@" + clone_url[len("https://") :]
