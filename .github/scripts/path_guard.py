"""CI path guard (plan section 11.4).

A PR from `agent-a/*` must not touch Agent B's paths and vice versa. Shared paths are allowed
for both agents but need human approval; they are reported, not blocked.

Usage in CI:  python .github/scripts/path_guard.py --branch "$HEAD_REF" --base "origin/$BASE_REF"
Usage in tests: ``check(branch, files)`` returns the list of violations.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Iterable

FORBIDDEN: dict[str, tuple[str, ...]] = {
	"agent-a/": ("frontend/", "tests/frontend/", "docs/design/"),
	"agent-b/": ("infra_control/", "ansible/", "tests/backend/", "docs/providers/", "docs/runbooks/"),
}

SHARED: tuple[str, ...] = ("contracts/", "AGENTS.md", "docs/QUESTIONS.md", ".github/")


def owner_prefix(branch: str) -> str | None:
	for prefix in FORBIDDEN:
		if branch.startswith(prefix):
			return prefix
	return None


def check(branch: str, files: Iterable[str]) -> list[str]:
	"""Return the changed files that the branch owner is not allowed to touch."""
	prefix = owner_prefix(branch)
	if prefix is None:
		return []
	forbidden = FORBIDDEN[prefix]
	return sorted(f for f in files if f.startswith(forbidden))


def shared(files: Iterable[str]) -> list[str]:
	return sorted(f for f in files if f.startswith(SHARED))


def changed_files(base: str) -> list[str]:
	out = subprocess.run(
		["git", "diff", "--name-only", f"{base}...HEAD"],
		check=True,
		capture_output=True,
		text=True,
	).stdout
	return [line.strip() for line in out.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--branch", required=True, help="head branch name, e.g. agent-a/A0.1-scaffold")
	parser.add_argument("--base", required=True, help="base ref, e.g. origin/main")
	args = parser.parse_args(argv)

	files = changed_files(args.base)
	violations = check(args.branch, files)
	needs_approval = shared(files)

	if needs_approval:
		print("::notice::Shared paths changed; human approval required:")
		for f in needs_approval:
			print(f"  {f}")

	if violations:
		print(f"::error::Branch {args.branch} touches paths it does not own:")
		for f in violations:
			print(f"  {f}")
		return 1

	print(f"path guard ok for {args.branch} ({len(files)} changed files)")
	return 0


if __name__ == "__main__":
	sys.exit(main())
