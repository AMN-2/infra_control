"""git.* (ADR 0005): GitHub connections and read-only repository browsing for the UI.

Tokens are stored encrypted on `Git Connection` and never returned. Browsing goes through
`integrations.github.GitHubClient` (timeouts, bounded retries, rate-limit aware).
"""

from __future__ import annotations

import builtins
from typing import Any

import frappe
from frappe.utils import now_datetime

from infra_control.api import _serialize as ser
from infra_control.api import api, int_param, str_param
from infra_control.core import audit
from infra_control.core.errors import NotFound, ValidationError
from infra_control.core.permissions import INFRA_ADMIN
from infra_control.integrations.github import GitHubClient

FIELDS = ["name", "label", "provider", "enabled", "login", "account_type", "scopes", "verified_at"]


def _client_for(connection: str) -> GitHubClient:
	if not frappe.db.exists("Git Connection", connection):
		raise NotFound("Git Connection", connection)
	doc: Any = frappe.get_doc("Git Connection", connection)
	if not doc.enabled:
		raise ValidationError(f"Git Connection {connection} is disabled", {"connection": connection})
	return GitHubClient(doc.get_password("token"))


def _serialized(row: dict[str, Any]) -> dict[str, Any]:
	return {
		"name": row["name"],
		"label": row["label"],
		"provider": row["provider"],
		"enabled": bool(row.get("enabled")),
		"login": row.get("login") or None,
		"account_type": row.get("account_type") or None,
		"scopes": [s.strip() for s in str(row.get("scopes") or "").split(",") if s.strip()],
		"verified_at": ser.iso_utc(row.get("verified_at")),
	}


@api()
def connections() -> dict[str, Any]:
	rows = frappe.get_all("Git Connection", fields=FIELDS, order_by="label asc")
	return {"items": [_serialized(r) for r in rows]}


@api(methods=("POST",), role=INFRA_ADMIN)
def connect(label: str | None = None, token: str | None = None) -> dict[str, Any]:
	"""Verify the token against GitHub, then store it (or replace an existing connection's)."""
	label_value = str_param("label", label, required=True) or ""
	token_value = str_param("token", token, required=True) or ""
	identity = GitHubClient(token_value).whoami()
	if frappe.db.exists("Git Connection", label_value):
		doc: Any = frappe.get_doc("Git Connection", label_value)
	else:
		doc = frappe.get_doc({"doctype": "Git Connection", "label": label_value, "provider": "github"})
	doc.token = token_value
	doc.enabled = 1
	doc.login = identity.login
	doc.account_type = identity.account_type
	doc.scopes = identity.scopes
	doc.verified_at = now_datetime()
	if doc.get("name"):
		doc.save()
	else:
		doc.insert()
	audit.record("git.connect", result="success", params={"label": label_value})
	row = frappe.get_all("Git Connection", filters={"name": doc.name}, fields=FIELDS)[0]
	return {"connection": _serialized(row)}


@api(methods=("POST",), role=INFRA_ADMIN)
def disconnect(connection: str | None = None) -> dict[str, Any]:
	name = str_param("connection", connection, required=True) or ""
	if not frappe.db.exists("Git Connection", name):
		raise NotFound("Git Connection", name)
	frappe.delete_doc("Git Connection", name, ignore_permissions=True)
	audit.record("git.disconnect", result="success", params={"connection": name})
	return {"connection": name, "deleted": True}


@api()
def repos(connection: str | None = None, query: str | None = None, page: Any = None) -> dict[str, Any]:
	name = str_param("connection", connection, required=True) or ""
	page_no = int_param("page", page, default=1, minimum=1, maximum=100)
	items, has_more = _client_for(name).list_repos(str_param("query", query) or "", page_no)
	return {"items": items, "next_page": page_no + 1 if has_more else None}


@api()
def refs(connection: str | None = None, repo: str | None = None) -> dict[str, Any]:
	name = str_param("connection", connection, required=True) or ""
	full_name = str_param("repo", repo, required=True) or ""
	client = _client_for(name)
	meta = client.get_repo(full_name)
	return {"repo": meta, "items": client.list_refs(full_name)}


def token_for(connection: str) -> str:
	"""The stored token of an enabled connection (for the provider layer, never for responses)."""
	if not frappe.db.exists("Git Connection", connection):
		raise NotFound("Git Connection", connection)
	doc: Any = frappe.get_doc("Git Connection", connection)
	if not doc.enabled:
		raise ValidationError(f"Git Connection {connection} is disabled", {"connection": connection})
	token: str = doc.get_password("token")
	return token


def connection_rows() -> builtins.list[dict[str, Any]]:
	return [dict(r) for r in frappe.get_all("Git Connection", fields=FIELDS)]
