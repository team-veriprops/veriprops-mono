"""Derived global state rules — PRD §0.3.

Verification status is derived from task states, not set by human click.
Rules are evaluated in priority order; the first match wins.
"""
from main.app.domain.verification.models import VerificationStatus
from main.app.state.machine import VERIFICATION_TERMINAL

_ACTIVE_TASK_STATES = {"ASSIGNED", "ACCEPTED", "IN_PROGRESS", "REJECTED"}
_SETTLED_TASK_STATES = {"SUBMITTED", "APPROVED"}

_DERIVABLE_STATES = {
    VerificationStatus.PAID,
    VerificationStatus.IN_PROGRESS,
    VerificationStatus.UNDER_REVIEW,
    VerificationStatus.COMPLETED,
}


def derive_status(
    current: VerificationStatus,
    task_statuses: list[str],
) -> VerificationStatus:
    """Return the verification status implied by *task_statuses*.

    Args:
        current: The verification's current status.
        task_statuses: String values of all TaskStatus entries for the verification.

    Returns:
        The derived status. Returns *current* unchanged when no rule fires.
    """
    # Rules 1–2: preserve terminal and externally-managed states.
    if current.value in VERIFICATION_TERMINAL:
        return current
    if current == VerificationStatus.DISPUTED:
        return current

    # Rule 3: pre-payment states are not task-derived.
    if current not in _DERIVABLE_STATES:
        return current

    # Rule 4: payment confirmed but no tasks assigned yet.
    if not task_statuses or all(s == "PENDING" for s in task_statuses):
        return VerificationStatus.PAID

    # Rule 5: ≥1 active task (ASSIGNED / ACCEPTED / IN_PROGRESS / REJECTED).
    # Also subsumes §0.3 rule 6: a REJECTED task from UNDER_REVIEW fires IN_PROGRESS.
    if any(s in _ACTIVE_TASK_STATES for s in task_statuses):
        return VerificationStatus.IN_PROGRESS

    # Rule 6: all tasks settled (SUBMITTED or APPROVED), ≥1 still SUBMITTED.
    if all(s in _SETTLED_TASK_STATES for s in task_statuses) and any(
        s == "SUBMITTED" for s in task_statuses
    ):
        return VerificationStatus.UNDER_REVIEW

    # Rule 7: all tasks APPROVED.
    if task_statuses and all(s == "APPROVED" for s in task_statuses):
        return VerificationStatus.COMPLETED

    return current
