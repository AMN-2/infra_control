"""Pure bulk-rollout planner and state machine (A3.4, plan 9.3). No Frappe here.

The shell (`engine.py`) records every target's status and the operator's flags on the Bulk
Operation document, then asks `next_action` which single unit to run next: back up all targets,
run the canary, run one batch, or finish with a terminal/paused status. All of the branching —
canary-first, halt on canary failure, the `failure_policy` after a batch, pause at a batch
boundary and cancel after the current target — lives here so it is unit-tested without a site.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

from infra_control.core.enums import BulkPhase, BulkStatus, BulkTargetStatus, FailurePolicy

T = TypeVar("T")

CANARY_BATCH = 0
"""Batch index reserved for the canary target; real batches are numbered from 1."""

_TERMINAL_TARGET: frozenset[BulkTargetStatus] = frozenset(
	{BulkTargetStatus.SUCCESS, BulkTargetStatus.FAILED, BulkTargetStatus.SKIPPED}
)


class ActionKind(StrEnum):
	RUN_BACKUPS = "run_backups"
	RUN_CANARY = "run_canary"
	RUN_BATCH = "run_batch"
	FINISH = "finish"


@dataclass(frozen=True)
class Action:
	"""The one unit the driver should execute next. `batch` is set for RUN_BATCH, `status` for FINISH."""

	kind: ActionKind
	batch: int | None = None
	status: BulkStatus | None = None


@dataclass(frozen=True)
class TargetSnapshot:
	batch: int
	status: BulkTargetStatus


@dataclass(frozen=True)
class BulkState:
	failure_policy: FailurePolicy
	targets: tuple[TargetSnapshot, ...]
	cancel_requested: bool = False
	pause_requested: bool = False
	backup_needed: bool = False
	backup_done: bool = False


# ---------------------------------------------------------------------------------------
# Batch assignment
# ---------------------------------------------------------------------------------------
def plan_batches(targets: Sequence[T], canary: T, batch_size: int) -> tuple[list[int], int]:
	"""Assign each target a batch index and count the non-canary batches.

	The canary is batch 0; the remaining targets keep their input order and fill batches of
	`batch_size` numbered from 1. Returns `(batch_per_target, batches_total)` where
	`batch_per_target` is aligned with `targets` and `batches_total` excludes the canary.
	"""
	if batch_size < 1:
		raise ValueError("batch_size must be >= 1")
	assignments: list[int] = []
	non_canary = 0
	canary_assigned = False
	for target in targets:
		if target == canary and not canary_assigned:
			assignments.append(CANARY_BATCH)
			canary_assigned = True
		else:
			assignments.append(1 + non_canary // batch_size)
			non_canary += 1
	if not canary_assigned:
		raise ValueError("canary target is not one of the targets")
	return assignments, math.ceil(non_canary / batch_size) if non_canary else 0


# ---------------------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------------------
def next_action(state: BulkState) -> Action:
	"""Decide the single next unit from the current flags and per-target statuses."""
	# A cancel stops everything after the target currently running; the shell skips the rest.
	if state.cancel_requested:
		return Action(ActionKind.FINISH, status=BulkStatus.CANCELLED)

	# Step 1: back up every target once, before the canary runs.
	if state.backup_needed and not state.backup_done:
		return Action(ActionKind.RUN_BACKUPS)

	# Step 2: the canary. Its failure halts the whole operation; nothing else runs.
	canary = _canary(state)
	if canary is not None and canary.status not in _TERMINAL_TARGET:
		return Action(ActionKind.RUN_CANARY)
	if canary is not None and canary.status is BulkTargetStatus.FAILED:
		return Action(ActionKind.FINISH, status=BulkStatus.HALTED)

	# Step 3: the batches, honouring `failure_policy` once a batch has failed.
	if state.failure_policy is FailurePolicy.HALT and _any_batch_failed(state):
		return Action(ActionKind.FINISH, status=BulkStatus.HALTED)

	batch = _next_pending_batch(state)
	if batch is not None:
		# A pause takes effect at the next batch boundary; it is not terminal (resume continues).
		if state.pause_requested:
			return Action(ActionKind.FINISH, status=BulkStatus.PAUSED)
		return Action(ActionKind.RUN_BATCH, batch=batch)

	# Nothing left to run: decide the final status from the counters.
	return Action(ActionKind.FINISH, status=final_status(_failed_count(state), state.failure_policy))


def final_status(failed: int, failure_policy: FailurePolicy) -> BulkStatus:
	"""Terminal status once every target is done: Success with no failures, else policy-dependent."""
	if failed == 0:
		return BulkStatus.SUCCESS
	return BulkStatus.FAILED if failure_policy is FailurePolicy.CONTINUE else BulkStatus.HALTED


def phase_for(kind: ActionKind) -> BulkPhase:
	"""The display phase that a running action corresponds to (FINISH handled by the shell)."""
	return {
		ActionKind.RUN_BACKUPS: BulkPhase.BACKUP,
		ActionKind.RUN_CANARY: BulkPhase.CANARY,
		ActionKind.RUN_BATCH: BulkPhase.BATCHES,
		ActionKind.FINISH: BulkPhase.DONE,
	}[kind]


# ---------------------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------------------
def _canary(state: BulkState) -> TargetSnapshot | None:
	return next((t for t in state.targets if t.batch == CANARY_BATCH), None)


def _batch_numbers(state: BulkState) -> list[int]:
	return sorted({t.batch for t in state.targets if t.batch != CANARY_BATCH})


def _next_pending_batch(state: BulkState) -> int | None:
	"""The lowest-numbered batch that still has a pending target (so batches run in order)."""
	for batch in _batch_numbers(state):
		if any(t.batch == batch and t.status is BulkTargetStatus.PENDING for t in state.targets):
			return batch
	return None


def _any_batch_failed(state: BulkState) -> bool:
	return any(t.batch != CANARY_BATCH and t.status is BulkTargetStatus.FAILED for t in state.targets)


def _failed_count(state: BulkState) -> int:
	return sum(1 for t in state.targets if t.status is BulkTargetStatus.FAILED)
