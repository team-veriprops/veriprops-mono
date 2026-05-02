"""Reusable forward-only state-machine validator.

PRD §0.2 / §0.3. Used by Verification now and by Task in later phases.
"""
from __future__ import annotations

from typing import Dict, Set

from main.appodus_utils.exception.exceptions import InvalidResourceStateException


class StateMachine:
    def __init__(self, transitions: Dict[str, Set[str]], terminal: Set[str] | None = None):
        self._transitions = {k: set(v) for k, v in transitions.items()}
        self._terminal = set(terminal or set())

    def assert_can_transition(self, current: str, target: str, *, resource: str = "Resource") -> None:
        if current == target:
            return
        if current in self._terminal:
            raise InvalidResourceStateException(
                resource=resource,
                message=f"{resource} is in terminal state {current}",
            )
        allowed = self._transitions.get(current, set())
        if target not in allowed:
            raise InvalidResourceStateException(
                resource=resource,
                message=f"{resource}: cannot transition {current} → {target}",
            )

    def is_terminal(self, state: str) -> bool:
        return state in self._terminal


# PRD §0.2 verification state machine.
VERIFICATION_TRANSITIONS: Dict[str, Set[str]] = {
    "DRAFT": {"SUBMITTED", "CANCELLED"},
    "SUBMITTED": {"PAYMENT_PENDING", "CANCELLED"},
    "PAYMENT_PENDING": {"PAID", "CANCELLED", "FAILED"},
    "PAID": {"IN_PROGRESS", "CANCELLED", "REFUNDED", "FAILED"},
    "IN_PROGRESS": {"UNDER_REVIEW", "FAILED", "CANCELLED"},
    "UNDER_REVIEW": {"COMPLETED", "IN_PROGRESS", "FAILED"},
    "COMPLETED": {"DISPUTED"},
    "DISPUTED": {"COMPLETED", "REFUNDED"},
}
VERIFICATION_TERMINAL: Set[str] = {"CANCELLED", "REFUNDED", "FAILED"}

verification_state_machine = StateMachine(
    transitions=VERIFICATION_TRANSITIONS,
    terminal=VERIFICATION_TERMINAL,
)
