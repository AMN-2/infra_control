"""Update checks for the apps on a bench (ADR 0009).

Discovery records, per app, the checked-out branch, the short commit and the token-free remote
URL. This module asks GitHub how far upstream has moved: the tip of the app's branch, how many
commits the bench is behind, and the newest version tag of the same major. Results are stored
on the `Bench App` rows (`upstream_commit`, `behind`, `latest_tag`, `checked_at`) so the UI can
show "update available" without asking GitHub on every page view.

Read-only against GitHub and the database; nothing here touches a server (AGENTS.md: only an
Infra Job mutates infrastructure). The token of the first enabled Git Connection is used when
there is one (private repositories, higher rate limit), else the anonymous API.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import frappe

from infra_control.core.errors import InfraError, NotFound, ValidationError
from infra_control.integrations.github import GitHubClient, github_repo_of, major_of_branch

APP_FIELDS = [
	"app",
	"version",
	"branch",
	"commit",
	"remote",
	"upstream_commit",
	"behind",
	"latest_tag",
	"checked_at",
]


def client() -> GitHubClient:
	rows = frappe.get_all(
		"Git Connection", filters={"enabled": 1}, fields=["name"], order_by="label asc", limit=1
	)
	if rows:
		doc: Any = frappe.get_doc("Git Connection", rows[0]["name"])
		return GitHubClient(doc.get_password("token"))
	return GitHubClient(None)


def check_app(gh: GitHubClient, app: dict[str, Any]) -> dict[str, Any]:
	"""Upstream state for one app row; apps that are not on GitHub stay unknown (no error)."""
	repo = github_repo_of(app.get("remote"))
	branch = app.get("branch") or ""
	out: dict[str, Any] = {"upstream_commit": None, "behind": None, "latest_tag": None, "error": None}
	if not repo or not branch or (len(branch) == 12 and branch.isalnum() and "-" not in branch):
		out["error"] = "not a GitHub branch checkout"
		return out
	try:
		out["upstream_commit"] = gh.branch_head(repo, branch)
		if app.get("commit"):
			out["behind"] = (
				0
				if str(app["commit"]).startswith(str(out["upstream_commit"]))
				else gh.commits_behind(repo, str(app["commit"]), branch)
			)
		out["latest_tag"] = gh.latest_tag(repo, major_of_branch(branch))
	except InfraError as exc:
		out["error"] = exc.message
	return out


def check_bench(name: str) -> list[dict[str, Any]]:
	"""Refresh the upstream state of every app on the bench and return the rows."""
	if not frappe.db.exists("Bench", name):
		raise NotFound("Bench", name)
	doc: Any = frappe.get_doc("Bench", name)
	rows = list(doc.get("apps") or [])
	if not rows:
		raise ValidationError(
			"The bench has no discovered apps yet; run inventory discovery first", {"bench": name}
		)
	gh = client()
	now = datetime.now(UTC).replace(tzinfo=None)
	for row in rows:
		result = check_app(gh, {f: row.get(f) for f in ("branch", "commit", "remote")})
		# Child rows are Documents in Frappe and plain dicts in the unit-test fake: `update` works on both.
		row.update(
			{
				"upstream_commit": result["upstream_commit"],
				"behind": result["behind"],
				"latest_tag": result["latest_tag"],
				"checked_at": now if result["error"] is None else row.get("checked_at"),
			}
		)
	doc.flags.ignore_permissions = True
	doc.save()
	return [{f: row.get(f) for f in APP_FIELDS} for row in rows]


def refs_for(bench: str, app: str) -> dict[str, Any]:
	"""Branches and tags of the app's upstream repository, for the version switch."""
	if not frappe.db.exists("Bench", bench):
		raise NotFound("Bench", bench)
	doc: Any = frappe.get_doc("Bench", bench)
	row = next((r for r in doc.get("apps") or [] if str(r.get("app")) == app), None)
	if row is None:
		raise NotFound("Bench App", f"{bench}/{app}")
	repo = github_repo_of(row.get("remote"))
	if not repo:
		raise ValidationError(
			f"{app} is not checked out from GitHub; its versions cannot be listed", {"app": app}
		)
	gh = client()
	return {"repo": gh.get_repo(repo), "items": gh.list_refs(repo)}
