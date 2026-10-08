# ADR 0005: GitHub connections, repository browsing and version pickers

Date: 2026-10-09. Status: accepted (reviewer request 2026-10-08: "connect to GitHub from the
UI, full control over repositories, choose a version").

## Context

`bench.add_app` and `bench.update` (ADR 0004) take a repository URL and a branch typed by
hand. Operating a SaaS means choosing among the organisation's repositories, often private,
and pinning a branch or tag. The plan has no GitHub integration.

## Decision

- New DocType `Git Connection` (`label`, `provider: github`, `token` Password, verified
  `login`/`account_type`/`scopes`/`verified_at`, `enabled`). Tokens are personal access
  tokens pasted in the UI (no OAuth app to register); `git.connect` verifies the token against
  `GET /user` before storing it and audits the action. Tokens are never returned by any API.
- Read-only browsing endpoints under the `git` tag: `git.connections`, `git.connect`,
  `git.disconnect` (Infra Admin), `git.repos` (paged, newest pushed first, substring filter),
  `git.refs` (branches then tags). The client (`integrations/github.py`) follows the external
  HTTP rules: timeouts, bounded retries with jitter, rate-limit aware.
- Playbook `params_schema` may carry `x-picker: git_connection | git_repo | git_ref`. The
  UI renders a connection select, a repository search and a branch/tag select for those
  properties; the backend ignores the hint. `bench.add_app` gains `connection`.
- Private repositories: with a `connection`, the adapter passes
  `https://x-access-token:<token>@…` as `repo_auth_url`; the Ansible task runs under `no_log`,
  the engine adds the token to the job's secret list for masking, and the playbook resets the
  bench's remote to the clean URL right after the clone so the token never stays on the server.
- `bench.update` accepts a tag as `branch`: a detached checkout skips the pull.

## Consequences

Contract section `git` and the `Git Connection` DocType are additions to the plan (§6.1,
§5); tests `test_github_client.py`, `test_api_git.py`. Provisioning servers from a chosen
plan is ADR 0006.
