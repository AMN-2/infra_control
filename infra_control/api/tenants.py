"""tenants.* (A4.x): the commercial layer over sites. A Tenant groups the sites of one client
with contact, plan and status; suspend/activate turn into one `site.suspend` job per site, so
nothing touches a server outside a job."""

from __future__ import annotations

import builtins
from typing import Any

import frappe

from infra_control.api import _serialize as ser
from infra_control.api import api, bool_param, enum_param, int_param, str_param
from infra_control.api._inventory_helpers import child_values
from infra_control.api._pagination import LIMIT_DEFAULT, LIMIT_MAX, page_by_name
from infra_control.core.enums import TenantStatus
from infra_control.core.errors import InfraError, InvalidState, NotFound, ValidationError
from infra_control.core.permissions import INFRA_OPERATOR
from infra_control.job_engine import engine

FIELDS = ["name", "label", "title", "status", "plan", "contact_email", "contact_phone", "notes", "modified"]
STATUSES = tuple(str(s) for s in TenantStatus)


def _sites_of(names: builtins.list[str]) -> dict[str, builtins.list[str]]:
	return child_values("Tenant", "Tenant Site", "site", names)


def _site_rows(sites: builtins.list[str]) -> builtins.list[dict[str, Any]]:
	if not sites:
		return []
	rows = frappe.get_all(
		"Site", filters={"name": ["in", sites]}, fields=["name", "domain", "status", "server", "bench"]
	)
	return [
		{
			"name": r["name"],
			"domain": r["domain"],
			"status": r["status"],
			"server": r.get("server"),
			"bench": r.get("bench"),
		}
		for r in sorted(rows, key=lambda r: str(r["domain"]))
	]


def _serialize(row: dict[str, Any], sites: builtins.list[str]) -> dict[str, Any]:
	return {
		"name": row["name"],
		"label": row["label"],
		"title": row["title"],
		"status": row["status"],
		"plan": row.get("plan") or None,
		"contact_email": row.get("contact_email") or None,
		"contact_phone": row.get("contact_phone") or None,
		"notes": row.get("notes") or None,
		"site_count": len(sites),
		"modified_at": ser.iso_utc(row.get("modified")),
	}


def _detail(name: str) -> dict[str, Any]:
	rows = frappe.get_all("Tenant", filters={"name": name}, fields=FIELDS, limit=1)
	if not rows:
		raise NotFound("Tenant", name)
	sites = _sites_of([name]).get(name, [])
	return {**_serialize(rows[0], sites), "sites": _site_rows(sites)}


@api()
def list(
	status: str | None = None, query: str | None = None, limit: Any = None, cursor: str | None = None
) -> dict[str, Any]:
	filters: dict[str, Any] = {}
	if st := enum_param("status", status, STATUSES):
		filters["status"] = st
	if q := str_param("query", query):
		filters["title"] = ["like", f"%{q}%"]
	page = page_by_name(
		"Tenant",
		filters=filters,
		fields=FIELDS,
		limit=int_param("limit", limit, default=LIMIT_DEFAULT, minimum=1, maximum=LIMIT_MAX),
		cursor=cursor,
		serialize=lambda r: r,
	)
	sites = _sites_of([r["name"] for r in page["items"]])
	page["items"] = [_serialize(r, sites.get(r["name"], [])) for r in page["items"]]
	return page


@api()
def get(tenant: str | None = None) -> dict[str, Any]:
	return _detail(str_param("tenant", tenant, required=True) or "")


def _apply(doc: Any, title: Any, plan: Any, contact_email: Any, contact_phone: Any, notes: Any) -> None:
	if title is not None:
		value = str_param("title", title, required=True) or ""
		doc.title = value
	for field, raw in (
		("plan", plan),
		("contact_email", contact_email),
		("contact_phone", contact_phone),
		("notes", notes),
	):
		if raw is not None:
			doc.set(field, str(raw).strip() or None)
	if doc.contact_email and "@" not in str(doc.contact_email):
		raise ValidationError("contact_email is not an email address", {"field": "contact_email"})


