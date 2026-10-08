"""ADR 0005: the GitHub client over mocked HTTP: identity, repositories, refs, auth URL, errors."""

from __future__ import annotations

import pytest
import responses

from infra_control.core.errors import NotFound, ProviderError, RateLimited, ValidationError
from infra_control.integrations.github import API_BASE, GitHubClient, authenticated_clone_url


def client() -> GitHubClient:
	return GitHubClient("ghp_test", sleep=lambda s: None)


@responses.activate
def test_whoami_reads_login_type_and_scopes() -> None:
	responses.get(
		f"{API_BASE}/user",
		json={"login": "smartchoice-iq", "type": "Organization"},
		headers={"X-OAuth-Scopes": "repo, read:org"},
	)
	who = client().whoami()
	assert (who.login, who.account_type, who.scopes) == ("smartchoice-iq", "Organization", "repo, read:org")
	assert responses.calls[0].request.headers["Authorization"] == "Bearer ghp_test"


@responses.activate
def test_bad_token_is_a_validation_error_and_404_not_found() -> None:
	responses.get(f"{API_BASE}/user", status=401, json={"message": "Bad credentials"})
	with pytest.raises(ValidationError):
		client().whoami()
	responses.get(f"{API_BASE}/repos/x/y", status=404, json={"message": "Not Found"})
	with pytest.raises(NotFound):
		client().get_repo("x/y")


@responses.activate
def test_repos_page_filters_by_query_and_reports_more() -> None:
	rows = [
		{
			"full_name": "org/smart_features",
			"name": "smart_features",
			"owner": {"login": "org"},
			"private": True,
			"default_branch": "develop",
			"clone_url": "https://github.com/org/smart_features.git",
			"description": None,
			"pushed_at": "2026-10-08T21:10:00Z",
		},
		{
			"full_name": "frappe/erpnext",
			"name": "erpnext",
			"owner": {"login": "frappe"},
			"private": False,
			"default_branch": "develop",
			"clone_url": "https://github.com/frappe/erpnext.git",
			"description": "ERP",
			"pushed_at": None,
		},
	]
	responses.get(
		f"{API_BASE}/user/repos",
		json=rows,
		headers={"Link": '<https://api.github.com/user/repos?page=2>; rel="next"'},
	)
	items, more = client().list_repos("smart", 1)
	assert more is True and [r["full_name"] for r in items] == ["org/smart_features"]
	assert items[0]["private"] is True and items[0]["description"] is None
	q = responses.calls[0].request.url or ""
	assert "affiliation=owner%2Ccollaborator%2Corganization_member" in q and "page=1" in q


@responses.activate
def test_refs_are_branches_then_tags() -> None:
	responses.get(
		f"{API_BASE}/repos/frappe/erpnext/branches",
		json=[{"name": "develop", "commit": {"sha": "1a2b3c4d5e6f7890"}}],
	)
	responses.get(
		f"{API_BASE}/repos/frappe/erpnext/tags",
		json=[{"name": "v15.48.0", "commit": {"sha": "3c4d5e6f70819abc"}}],
	)
	refs = client().list_refs("frappe/erpnext")
	assert refs == [
		{"name": "develop", "kind": "branch", "sha": "1a2b3c4d5e6f"},
		{"name": "v15.48.0", "kind": "tag", "sha": "3c4d5e6f7081"},
	]
	with pytest.raises(ValidationError):
		client().list_refs("not-a-repo")


@responses.activate
def test_rate_limit_and_retries() -> None:
	responses.get(
		f"{API_BASE}/user", status=403, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "0"}
	)
	with pytest.raises(RateLimited):
		client().whoami()
	responses.get(f"{API_BASE}/user", status=503)
	responses.get(f"{API_BASE}/user", status=503)
	responses.get(f"{API_BASE}/user", status=503)
	with pytest.raises(ProviderError):
		client().whoami()
	assert len(responses.calls) == 4


def test_authenticated_clone_url_only_for_https() -> None:
	assert (
		authenticated_clone_url("https://github.com/o/r.git", "tok")
		== "https://x-access-token:tok@github.com/o/r.git"
	)
	with pytest.raises(ValidationError):
		authenticated_clone_url("git@github.com:o/r.git", "tok")
	with pytest.raises(ValidationError):
		GitHubClient("  ")
