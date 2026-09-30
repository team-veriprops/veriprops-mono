"""The refund a closure owes (PRD §3 refund & liability model), as one pure function.

The admin picks why a paid case is closing; the backend — never the admin, never the browser —
works out what goes back, from the PRD's table: a customer who withdraws before work starts
gets the payment less the configured surcharge, and nothing once work has started; a duplicate
or a case we cannot deliver is refunded in full; fraud gets nothing; an inaccessible property
gets the amount the admin enters on the evidence, never more than was paid.
"""
import pytest

from main.app.core.state.status import VerificationStatus
from main.app.domain.verification.closure.models import CloseReason
from main.app.domain.verification.closure.policy import closure_refund, closure_status
from main.appodus_utils.exception.exceptions import ValidationException

PAID = 15_000_000


class TestRefund:
    def test_a_withdrawal_before_work_starts_refunds_less_the_surcharge(self):
        assert closure_refund(CloseReason.CUSTOMER_WITHDREW, VerificationStatus.PAID, PAID, surcharge_pct=20) == 12_000_000

    @pytest.mark.parametrize("status", [VerificationStatus.IN_PROGRESS, VerificationStatus.UNDER_REVIEW])
    def test_a_withdrawal_after_work_started_refunds_nothing(self, status):
        assert closure_refund(CloseReason.CUSTOMER_WITHDREW, status, PAID, surcharge_pct=20) == 0

    @pytest.mark.parametrize("reason", [CloseReason.DUPLICATE, CloseReason.CANNOT_DELIVER])
    def test_a_duplicate_or_our_failure_refunds_in_full(self, reason):
        assert closure_refund(reason, VerificationStatus.IN_PROGRESS, PAID, surcharge_pct=20) == PAID

    def test_fraud_refunds_nothing(self):
        assert closure_refund(CloseReason.FRAUD, VerificationStatus.PAID, PAID, surcharge_pct=20) == 0

    def test_an_inaccessible_property_refunds_what_the_admin_entered(self):
        assert closure_refund(
            CloseReason.PROPERTY_INACCESSIBLE, VerificationStatus.IN_PROGRESS, PAID, surcharge_pct=20,
            requested_minor=5_000_000,
        ) == 5_000_000

    @pytest.mark.parametrize("requested", [None, -1, PAID + 1])
    def test_an_inaccessible_property_needs_an_amount_within_what_was_paid(self, requested):
        with pytest.raises(ValidationException):
            closure_refund(CloseReason.PROPERTY_INACCESSIBLE, VerificationStatus.IN_PROGRESS, PAID,
                           surcharge_pct=20, requested_minor=requested)

    def test_only_an_inaccessible_property_takes_an_admin_amount(self):
        with pytest.raises(ValidationException):
            closure_refund(CloseReason.DUPLICATE, VerificationStatus.PAID, PAID, surcharge_pct=20,
                           requested_minor=1_000)

    def test_the_surcharge_rounds_to_the_kobo_in_the_customers_favour(self):
        assert closure_refund(CloseReason.CUSTOMER_WITHDREW, VerificationStatus.PAID, 333, surcharge_pct=20) == 267


class TestStatus:
    def test_our_failure_to_deliver_ends_as_failed(self):
        assert closure_status(CloseReason.CANNOT_DELIVER) == VerificationStatus.FAILED

    @pytest.mark.parametrize("reason", [r for r in CloseReason if r != CloseReason.CANNOT_DELIVER])
    def test_every_other_reason_ends_as_cancelled(self, reason):
        assert closure_status(reason) == VerificationStatus.CANCELLED
