"""§7.3.2's channel states, projected from the real machine (WA-08, D45).

§7.3.2 names ten stages — `enquiry → … → closed`. The backend already has the
authoritative `VerificationStatus` machine, and §7.3.1 requires the bot to read case state
"through the same API endpoints the website dashboard uses". So these ten names are a
**projection**, not a second state machine: no row stores them, nothing transitions
between them, and this module is their only owner. Two machines for one case is the exact
"two surfaces show different statuses" failure §7.3.1 exists to prevent.

Note what this module is *not* for. The words a customer reads come from
`verification/tracking/labels.py`, which the dashboard already uses — the bot must not
invent a second customer-facing vocabulary. These names are the channel's internal stage
vocabulary: what §7.10 counts and what a milestone trigger is described against.
"""
from __future__ import annotations

import enum
from typing import Optional

from main.app.core.state.status import TaskState, VerificationStatus


class ChannelState(str, enum.Enum):
    """The §7.3.2 stage names, verbatim."""

    ENQUIRY = "enquiry"
    INTAKE_IN_PROGRESS = "intake_in_progress"
    INTAKE_COMPLETE = "intake_complete"
    PAYMENT_PENDING = "payment_pending"
    PAID = "paid"
    VERIFYING = "verifying"
    FIELD_INSPECTION = "field_inspection"
    REPORT_READY = "report_ready"
    DELIVERED = "delivered"
    CLOSED = "closed"


# Task states that mean the site visit is under way or done. `PENDING`/`ASSIGNED` are not
# here: an inspector who has been assigned has not yet gone anywhere, and telling a
# customer their inspection is happening when it is not is the kind of small overstatement
# that costs trust when the report lands late.
_FIELD_WORK_STARTED = frozenset(
    {TaskState.ACCEPTED, TaskState.IN_PROGRESS, TaskState.SUBMITTED, TaskState.APPROVED}
)

# Everything that does not depend on the field task. `DISPUTED` projects to `delivered`
# because a dispute is a post-delivery conversation — the report exists and the customer
# has it; what is open is whether it was right.
_BY_STATUS: dict[VerificationStatus, ChannelState] = {
    VerificationStatus.DRAFT: ChannelState.INTAKE_IN_PROGRESS,
    VerificationStatus.SUBMITTED: ChannelState.INTAKE_COMPLETE,
    VerificationStatus.PAYMENT_PENDING: ChannelState.PAYMENT_PENDING,
    VerificationStatus.PAID: ChannelState.PAID,
    VerificationStatus.IN_PROGRESS: ChannelState.VERIFYING,
    # Admin review is where the report exists but has not been released — §7.3.2's
    # `report_ready`, which sits between the inspection and delivery for the same reason.
    VerificationStatus.UNDER_REVIEW: ChannelState.REPORT_READY,
    VerificationStatus.COMPLETED: ChannelState.DELIVERED,
    VerificationStatus.DISPUTED: ChannelState.DELIVERED,
    VerificationStatus.CANCELLED: ChannelState.CLOSED,
    VerificationStatus.REFUNDED: ChannelState.CLOSED,
    VerificationStatus.FAILED: ChannelState.CLOSED,
}


def channel_state(
    status: Optional[VerificationStatus], field_task_state: Optional[TaskState] = None
) -> ChannelState:
    """The §7.3.2 stage for a case.

    ``None`` status is `enquiry` — a conversation with no case behind it yet, which is
    where every WhatsApp customer starts and the one stage that has no row to read.

    ``field_task_state`` refines `verifying` into `field_inspection`, the one stage the
    global status cannot express on its own: the case-level machine says work is under
    way, and only the FIELD task says which work.
    """
    if status is None:
        return ChannelState.ENQUIRY
    projected = _BY_STATUS[VerificationStatus(status)]
    if projected == ChannelState.VERIFYING and field_task_state is not None:
        if TaskState(field_task_state) in _FIELD_WORK_STARTED:
            return ChannelState.FIELD_INSPECTION
    return projected