@api(methods=("POST",), role=INFRA_OPERATOR)
def create(
	label: str | None = None,
	title: str | None = None,
	plan: str | None = None,
	contact_email: str | None = None,
	contact_phone: str | None = None,
	notes: str | None = None,
) -> dict[str, Any]:
	label_value = (str_param("label", label, required=True) or "").strip().upper()
	if frappe.db.exists("Tenant", label_value):
		raise InvalidState(f"Tenant {label_value} already exists", {"tenant": label_value})
	doc: Any = frappe.get_doc(
		{"doctype": "Tenant", "label": label_value, "title": label_value, "status": "active"}
	)
	_apply(doc, title or label_value, plan, contact_email, contact_phone, notes)
	doc.insert()
	return {"tenant": _detail(str(doc.name))}


@api(methods=("POST",), role=INFRA_OPERATOR)
def update(
	tenant: str | None = None,
	title: str | None = None,
	plan: str | None = None,
	contact_email: str | None = None,
	contact_phone: str | None = None,
	notes: str | None = None,
) -> dict[str, Any]:
	name = str_param("tenant", tenant, required=True) or ""
	if not frappe.db.exists("Tenant", name):
		raise NotFound("Tenant", name)
	doc: Any = frappe.get_doc("Tenant", name)
	_apply(doc, title, plan, contact_email, contact_phone, notes)
	doc.save()
	return {"tenant": _detail(name)}


@api(methods=("POST",), role=INFRA_OPERATOR)
def assign(tenant: str | None = None, site: str | None = None, remove: Any = None) -> dict[str, Any]:
	"""Attach a site to the tenant (one tenant per site), or detach it with `remove`."""
	name = str_param("tenant", tenant, required=True) or ""
	site_name = str_param("site", site, required=True) or ""
	if not frappe.db.exists("Tenant", name):
		raise NotFound("Tenant", name)
	if not frappe.db.exists("Site", site_name):
		raise NotFound("Site", site_name)
	detach = bool_param("remove", remove, default=False)
	doc: Any = frappe.get_doc("Tenant", name)
	current = [str(r.get("site")) for r in doc.get("sites") or []]
	if detach:
		if site_name not in current:
			raise InvalidState(f"{site_name} is not a site of {name}", {"site": site_name})
		doc.set("sites", [{"site": s} for s in current if s != site_name])
	else:
		other = frappe.get_all(
			"Tenant Site", filters={"site": site_name, "parent": ["!=", name]}, pluck="parent", limit=1
		)
		if other:
			raise InvalidState(
				f"{site_name} already belongs to {other[0]}", {"site": site_name, "tenant": other[0]}
			)
		if site_name not in current:
			doc.append("sites", {"site": site_name})
	doc.save()
	return {"tenant": _detail(name)}


@api(methods=("POST",), role=INFRA_OPERATOR)
def suspend(tenant: str | None = None, suspended: Any = None) -> dict[str, Any]:
	"""Suspend or activate every site of the tenant: one `site.suspend` job per site."""
	name = str_param("tenant", tenant, required=True) or ""
	if not frappe.db.exists("Tenant", name):
		raise NotFound("Tenant", name)
	on = bool_param("suspended", suspended, default=True)
	jobs: builtins.list[str] = []
	errors: builtins.list[dict[str, str]] = []
	for site in _sites_of([name]).get(name, []):
		try:
			job = engine.create_job("site.suspend", "Site", site, {"suspended": on})
			jobs.append(str(job.name))
		except InfraError as exc:
			errors.append({"site": site, "error": str(exc)})
	frappe.db.set_value("Tenant", name, "status", "suspended" if on else "active")
	return {"tenant": _detail(name), "jobs": jobs, "errors": errors}
