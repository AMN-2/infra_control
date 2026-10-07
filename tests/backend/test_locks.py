"""Security requirement 5 / plan 9.1 step 2: one running job per server, enforced by a Redis lock."""

from __future__ import annotations

from fake_frappe import FakeRedis

from infra_control.job_engine import locks


def test_only_one_holder_and_only_the_holder_releases() -> None:
	r = FakeRedis()
	key = locks.lock_key("server", "SRV-0001")
	assert key == "infra:lock:server:SRV-0001"
	assert locks.acquire(r, key, "JOB-00001") is True
	assert locks.acquire(r, key, "JOB-00002") is False, "a second job on the same server must wait"
	assert locks.acquire(r, key, "JOB-00001") is True, "re-entrant for the holder"
	assert locks.holder(r, key) == "JOB-00001"
	assert locks.release(r, key, "JOB-00002") is False
	assert locks.holder(r, key) == "JOB-00001"
	assert locks.release(r, key, "JOB-00001") is True
	assert locks.holder(r, key) is None
	assert locks.acquire(r, key, "JOB-00002") is True


def test_force_release_for_dead_workers() -> None:
	r = FakeRedis()
	key = locks.lock_key("site", "staging.client-c.frappe.cloud")
	locks.acquire(r, key, "JOB-00009")
	locks.force_release(r, key)
	assert locks.holder(r, key) is None


def test_different_servers_do_not_block_each_other() -> None:
	r = FakeRedis()
	assert locks.acquire(r, locks.lock_key("server", "SRV-0001"), "JOB-1")
	assert locks.acquire(r, locks.lock_key("server", "SRV-0002"), "JOB-2")
