"""The §7.6.2 "verification started" milestone trigger (D66).

Status derivation lives in two places — `VerificationTaskService._derive_and_persist` (a
task moved) and `ReviewService._derive_and_persist` (an admin decided) — because the two
services own different halves of §4.1. Both can be the moment work actually starts, so
both have to publish, and this is the one definition of *when*, so a third caller cannot
invent a fourth answer.

The event is deliberately its own type rather than a subscriber sniffing
`STATUS_CHANGED.data["status"]`: four milestones are four triggers, and reading another
event's payload shape is the coupling the declarative rule table exists to remove.
"""
from __future__ import annotations

from typing import Iterable

from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.core.state.status import TaskState, VerificationStatus
from main.app.domain.verification.models import Verification

# A task that has been submitted or approved is proof work already began. `derive_status`
# has no memory, so a verification passes through IN_PROGRESS once per role — assigning
# the next agent re-activates it after the previous one submitted — and the raw
# transition therefore happens several times per case. Which is right for a status feed
# and wrong for a milestone: §7.6.2 promises the customer three or four messages per
# verification, not one per agent. The presence of a settled task is what distinguishes
# "work has started" from "work is continuing", and it needs no column to record.
_WORK_ALREADY_BEGUN: frozenset[str] = frozenset({
    TaskState.SUBMITTED.value,
    TaskState.APPROVED.value,
})


async def publish_verification_started(
    verification_id: str,
    verification: Verification,
    new_status: VerificationStatus,
    task_states: Iterable[str],
) -> None:
    """Announce that work has begun — once per verification.

    Called from the two derivation sites after they have established that the status
    actually moved. Two guards, and both are needed:

    * the transition must be *into* ``IN_PROGRESS``; and
    * no task may already have been submitted or approved, or this is the second agent
      starting rather than the verification starting.

    ``verification_id`` is passed rather than read off the row because reference ids
    travel as strings while `Verification.id` is a native UUID.
    """
    if new_status is not VerificationStatus.IN_PROGRESS:
        return
    if any(str(state) in _WORK_ALREADY_BEGUN for state in task_states):
        return
    await publish_domain_event(DomainEvent(
        type=EventType.VERIFICATION_STARTED,
        verification_id=verification_id,
        recipient_user_ids=(verification.customer_id,),
        data={"vid": verification.vid},
    ))
