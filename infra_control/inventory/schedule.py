"""Hourly `inventory.sync` for every enabled Provider Account (hooks.scheduler_events).

The scheduler never calls a provider itself: it creates `Infra Job`s like any user would, so
the run is audited, locked per account and visible in the UI. An account with a sync already
queued or running is skipped, so a slow discovery never piles up.
"""

from __future__ import annotations

import frappe

from infra_control.core.errors import InfraError
from infra_control.job_engine import engine

PLAYBOOK = "inventory.sync"


def sync_all_providers() -> list[str]:
	"""Returns the names of the jobs created."""
	created: list[str] = []
	busy = {
		row["target_name"]
		for row in frappe.get_all(
			"Infra Job",
			filters={"playbook": PLAYBOOK, "status": ["in", ["Queued", "Running"]]},
			fields=["target_name"],
		)
	}
	for account in frappe.get_all("Provider Account", filters={"enabled": 1}, pluck="name"):
		if account in busy:
			continue
		try:
			job = engine.create_job(PLAYBOOK, "Provider Account", account, user=engine.SCHEDULER_USER)
		except InfraError as exc:
			# Audited by create_job already; the scheduler just moves on to the next account.
			frappe.log_error(title=f"inventory.sync not scheduled for {account}", message=str(exc))
			continue
		created.append(str(job.name))
	return created
