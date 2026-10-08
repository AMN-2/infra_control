"""A3.4 pure planner: batch assignment and the bulk state machine, without any Frappe."""

from __future__ import annotations

import pytest

from infra_control.bulk import plan
from infra_control.bulk.plan import ActionKind, BulkState, TargetSnapshot
from infra_control.core.enums import BulkStatus, BulkTargetStatus, FailurePolicy

PENDING = BulkTargetStatus.PENDING
RUNNING = BulkTargetStatus.RUNNING
SUCCESS = BulkTargetStatus.SUCCESS
FAILED = BulkTargetStatus.FAILED
SKIPPED = BulkTargetStatus.SKIPPED


# ----- batch assignment --------------------------------------------------------------------
def test_canary_is_batch_zero_and_the_rest_fill_batches_in_order() -> None:
	targets = ["a", "b", "c", "d", "e"]
	assignments, total = plan.plan_batches(targets, "c", batch_size=2)
	# c is the canary (batch 0); a,b -> batch 1; d,e -> batch 2, input order preserved.
	assert assignments == [1, 1, 0, 2, 2]
	assert total == 2


def test_single_target_canary_has_no_batches() -> None:
	assignments, total = plan.plan_batches(["only"], "only", batch_size=5)
	assert assignments == [0] and total == 0


def test_batch_size_larger_than_targets_is_one_batch() -> None:
	assignments, total = plan.plan_batches(["c", "a", "b"], "c", batch_size=10)
	assert assignments == [0, 1, 1] and total == 1


def test_canary_must_be_a_target_and_batch_size_must_be_positive() -> None:
	with pytest.raises(ValueError, match="canary"):
		plan.plan_batches(["a", "b"], "z", batch_size=2)
	with pytest.raises(ValueError, match="batch_size"):
		plan.plan_batches(["a"], "a", batch_size=0)


# ----- helpers -----------------------------------------------------------------------------
def _state(
	targets: list[tuple[int, BulkTargetStatus]],
	*,
	policy: FailurePolicy = FailurePolicy.HALT,
	cancel: bool = False,
	pause: bool = False,
	backup_needed: bool = False,
	backup_done: bool = False,
) -> BulkState:
	return BulkState(
		failure_policy=policy,
		targets=tuple(TargetSnapshot(batch=b, status=s) for b, s in targets),
		cancel_requested=cancel,
		pause_requested=pause,
		backup_needed=backup_needed,
		backup_done=backup_done,
	)


# ----- state machine -----------------------------------------------------------------------
def test_backups_run_before_the_canary() -> None:
	state = _state([(0, PENDING), (1, PENDING)], backup_needed=True, backup_done=False)
	assert plan.next_action(state).kind is ActionKind.RUN_BACKUPS


def test_canary_runs_first_then_the_batches() -> None:
	assert plan.next_action(_state([(0, PENDING), (1, PENDING)])).kind is ActionKind.RUN_CANARY
	after_canary = _state([(0, SUCCESS), (1, PENDING), (1, PENDING)])
	action = plan.next_action(after_canary)
	assert action.kind is ActionKind.RUN_BATCH and action.batch == 1


def test_batches_run_in_order() -> None:
	state = _state([(0, SUCCESS), (1, SUCCESS), (2, PENDING)])
	action = plan.next_action(state)
	assert action.kind is ActionKind.RUN_BATCH and action.batch == 2


def test_canary_failure_halts_and_nothing_else_runs() -> None:
	action = plan.next_action(_state([(0, FAILED), (1, PENDING), (1, PENDING)]))
	assert action.kind is ActionKind.FINISH and action.status is BulkStatus.HALTED


def test_batch_failure_halts_under_halt_policy() -> None:
	state = _state([(0, SUCCESS), (1, FAILED), (2, PENDING)], policy=FailurePolicy.HALT)
	action = plan.next_action(state)
	assert action.kind is ActionKind.FINISH and action.status is BulkStatus.HALTED


def test_batch_failure_continues_under_continue_policy() -> None:
	state = _state([(0, SUCCESS), (1, FAILED), (2, PENDING)], policy=FailurePolicy.CONTINUE)
	action = plan.next_action(state)
	assert action.kind is ActionKind.RUN_BATCH and action.batch == 2


def test_pause_stops_at_the_next_batch_boundary() -> None:
	state = _state([(0, SUCCESS), (1, SUCCESS), (2, PENDING)], pause=True)
	action = plan.next_action(state)
	assert action.kind is ActionKind.FINISH and action.status is BulkStatus.PAUSED


def test_pause_does_not_fire_when_there_is_no_batch_left() -> None:
	# All done: a pending pause request is irrelevant; decide the final status instead.
	state = _state([(0, SUCCESS), (1, SUCCESS)], pause=True)
	action = plan.next_action(state)
	assert action.kind is ActionKind.FINISH and action.status is BulkStatus.SUCCESS


def test_cancel_wins_immediately() -> None:
	state = _state([(0, SUCCESS), (1, RUNNING), (2, PENDING)], cancel=True)
	action = plan.next_action(state)
	assert action.kind is ActionKind.FINISH and action.status is BulkStatus.CANCELLED


def test_success_path_final_status() -> None:
	state = _state([(0, SUCCESS), (1, SUCCESS), (1, SUCCESS)])
	action = plan.next_action(state)
	assert action.kind is ActionKind.FINISH and action.status is BulkStatus.SUCCESS


def test_continue_policy_final_status_is_failed_when_any_failed() -> None:
	state = _state([(0, SUCCESS), (1, SUCCESS), (1, FAILED)], policy=FailurePolicy.CONTINUE)
	action = plan.next_action(state)
	assert action.kind is ActionKind.FINISH and action.status is BulkStatus.FAILED


def test_final_status_counter_rule() -> None:
	assert plan.final_status(0, FailurePolicy.HALT) is BulkStatus.SUCCESS
	assert plan.final_status(0, FailurePolicy.CONTINUE) is BulkStatus.SUCCESS
	assert plan.final_status(2, FailurePolicy.CONTINUE) is BulkStatus.FAILED
	assert plan.final_status(2, FailurePolicy.HALT) is BulkStatus.HALTED


def test_skipped_targets_do_not_block_completion() -> None:
	# Cancel already applied by the shell: remaining are Skipped, so the run finishes.
	state = _state([(0, SUCCESS), (1, SUCCESS), (2, SKIPPED)])
	action = plan.next_action(state)
	assert action.kind is ActionKind.FINISH and action.status is BulkStatus.SUCCESS
