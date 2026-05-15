"""Tests for the FSM state machine."""

import pytest
from stoa.fsm.engine import FSMError, State, WorkflowFSM


def test_valid_happy_path():
    fsm = WorkflowFSM(task_id="test-1")
    fsm.transition(State.PLANNING, "starting")
    fsm.transition(State.EXECUTING, "plan ready")
    fsm.transition(State.VERIFYING, "steps done")
    fsm.transition(State.COMPLETE, "verified")
    assert fsm.current_state == State.COMPLETE
    assert fsm.is_terminal()


def test_invalid_transition_raises():
    fsm = WorkflowFSM(task_id="test-2")
    fsm.transition(State.PLANNING, "starting")
    with pytest.raises(FSMError):
        # Cannot jump from PLANNING directly to COMPLETE
        fsm.transition(State.COMPLETE, "illegal")


def test_recovery_path():
    fsm = WorkflowFSM(task_id="test-3")
    fsm.transition(State.PLANNING, "starting")
    fsm.transition(State.EXECUTING, "plan ready")
    fsm.transition(State.VERIFYING, "steps done")
    fsm.transition(State.RECOVERING, "step failed")
    fsm.transition(State.EXECUTING, "recovered")
    fsm.transition(State.VERIFYING, "retry done")
    fsm.transition(State.COMPLETE, "verified")
    assert fsm.current_state == State.COMPLETE
    assert fsm.recovery_attempts == 1


def test_max_recovery_exceeded():
    fsm = WorkflowFSM(task_id="test-4", max_recovery_attempts=2)
    fsm.transition(State.PLANNING, "starting")
    fsm.transition(State.EXECUTING, "plan ready")
    fsm.transition(State.VERIFYING, "steps done")
    fsm.transition(State.RECOVERING, "fail 1")
    fsm.transition(State.EXECUTING, "retry 1")
    fsm.transition(State.VERIFYING, "steps done again")
    fsm.transition(State.RECOVERING, "fail 2")
    fsm.transition(State.EXECUTING, "retry 2")
    fsm.transition(State.VERIFYING, "steps done again")
    with pytest.raises(FSMError, match="Max recovery"):
        fsm.transition(State.RECOVERING, "fail 3")


def test_trace_records_transitions():
    fsm = WorkflowFSM(task_id="test-5")
    fsm.transition(State.PLANNING, "starting")
    fsm.transition(State.EXECUTING, "plan ready")
    trace = fsm.trace()
    assert len(trace) == 2
    assert trace[0]["from"] == "pending"
    assert trace[0]["to"] == "planning"
