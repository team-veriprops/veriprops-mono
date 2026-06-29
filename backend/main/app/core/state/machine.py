"""Reusable forward-only state-machine validator and authoritative transition tables.

PRD §0.2 (Verification), §5 (Task), §8 (Report).
All domain state machines are defined here so there is one canonical source of truth.
"""
from __future__ import annotations

from typing import Dict, Set

from main.app.core.state.status import ReportState, TaskState, VerificationStatus
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

_V = VerificationStatus
VERIFICATION_TRANSITIONS: Dict[str, Set[str]] = {
    _V.DRAFT: {_V.SUBMITTED, _V.CANCELLED},
    _V.SUBMITTED: {_V.PAYMENT_PENDING, _V.CANCELLED},
    _V.PAYMENT_PENDING: {_V.PAID, _V.CANCELLED, _V.FAILED},
    _V.PAID: {_V.IN_PROGRESS, _V.CANCELLED, _V.REFUNDED, _V.FAILED},
    _V.IN_PROGRESS: {_V.UNDER_REVIEW, _V.FAILED, _V.CANCELLED},
    _V.UNDER_REVIEW: {_V.COMPLETED, _V.IN_PROGRESS, _V.FAILED},
    # COMPLETED → IN_PROGRESS: re-check approved (S44) or tier upgrade (S45)
    _V.COMPLETED: {_V.DISPUTED, _V.IN_PROGRESS},
    # DISPUTED → IN_PROGRESS: partial re-check resolution (S46)
    _V.DISPUTED: {_V.COMPLETED, _V.REFUNDED, _V.IN_PROGRESS},
}
VERIFICATION_TERMINAL: Set[str] = {_V.CANCELLED, _V.REFUNDED, _V.FAILED}

verification_state_machine = StateMachine(
    transitions=VERIFICATION_TRANSITIONS,
    terminal=VERIFICATION_TERMINAL,
)


# ── Task state machine (PRD §5, §8) ──────────────────────────────────────────
#
# Main path:  PENDING → ASSIGNED → ACCEPTED → IN_PROGRESS → SUBMITTED → APPROVED
# Detours:    ASSIGNED → PENDING   (decline / no-show timeout; back to pool)
#             SUBMITTED → REJECTED → IN_PROGRESS   (admin rejects; agent reworks)
#             APPROVED  → IN_PROGRESS               (admin reopens an approved task)
# Terminal:   none — admin reopen keeps APPROVED non-terminal so it can be walked back.

_T = TaskState
TASK_TRANSITIONS: Dict[str, Set[str]] = {
    # Pool path: agent accepts from the open pool (PENDING → ACCEPTED directly).
    # Admin-assign path: admin assigns to a specific agent (PENDING → ASSIGNED → ACCEPTED).
    _T.PENDING: {_T.ASSIGNED, _T.ACCEPTED},
    _T.ASSIGNED: {_T.ACCEPTED, _T.PENDING},
    _T.ACCEPTED: {_T.IN_PROGRESS, _T.PENDING},  # PENDING = agent declines after accepting
    _T.IN_PROGRESS: {_T.SUBMITTED},
    _T.SUBMITTED: {_T.APPROVED, _T.REJECTED},
    _T.REJECTED: {_T.IN_PROGRESS},
    _T.APPROVED: {_T.IN_PROGRESS},  # admin reopen path
}
TASK_TERMINAL: Set[str] = set()  # APPROVED is no longer terminal; verification state machine governs completion

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

_R = ReportState
REPORT_TRANSITIONS: Dict[str, Set[str]] = {
    _R.DRAFT: {_R.RELEASED},
    _R.RELEASED: {_R.SUPERSEDED},
}
REPORT_TERMINAL: Set[str] = {_R.SUPERSEDED}

report_state_machine = StateMachine(
    transitions=REPORT_TRANSITIONS,
    terminal=REPORT_TERMINAL,
)
