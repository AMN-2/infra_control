"""Controller-held secrets that must never appear in job output, errors or audit rows (A4.1).

`controller_secret_values()` collects every value stored as a Password on `Infra Settings`
(Spaces key and secret, Telegram token, off-site backup credentials) so the job engine can
add them to the masking list of every job, whatever the job does. Reading them must never
fail a job: an unreadable settings document contributes nothing.
"""

from __future__ import annotations

import contextlib
from typing import Any

import frappe

PASSWORD_FIELDS: tuple[str, ...] = (
	"spaces_key",
	"spaces_secret",
	"telegram_bot_token",
	"offsite_key",
	"offsite_secret",
)


def controller_secret_values() -> list[str]:
	out: list[str] = []
	with contextlib.suppress(Exception):
		doc: Any = frappe.get_doc("Infra Settings")
		for field in PASSWORD_FIELDS:
			if not doc.get(field):
				continue
			with contextlib.suppress(Exception):
				value = doc.get_password(field)
				if isinstance(value, str) and len(value) >= 8:
					out.append(value)
	return out
