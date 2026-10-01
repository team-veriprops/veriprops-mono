"""The report-review state carries the case's VID and whether it can be closed from there (§6.4):
the review page offers "Close case" only when the backend says the case is paid, unfinished and
not already closing — never by reading the status itself."""
from types import SimpleNamespace

import pytest

from main.app.core.state.status import VerificationStatus, VerificationTier
from main.app.domain.verification.review.controller import _state_dto
from main.app.domain.verification.review.service import ReviewContext


def _ctx(status, closure_reason=None):
    verification = SimpleNamespace(vid="VP-1", status=status.value, closure_reason=closure_reason)
    return ReviewContext(verification=verification, tier=VerificationTier.STANDARD, tasks=[], submissions={},
                         conflicts=[], projected_trust_score=None, all_approved=False, releasable=False, report=None)


@pytest.mark.parametrize("status, closure_reason, can_close", [
    (VerificationStatus.UNDER_REVIEW, None, True),
    (VerificationStatus.IN_PROGRESS, None, True),
    (VerificationStatus.UNDER_REVIEW, "DUPLICATE", False),
    (VerificationStatus.COMPLETED, None, False),
])
def test_close_is_offered_only_on_a_paid_unfinished_case_not_already_closing(status, closure_reason, can_close):
    dto = _state_dto("ver-1", _ctx(status, closure_reason))
    assert (dto.vid, dto.can_close) == ("VP-1", can_close)
