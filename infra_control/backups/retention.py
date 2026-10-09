"""Backup retention (A4.2): keep the newest `retain` backups per kind for each site with a
policy, delete the rest from Spaces and from the `Backup` list. Runs daily; a Spaces failure
for one object never stops the sweep, and nothing is removed from the list before the object
is gone (so a backup still in storage stays restorable)."""

from __future__ import annotations

from typing import Any

import frappe

from infra_control.providers.digitalocean import settings, spaces


def to_prune(rows: list[dict[str, Any]], retain: int) -> list[dict[str, Any]]:
	"""Pure: rows (any order) -> the ones beyond `retain` per kind, oldest first. 0 keeps all."""
	if retain <= 0:
		return []
	by_kind: dict[str, list[dict[str, Any]]] = {}
	for r in rows:
		by_kind.setdefault(str(r.get("kind")), []).append(r)
	out: list[dict[str, Any]] = []
	for group in by_kind.values():
		group.sort(key=lambda r: str(r.get("created_at") or r.get("creation") or ""), reverse=True)
		out.extend(reversed(group[retain:]))
	return out


def prune() -> dict[str, int]:
	"""Daily scheduler entry. Returns counts for the log."""
	client = settings.spaces_client()
	deleted = kept_on_error = 0
	for policy in frappe.get_all("Backup Policy", filters={"retain": [">", 0]}, fields=["site", "retain"]):
		rows = frappe.get_all(
			"Backup",
			filters={"site": policy["site"]},
			fields=["name", "kind", "location", "created_at", "creation"],
		)
		for row in to_prune(rows, int(policy["retain"])):
			location = str(row.get("location") or "")
			try:
				if location.startswith("spaces://") and client is not None:
					_bucket, key = spaces.parse_location(location)
					client.delete(key)
			except Exception as exc:  # one object failing must not stop the sweep
				kept_on_error += 1
				frappe.log_error(title=f"backup retention: {row['name']} not deleted", message=str(exc))
				continue
			frappe.delete_doc("Backup", row["name"], ignore_permissions=True, force=True)
			deleted += 1
	frappe.db.commit()
	return {"deleted": deleted, "kept_on_error": kept_on_error}
