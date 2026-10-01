"""Refund requests (§8.5, §18.1): the only path by which a customer's money leaves.

Filing never sends anything. Finance approving claims the request (two approvals refund once),
finishes a closing case, and sends the refund — last. Rejecting sends nothing, needs a reason,
and puts a closing case back to work.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.payment.models import RefundOutcome
from main.app.domain.payment.refund_request.approval import RefundApprovalService
from main.app.domain.payment.refund_request.models import RefundRequestStatus, RefundSource
from main.app.domain.payment.refund_request.service import RefundRequestService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.exception.exceptions import InvalidResourceStateException, ValidationException
from test.utils.repo_fakes import fake_claim_transition


@pytest.fixture(autouse=True)
def mock_db_session():
    session = MagicMock()
    session.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


@pytest.fixture(autouse=True)
def events(monkeypatch):
    import main.app.domain.payment.refund_request.approval as module
    monkeypatch.setattr(module, "publish_domain_event", AsyncMock())


def _request(source=RefundSource.CASE_CLOSURE, status=RefundRequestStatus.PENDING, amount=12_000_000):
    return SimpleNamespace(
        id="req-1", verification_id="ver-1", customer_id="cust-1", source=source.value, status=status.value,
        amount_minor=amount, currency="NGN", reason="DUPLICATE", note="Paid twice", evidence_ref=None, payment_id=None,
        requested_by="ops-1", decided_by=None, decided_at=None, decision_note=None, deleted=False,
        date_created=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )


def _approvals(request, order=None):
    order = order if order is not None else []
    svc = object.__new__(RefundApprovalService)
    svc._repo = MagicMock()
    svc._repo.claim_transition = fake_claim_transition(lambda _id: request)
    svc._requests = MagicMock()
    svc._requests.get = AsyncMock(return_value=request)
    svc._closures = MagicMock()
    svc._closures.finalize = AsyncMock(side_effect=lambda *a, **k: order.append("finalize"))
    svc._closures.lift_hold = AsyncMock(side_effect=lambda *a, **k: order.append("lift"))
    svc._disputes = MagicMock()
    svc._disputes.settle_full_refund = AsyncMock(side_effect=lambda *a, **k: order.append("settle"))
    svc._disputes.reopen_refused_refund = AsyncMock(side_effect=lambda *a, **k: order.append("reopen"))
    svc._payments = MagicMock()
    svc._payments.refund = AsyncMock(side_effect=lambda *a, **k: order.append("refund") or RefundOutcome(refunded_minor=a[1]))
    svc._verifications = MagicMock()
    svc._verifications.get_model = AsyncMock(return_value=SimpleNamespace(vid="VP-1"))
    svc._audit = MagicMock()
    svc._audit.schedule = MagicMock(side_effect=lambda **k: order.append("audit"))
    return svc


class TestApprove:
    async def test_approving_finishes_the_close_then_sends_the_refund_last(self):
        order = []
        request = _request()
        svc = _approvals(request, order)

        decision = await svc.approve("req-1", "finance-1", "Checked with the customer")

        assert request.status == RefundRequestStatus.APPROVED.value
        assert (request.decided_by, request.decision_note) == ("finance-1", "Checked with the customer")
        assert order[0] == "finalize" and order[-1] == "refund"
        assert svc._payments.refund.await_args.args[:3] == ("ver-1", 12_000_000, "finance-1")
        assert decision.outcome.refunded_minor == 12_000_000
        assert decision.request.vid == "VP-1"

    async def test_an_upheld_dispute_settles_as_refunded_then_the_refund_goes_out(self):
        order = []
        svc = _approvals(_request(source=RefundSource.DISPUTE_UPHELD), order)

        await svc.approve("req-1", "finance-1", None)

        assert order.index("settle") < order.index("refund")
        svc._closures.finalize.assert_not_awaited()

    async def test_a_late_charge_refunds_that_charge_and_nothing_else(self):
        request = _request(source=RefundSource.LATE_CHARGE)
        request.payment_id = "pay-late"
        svc = _approvals(request)

        await svc.approve("req-1", "finance-1", None)

        svc._closures.finalize.assert_not_awaited()
        svc._disputes.settle_full_refund.assert_not_awaited()
        assert svc._payments.refund.await_args.kwargs["payment_ids"] == ["pay-late"]

    async def test_a_decided_request_is_never_sent_twice(self):
        svc = _approvals(_request(status=RefundRequestStatus.APPROVED))

        with pytest.raises(InvalidResourceStateException):
            await svc.approve("req-1", "finance-1", None)
        svc._payments.refund.assert_not_awaited()


class TestReject:
    async def test_rejecting_sends_nothing_and_puts_the_case_back_to_work(self):
        request = _request()
        svc = _approvals(request)

        await svc.reject("req-1", "finance-1", "The customer asked to continue")

        assert request.status == RefundRequestStatus.REJECTED.value
        svc._closures.lift_hold.assert_awaited_once()
        svc._payments.refund.assert_not_awaited()

    async def test_rejecting_an_upheld_disputes_refund_reopens_the_dispute(self):
        svc = _approvals(_request(source=RefundSource.DISPUTE_UPHELD))

        await svc.reject("req-1", "finance-1", "Not supported by the evidence")

        svc._disputes.reopen_refused_refund.assert_awaited_once()
        svc._payments.refund.assert_not_awaited()

    @pytest.mark.parametrize("note", [None, "   "])
    async def test_a_rejection_must_say_why(self, note):
        svc = _approvals(_request())

        with pytest.raises(ValidationException):
            await svc.reject("req-1", "finance-1", note)
        svc._closures.lift_hold.assert_not_awaited()


def _requests(pending=None):
    svc = object.__new__(RefundRequestService)
    svc._requests = MagicMock()
    svc._requests.get_pending_for_verification = AsyncMock(return_value=pending)
    svc._requests.create_return_model = AsyncMock(side_effect=lambda dto: SimpleNamespace(id="req-new", **dto.model_dump()))
    if pending is not None:
        svc._requests.claim_transition = fake_claim_transition(lambda _id: pending)
    svc._audit = MagicMock()
    return svc


def _file_kwargs(source=RefundSource.CASE_CLOSURE, amount=5_000_000):
    return dict(verification_id="ver-1", customer_id="cust-1", source=source, amount_minor=amount,
                currency=TransactionCurrency.NGN, requested_by="ops-1")


class TestFile:
    async def test_filing_creates_a_pending_request_and_sends_nothing(self):
        svc = _requests()

        request = await svc.file(**_file_kwargs())

        assert request.status == RefundRequestStatus.PENDING
        assert request.amount_minor == 5_000_000

    async def test_a_second_request_for_a_case_is_refused_while_one_waits(self):
        svc = _requests(pending=_request())

        with pytest.raises(InvalidResourceStateException):
            await svc.file(**_file_kwargs(source=RefundSource.DISPUTE_UPHELD))

    async def test_a_late_charge_is_filed_on_its_own_for_its_own_charge(self):
        """Each late charge is separate money: it never waits behind, or merges into, another."""
        svc = _requests(pending=_request())

        request = await svc.file(**_file_kwargs(source=RefundSource.LATE_CHARGE, amount=3_000_000), payment_id="pay-late")

        assert (request.source, request.payment_id, request.amount_minor) == (RefundSource.LATE_CHARGE, "pay-late", 3_000_000)
