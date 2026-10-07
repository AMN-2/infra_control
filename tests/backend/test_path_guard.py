"""A0.1: the CI path guard blocks cross-ownership changes (plan section 11.4)."""

from __future__ import annotations

import path_guard


def test_agent_a_cannot_touch_frontend() -> None:
	files = [
		"infra_control/api/jobs.py",
		"frontend/src/App.vue",
		"tests/frontend/unit/x.spec.ts",
		"docs/design/tokens.md",
	]
	assert path_guard.check("agent-a/A1.2-job-engine", files) == [
		"docs/design/tokens.md",
		"frontend/src/App.vue",
		"tests/frontend/unit/x.spec.ts",
	]


def test_agent_b_cannot_touch_backend() -> None:
	files = [
		"frontend/src/App.vue",
		"infra_control/api/jobs.py",
		"ansible/roles/base/tasks/main.yml",
		"docs/providers/x.md",
	]
	assert path_guard.check("agent-b/B1.1-design-system", files) == [
		"ansible/roles/base/tasks/main.yml",
		"docs/providers/x.md",
		"infra_control/api/jobs.py",
	]


def test_shared_paths_are_allowed_but_reported() -> None:
	files = ["contracts/openapi.yaml", "AGENTS.md", "docs/QUESTIONS.md", ".github/workflows/ci.yml"]
	assert path_guard.check("agent-a/A0.2-contracts", files) == []
	assert path_guard.check("agent-b/B0.1-scaffold", files) == []
	assert path_guard.shared(files) == sorted(files)


def test_human_branches_are_unrestricted() -> None:
	files = ["frontend/src/App.vue", "infra_control/api/jobs.py"]
	assert path_guard.check("fix/anything", files) == []
	assert path_guard.check("main", files) == []


def test_prefix_match_is_on_path_not_substring() -> None:
	# `my_frontend/` is not `frontend/`
	assert path_guard.check("agent-a/x", ["my_frontend/a.ts"]) == []
