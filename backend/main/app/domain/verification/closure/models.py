"""Closing a paid case (PRD §3 refund & liability model, §6.4, §8.5).

After payment a case has one way out: an admin closes it with a reason, and the reason — read
through the PRD's refund table (policy.py) — decides what the customer gets back and how the
case ends. When money is to go back, the case goes **on hold** first: agents are told to stop
and cannot move their tasks, the time-based sweeps leave it alone, and a refund request waits
for Finance (payment/refund_request/). Finance approving closes it for good — submitted work is
paid, every other task is cancelled, the refund goes out; Finance rejecting lifts the hold and
the work resumes. A close that returns nothing ends the case at once.
"""
from __future__ import annotations

import enum
from typing import List, Optional

from pydantic import Field

from main.app.core.state.status import AgentRole, TaskState, VerificationStatus
from main.appodus_utils import Object
from main.appodus_utils.db.types.money import TransactionCurrency


class CloseReason(str, enum.Enum):
    """Why a paid case is closing: the row of the PRD refund table it falls under."""

    CUSTOMER_WITHDREW = "CUSTOMER_WITHDREW"          # the customer asked to stop
    DUPLICATE = "DUPLICATE"                          # paid or submitted twice for one property
    CANNOT_DELIVER = "CANNOT_DELIVER"                # our failure: no coverage, never activated
    FRAUD = "FRAUD"                                  # a fraudulent customer submission
    PROPERTY_INACCESSIBLE = "PROPERTY_INACCESSIBLE"  # external: the agent could not get in


class CloseCaseDto(Object):
    reason: CloseReason
    # Recorded on the case, the audit trail and Finance's request: why, in the admin's words.
    note: str = Field(..., min_length=5, max_length=1000)
    # PROPERTY_INACCESSIBLE only: the refund the admin sets on the evidence, and that evidence.
    amount_minor: Optional[int] = None
    evidence_ref: Optional[str] = Field(None, max_length=255)


class ClosureAgentImpactDto(Object):
    """What closing does to one agent's task."""

    task_id: str
    role: AgentRole
    agent_id: Optional[str] = None
    state: TaskState
    # Submitted work is paid its role's fixed commission; anything else is cancelled unpaid.
    paid: bool


class ClosureQuoteDto(Object):
    """What closing would do, computed by the backend, confirmed by the admin."""

    reason: CloseReason
    # The contractual currency every amount here is in (the case's own).
    currency: TransactionCurrency
    refundable_minor: int
    refund_minor: int
    resulting_status: VerificationStatus
    # True when money is to go back: the case waits on hold for Finance's approval.
    requires_approval: bool
    agents: List[ClosureAgentImpactDto] = []


class ClosureResultDto(Object):
    status: VerificationStatus
    on_hold: bool
    refund_minor: int
    currency: TransactionCurrency
    refund_request_id: Optional[str] = None
