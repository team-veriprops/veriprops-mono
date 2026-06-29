"""Verification-status derivation owner (PRD §2.5 / §4.1).

`verification.status` is a **projection** of payment state + task states + admin
flags, written by exactly one function. No endpoint sets the global status
inline; every task-mutating handler calls :func:`derive_status` and persists the
result, so there is never a "dashboard says X, admin says Y" disagreement.

`derive_status` is a **pure** function:

    derive_status(current_status, task_states) -> new_status

It applies the §2.5 rules in strict precedence order. ``current_status`` carries
the externally-managed facts the task list cannot express (terminal/dispute
outcomes set by admin, and the pre-payment phase set by the payment flow); the
``task_states`` list carries the work progress.

Dependency-blocked tasks (e.g. a Premium Lawyer task before its siblings reach
``SUBMITTED``) are **not** instantiated as rows until they unlock (§4.2), so they
never appear in ``task_states`` and correctly do not drag the verification into
``UNDER_REVIEW`` early. The "all required tasks" count is owned by
``dependencies.required_task_count`` (tier config), never ``COUNT(tasks)``.
"""
from __future__ import annotations

from typing import Iterable

from main.app.core.state.status import TaskState, VerificationStatus

# States derive.py must never overwrite — they are owned by admin actions
# (terminal + dispute outcomes) rather than by task progress.
_PRESERVED: frozenset[VerificationStatus] = frozenset({
    VerificationStatus.CANCELLED,
    VerificationStatus.REFUNDED,
    VerificationStatus.FAILED,
    VerificationStatus.DISPUTED,
})

# Pre-payment phase is owned by the submission + payment flow; task states are
# irrelevant until payment is confirmed, so these pass through unchanged.
_PRE_PAYMENT: frozenset[VerificationStatus] = frozenset({
    VerificationStatus.DRAFT,
    VerificationStatus.SUBMITTED,
    VerificationStatus.PAYMENT_PENDING,
})

# A task in any of these states means work is actively underway (§2.5 rule 3).
# REJECTED counts as active: the agent must rework, so the verification regresses
# from UNDER_REVIEW back to IN_PROGRESS.
_ACTIVE: frozenset[str] = frozenset({
    TaskState.ASSIGNED.value,
    TaskState.ACCEPTED.value,
    TaskState.IN_PROGRESS.value,
    TaskState.REJECTED.value,
})

# A task is "settled" once it is awaiting or has passed review.
_SETTLED: frozenset[str] = frozenset({
    TaskState.SUBMITTED.value,
    TaskState.APPROVED.value,
})


def _normalize(state) -> str:
    """Accept either a ``TaskState`` enum member or its raw string value."""
    return state.value if isinstance(state, (TaskState, VerificationStatus)) else str(state)


def derive_status(
    current_status: VerificationStatus | str,
    task_states: Iterable[TaskState | str],
) -> VerificationStatus:
    """Return the global verification status derived from ``task_states``.

    Precedence (PRD §2.5):

    1. Preserved states (CANCELLED / REFUNDED / FAILED / DISPUTED) — returned as-is.
    2. Pre-payment states (DRAFT / SUBMITTED / PAYMENT_PENDING) — returned as-is.
    3. Any task ACTIVE (ASSIGNED / ACCEPTED / IN_PROGRESS / REJECTED) → IN_PROGRESS.
    4. Tasks non-empty, all SETTLED, at least one SUBMITTED → UNDER_REVIEW.
    5. Tasks non-empty, all APPROVED → COMPLETED (system stages; admin releases).
    6. Otherwise (no tasks, or all PENDING) → PAID.
    """
    current = VerificationStatus(current_status)
    if current in _PRESERVED:
        return current
    if current in _PRE_PAYMENT:
        return current

    states = [_normalize(s) for s in task_states]

    if any(s in _ACTIVE for s in states):
        return VerificationStatus.IN_PROGRESS

    if states and all(s in _SETTLED for s in states):
        if any(s == TaskState.SUBMITTED.value for s in states):
            return VerificationStatus.UNDER_REVIEW
        return VerificationStatus.COMPLETED  # all APPROVED

    return VerificationStatus.PAID
