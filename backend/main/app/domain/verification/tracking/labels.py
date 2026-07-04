"""Customer-facing label projection (PRD §9.2) — backend is the source of truth.

The customer never sees raw internal enum values; these pure maps translate the
verification status, the collapsed per-task state, and the SLA health into the exact
plain-English strings the tracking dashboard renders. Kept server-side so the frontend
derives no facts (CLAUDE.md).
"""
from __future__ import annotations

from typing import Optional

from main.app.core.sla import SlaHealth
from main.app.core.state.status import AgentRole, TaskState, VerificationStatus

# §9.2 global status → customer-visible label.
_STATUS_LABELS = {
    VerificationStatus.DRAFT: "Draft",
    VerificationStatus.SUBMITTED: "Submitted",
    VerificationStatus.PAYMENT_PENDING: "Awaiting Payment",
    VerificationStatus.PAID: "Payment Confirmed — Agents Being Assigned",
    VerificationStatus.IN_PROGRESS: "Verification In Progress",
    VerificationStatus.UNDER_REVIEW: "Under Review",
    VerificationStatus.COMPLETED: "Completed ✅",
    VerificationStatus.DISPUTED: "Dispute Under Review",
    VerificationStatus.CANCELLED: "Cancelled",
    VerificationStatus.FAILED: "Could Not Be Completed",
    VerificationStatus.REFUNDED: "Refunded",
}

# §9.2 per-task state collapse — the customer sees three states, not seven.
_TASK_PENDING = "Pending"
_TASK_IN_PROGRESS = "In Progress"
_TASK_COMPLETED = "Completed"
# The dependency-blocked Lawyer row before its upstream siblings submit (§9.2).
LAWYER_AWAITING_LABEL = "Awaiting other stages"

_TASK_LABELS = {
    TaskState.PENDING: _TASK_PENDING,
    TaskState.ASSIGNED: _TASK_PENDING,
    TaskState.ACCEPTED: _TASK_PENDING,
    TaskState.IN_PROGRESS: _TASK_IN_PROGRESS,
    TaskState.SUBMITTED: _TASK_IN_PROGRESS,
    TaskState.REJECTED: _TASK_IN_PROGRESS,
    TaskState.APPROVED: _TASK_COMPLETED,
}

# Admin SLA health → the customer-facing three-state SLA wording (§9.1).
_SLA_LABELS = {
    SlaHealth.ON_TRACK: "On track",
    SlaHealth.AT_RISK: "Running late",
    SlaHealth.OVERDUE: "Delayed",
    SlaHealth.NONE: None,
}


def customer_status_label(status: VerificationStatus) -> str:
    """Plain-English label for the global verification status (§9.2)."""
    return _STATUS_LABELS[VerificationStatus(status)]


def customer_task_state(state: TaskState) -> str:
    """Collapsed customer-facing task state (§9.2): Pending / In Progress / Completed."""
    return _TASK_LABELS[TaskState(state)]


def customer_sla_label(health: SlaHealth) -> Optional[str]:
    """On track / Running late / Delayed — or None when no SLA clock is active (§9.1)."""
    return _SLA_LABELS[SlaHealth(health)]


# §9.3 interim reassurance — per-role positive milestone copy, framed **provisionally**
# ("so far, no issues found at this stage") so a later adverse final finding never reads
# as a bait-and-switch. Surfaced only after admin review-approval.
_INTERIM_MESSAGES = {
    AgentRole.REGISTRY: "Registry & title check complete — so far, no issues found at this stage.",
    AgentRole.FIELD: "Physical inspection complete — so far, no issues found at this stage.",
    AgentRole.SURVEYOR: "Boundary & survey check complete — so far, no issues found at this stage.",
    AgentRole.LAWYER: "Legal review complete — so far, no issues found at this stage.",
}


def interim_message(role: AgentRole) -> str:
    """Provisional positive interim reassurance copy for an approved role (§9.3)."""
    return _INTERIM_MESSAGES[AgentRole(role)]
