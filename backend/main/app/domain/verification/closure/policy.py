"""The PRD refund table (§3 refund & liability model) for closing a paid case: pure functions,
so the quote the admin sees and the close that follows can never compute different amounts."""
from __future__ import annotations

from typing import Optional

from main.app.core.state.status import VerificationStatus
from main.app.domain.verification.closure.models import CloseReason
from main.appodus_utils.exception.exceptions import ValidationException

# Paid and not yet finished: the cases the close flow ends. Before payment there is no money and
# a plain cancel applies; after completion, disputes and re-checks do.
CLOSABLE_STATUSES = (VerificationStatus.PAID, VerificationStatus.IN_PROGRESS, VerificationStatus.UNDER_REVIEW)

# Work has not started while the case is merely PAID (no agent has taken a task).
_BEFORE_WORK = {VerificationStatus.PAID}
_FULL_REFUND = {CloseReason.DUPLICATE, CloseReason.CANNOT_DELIVER}


def closure_refund(
    reason: CloseReason, status: VerificationStatus, refundable_minor: int, *,
    surcharge_pct: int, requested_minor: Optional[int] = None,
) -> int:
    """What closing for *reason* returns to the customer, in minor units."""
    if reason == CloseReason.PROPERTY_INACCESSIBLE:
        if requested_minor is None or not 0 <= requested_minor <= refundable_minor:
            raise ValidationException(
                message="Enter the refund for an inaccessible property: from nothing up to what was paid.",
            )
        return requested_minor
    if requested_minor is not None:
        raise ValidationException(message="Only an inaccessible property takes a refund amount from the admin.")
    if reason in _FULL_REFUND:
        return refundable_minor
    if reason == CloseReason.CUSTOMER_WITHDREW and status in _BEFORE_WORK:
        # The surcharge rounds down, so the customer never loses a fraction of a kobo to it.
        return refundable_minor - refundable_minor * surcharge_pct // 100
    return 0


def closure_status(reason: CloseReason) -> VerificationStatus:
    """How the case ends: FAILED when we could not deliver, CANCELLED otherwise."""
    return VerificationStatus.FAILED if reason == CloseReason.CANNOT_DELIVER else VerificationStatus.CANCELLED


def is_on_hold(verification) -> bool:
    """A paid case waiting for Finance to decide its closing refund: agents cannot move its
    tasks, admins cannot assign it, and the time-based sweeps pass it by."""
    return bool(verification.closure_reason) and verification.status in {s.value for s in CLOSABLE_STATUSES}
