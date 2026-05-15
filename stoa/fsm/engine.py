"""Finite State Machine orchestration engine.

Every workflow runs through a fixed set of states in a fixed order.
The AI cannot invent new states or skip mandatory gates (like Verification).
This is how runaway loops become structurally impossible: the machine
simply has no transition that allows indefinite retry without bound.

States:
  PENDING → PLANNING → EXECUTING → VERIFYING → COMPLETE
                              ↓
                          FAILED (if budget exceeded or too many retries)
                              ↓
                          RECOVERING (Reflexion loop)
                              ↓ (back to EXECUTING or → FAILED)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FSMError(Exception):
    """Raised on illegal state transitions."""


class State(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    COMPLETE = "complete"
    FAILED = "failed"


# Allowlist of valid transitions. Any transition not in this set is illegal.
_VALID_TRANSITIONS: frozenset[tuple[State, State]] = frozenset({
    (State.PENDING,    State.PLANNING),
    (State.PLANNING,   State.EXECUTING),
    (State.EXECUTING,  State.VERIFYING),
    (State.VERIFYING,  State.COMPLETE),
    (State.VERIFYING,  State.RECOVERING),
    (State.RECOVERING, State.EXECUTING),
    (State.RECOVERING, State.FAILED),
    # Budget exceeded can short-circuit from any active state
    (State.PLANNING,   State.FAILED),
    (State.EXECUTING,  State.FAILED),
    (State.VERIFYING,  State.FAILED),
})


@dataclass
class Transition:
    from_state: State
    to_state: State
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowFSM:
    """Tracks state and enforces valid transitions for one workflow run."""

    task_id: str
    current_state: State = State.PENDING
    transitions: list[Transition] = field(default_factory=list)
    recovery_attempts: int = 0
    max_recovery_attempts: int = 3

    def transition(self, to: State, reason: str, metadata: dict[str, Any] | None = None) -> None:
        if (self.current_state, to) not in _VALID_TRANSITIONS:
            raise FSMError(
                f"Illegal transition {self.current_state.value} → {to.value} "
                f"for task {self.task_id}"
            )

        if to == State.RECOVERING:
            self.recovery_attempts += 1
            if self.recovery_attempts > self.max_recovery_attempts:
                raise FSMError(
                    f"Max recovery attempts ({self.max_recovery_attempts}) exceeded "
                    f"for task {self.task_id}. Failing."
                )

        self.transitions.append(
            Transition(
                from_state=self.current_state,
                to_state=to,
                reason=reason,
                metadata=metadata or {},
            )
        )
        self.current_state = to

    def is_terminal(self) -> bool:
        return self.current_state in (State.COMPLETE, State.FAILED)

    def trace(self) -> list[dict[str, Any]]:
        return [
            {
                "from": t.from_state.value,
                "to": t.to_state.value,
                "reason": t.reason,
                **t.metadata,
            }
            for t in self.transitions
        ]
