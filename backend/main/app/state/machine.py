"""Reusable forward-only state-machine validator and authoritative transition tables.

PRD §0.2 (Verification), §5 (Task), §8 (Report).
All domain state machines are defined here so there is one canonical source of truth.
"""
from __future__ import annotations

from typing import Dict, Set

from main.appodus_utils.exception.exceptions import IllegalStateTransitionException


class StateMachine:
    """Forward-only state-machine validator.

    Raises IllegalStateTransitionException (a subclass of InvalidResourceStateException)
    on any move not explicitly allowed by the transition table.
    Terminal states reject all outgoing transitions regardless of the table.
    Same-state self-loops are silently allowed (idempotent updates).
    """

    def __init__(self, transitions: Dict[str, Set[str]], terminal: Set[str] | None = None):
        self._transitions = {k: set(v) for k, v in transitions.items()}
        self._terminal = set(terminal or set())

    def assert_can_transition(self, current: str, target: str, *, resource: str = "Resource") -> None:
        if current == target:
            return
        if current in self._terminal:
            raise IllegalStateTransitionException(
                resource=resource,
                from_state=current,
                to_state=target,
                message=f"{resource} is in terminal state {current!r} — no further transitions allowed",
            )
        allowed = self._transitions.get(current, set())
        if target not in allowed:
            raise IllegalStateTransitionException(
                resource=resource,
                from_state=current,
                to_state=target,
            )

    def is_terminal(self, state: str) -> bool:
        return state in self._terminal

    def allowed_transitions(self, current: str) -> Set[str]:
        """Return the set of valid next states from *current* (empty for terminal states)."""
        if current in self._terminal:
            return set()
        return set(self._transitions.get(current, set()))


# ── Verification state machine (PRD §0.2) ──────────────────────────────────
#
# Global state derives from task states (see derive.py / R0.16); the transitions
# below cover only the explicitly-permitted moves. State is managed by
# VerificationService and guarded by VerificationValidator.
#
# Terminal states: CANCELLED, REFUNDED, FAILED (no exits once reached).

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


# ── Task state machine (PRD §5) ────────────────────────────────────────────
#
# Main path:  PENDING → ASSIGNED → ACCEPTED → IN_PROGRESS → SUBMITTED → APPROVED
# Detours:    ASSIGNED → PENDING   (decline / no-show timeout; back to pool)
#             SUBMITTED → REJECTED → IN_PROGRESS   (admin rejects; agent reworks)
# Terminal:   APPROVED (task is done; no further moves).

TASK_TRANSITIONS: Dict[str, Set[str]] = {
    "PENDING": {"ASSIGNED"},
    "ASSIGNED": {"ACCEPTED", "PENDING"},
    "ACCEPTED": {"IN_PROGRESS"},
    "IN_PROGRESS": {"SUBMITTED"},
    "SUBMITTED": {"APPROVED", "REJECTED"},
    "REJECTED": {"IN_PROGRESS"},
}
TASK_TERMINAL: Set[str] = {"APPROVED"}

task_state_machine = StateMachine(
    transitions=TASK_TRANSITIONS,
    terminal=TASK_TERMINAL,
)


# ── Report state machine (PRD §8) ─────────────────────────────────────────
#
# A report is versioned (v1, v2, …). Each dispute-triggered re-check cycle
# produces a new version; the previous version moves to SUPERSEDED.
# Main path:  DRAFT → RELEASED
# Versioning: RELEASED → SUPERSEDED  (when admin releases a newer version)
# Terminal:   SUPERSEDED (frozen; a newer version is the live one).

REPORT_TRANSITIONS: Dict[str, Set[str]] = {
    "DRAFT": {"RELEASED"},
    "RELEASED": {"SUPERSEDED"},
}
REPORT_TERMINAL: Set[str] = {"SUPERSEDED"}

report_state_machine = StateMachine(
    transitions=REPORT_TRANSITIONS,
    terminal=REPORT_TERMINAL,
)
