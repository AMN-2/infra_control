"""Redis locks: one running job per server (plan section 9.1 step 2, security requirement 5).

Key: `infra:lock:server:<name>`; for targets without a server (Frappe Cloud) `infra:lock:site:<name>`
or `infra:lock:bench:<name>`; `infra:lock:provider:<name>` for account-level jobs. The value is a
token (the job name) so only the holder can release, via a compare-and-delete Lua script.
"""

from __future__ import annotations

from typing import Any, Protocol

PREFIX = "infra:lock:"
DEFAULT_TTL_SECONDS = 6 * 60 * 60  # a job that outlives this is dead; crash recovery also releases

_RELEASE = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
else
  return 0
end
"""


class RedisLike(Protocol):
	def set(self, name: str, value: str, *, nx: bool = ..., ex: int | None = ...) -> Any: ...
	def get(self, name: str) -> Any: ...
	def delete(self, *names: str) -> Any: ...
	def eval(self, script: str, numkeys: int, *keys_and_args: str) -> Any: ...


def lock_key(scope: str, name: str) -> str:
	return f"{PREFIX}{scope}:{name}"


def acquire(client: RedisLike, key: str, token: str, ttl: int = DEFAULT_TTL_SECONDS) -> bool:
	"""Atomically take the lock. Re-entrant for the same token (a retried worker run)."""
	if client.set(key, token, nx=True, ex=ttl):
		return True
	return holder(client, key) == token


def release(client: RedisLike, key: str, token: str) -> bool:
	"""Release only if we still hold it; returns whether a lock was removed."""
	return bool(client.eval(_RELEASE, 1, key, token))


def force_release(client: RedisLike, key: str) -> None:
	"""Crash recovery: the holder is dead, drop the lock regardless of token."""
	client.delete(key)


def holder(client: RedisLike, key: str) -> str | None:
	value = client.get(key)
	if value is None:
		return None
	return value.decode() if isinstance(value, bytes) else str(value)
