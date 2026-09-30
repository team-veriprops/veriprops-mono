"""Refunds (§8.5, §15): an approved amount goes back, charge by charge, and a refusal is recoverable.

Only an approved refund request reaches here (refund_request/): the amount Finance approved is
spread across the case's settled charges, oldest first. Each charge is claimed, then refunded at
its gateway in the currency it was charged in — part of a charge when the amount is less. A
charge the gateway refuses goes back to SUCCEEDED still owing what it was asked for
(`refund_due_minor`), which is what Finance's refunds-to-retry list shows and a retry sends. A
charge under a chargeback is held: the issuer is already returning that money.
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.config.settings import IntegratedPlatform, settings
from main.app.domain.audit.models import AuditActionType
from main.app.domain.payment.models import PaymentStatus, RefundOutcome
from main.app.domain.payment.service import PaymentService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import InvalidResourceStateException, ValidationException
from main.appodus_utils.integrations.exception.exceptions import IntegrationException
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


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_STUB_MODE", False)


@pytest.fixture
def stub(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_STUB_MODE", True)


def _payment(pid, **over):
    """₦120,000 contractual, charged as $80.00 (8,000 cents)."""
    base = dict(
        id=pid, tx_ref=f"ref-{pid}", verification_id="ver-1", customer_id="cust-1",
        status=PaymentStatus.SUCCEEDED.value, provider=IntegratedPlatform.PAYSTACK.value,
        amount_minor=12_000_000, currency="NGN", charge_currency="USD", charge_amount_minor=8_000,
        chargeback_status=None, refunded_amount_minor=None, refund_due_minor=None, deleted=False,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _service(payments, refused=()):
    """*refused*: tx_refs the gateway declines to refund."""
    svc = object.__new__(PaymentService)
    svc._payment_repo = MagicMock()
    svc._audit = MagicMock()
    rows = {p.id: p for p in payments}

    svc._payment_repo.list_for_verification = AsyncMock(return_value=list(payments))
    svc._payment_repo.get_model = AsyncMock(side_effect=lambda pid: rows.get(pid))
    svc._payment_repo.claim_transition = fake_claim_transition(rows)

    async def _refund(reference, amount_minor, reason):
        if reference in refused:
            raise IntegrationException("Could not refund the payment: the payment gateway declined the request.")

    gateway = MagicMock()
    gateway.refund_charge = AsyncMock(side_effect=_refund)
    svc._gateways = MagicMock()
    svc._gateways.for_platform = MagicMock(return_value=gateway)
    svc._gateway = gateway
    return svc


def _actions(svc):
    return [c.kwargs["action"] for c in svc._audit.schedule.call_args_list]


class TestRefund:
    async def test_the_full_amount_refunds_every_charge_in_what_it_was_charged(self, live):
        first = _payment("p1")
        second = _payment("p2", charge_currency=None, charge_amount_minor=None, amount_minor=500_000)
        svc = _service([first, second])

        outcome = await svc.refund("ver-1", 12_500_000, "finance-1", reason="closed: duplicate")

        assert outcome == RefundOutcome(refunded_minor=12_500_000)
        calls = [c.args for c in svc._gateway.refund_charge.await_args_list]
        assert calls == [("ref-p1", 8_000, "closed: duplicate"), ("ref-p2", 500_000, "closed: duplicate")]
        assert (first.status, first.refunded_amount_minor) == (PaymentStatus.REFUNDED.value, 12_000_000)
        assert _actions(svc) == [AuditActionType.PAYMENT_REFUNDED, AuditActionType.PAYMENT_REFUNDED]

    async def test_a_partial_amount_refunds_part_of_a_charge_in_its_own_currency(self, live):
        """A withdrawal less the surcharge: 80% of ₦120,000 goes back as 80% of $80.00."""
        payment = _payment("p1")
        svc = _service([payment])

        outcome = await svc.refund("ver-1", 9_600_000, "finance-1", reason="withdrawn")

        assert outcome.refunded_minor == 9_600_000
        assert svc._gateway.refund_charge.await_args.args == ("ref-p1", 6_400, "withdrawn")
        assert (payment.status, payment.refunded_amount_minor, payment.refund_due_minor) == (
            PaymentStatus.REFUNDED.value, 9_600_000, None,
        )

    async def test_the_amount_is_spread_oldest_charge_first(self, live):
        first = _payment("p1", charge_currency=None, charge_amount_minor=None)
        second = _payment("p2", charge_currency=None, charge_amount_minor=None, amount_minor=5_000_000)
        svc = _service([first, second])

        await svc.refund("ver-1", 13_000_000, "finance-1")

        calls = [c.args[:2] for c in svc._gateway.refund_charge.await_args_list]
        assert calls == [("ref-p1", 12_000_000), ("ref-p2", 1_000_000)]

    async def test_a_refused_charge_goes_back_still_owing_what_it_was_asked_for(self, live):
        first, second = _payment("p1"), _payment("p2")
        svc = _service([first, second], refused={"ref-p2"})

        outcome = await svc.refund("ver-1", 24_000_000, "finance-1", reason="x")

        assert outcome == RefundOutcome(refunded_minor=12_000_000, failed_payment_ids=["p2"])
        assert first.status == PaymentStatus.REFUNDED.value
        assert (second.status, second.refund_due_minor, second.refunded_amount_minor) == (
            PaymentStatus.SUCCEEDED.value, 12_000_000, None,
        )
        assert _actions(svc) == [AuditActionType.PAYMENT_REFUNDED, AuditActionType.PAYMENT_REFUND_FAILED]

    async def test_more_than_is_refundable_is_refused_before_anything_moves(self, live):
        svc = _service([_payment("p1")])

        with pytest.raises(ValidationException):
            await svc.refund("ver-1", 12_000_001, "finance-1")
        svc._gateway.refund_charge.assert_not_awaited()

    async def test_charges_already_refunded_or_failed_are_not_touched(self, live):
        svc = _service([_payment("p1", status=PaymentStatus.REFUNDED.value), _payment("p2", status=PaymentStatus.FAILED.value)])

        assert await svc.refund("ver-1", 0, "finance-1") == RefundOutcome()
        svc._gateway.refund_charge.assert_not_awaited()

    async def test_the_stub_path_moves_no_money(self, stub):
        payment = _payment("p1", provider=None)
        svc = _service([payment])

        outcome = await svc.refund("ver-1", 12_000_000, "finance-1")

        assert outcome.refunded_minor == 12_000_000
        assert payment.status == PaymentStatus.REFUNDED.value
        svc._gateway.refund_charge.assert_not_awaited()


class TestWhatIsOwedAlready:
    async def test_a_refund_can_be_limited_to_its_own_charge(self, live):
        """A late charge's refund returns that charge, never the case's older one."""
        old, late = _payment("p1"), _payment("p2", amount_minor=5_000_000, charge_currency=None, charge_amount_minor=None)
        svc = _service([old, late])

        await svc.refund("ver-1", 5_000_000, "finance-1", payment_ids=["p2"])

        assert [c.args[0] for c in svc._gateway.refund_charge.await_args_list] == ["ref-p2"]
        assert old.status == PaymentStatus.SUCCEEDED.value

    async def test_a_charge_already_owing_a_refund_is_not_refunded_again(self, live):
        """It waits for Finance's retry of exactly what it owes; a new refund must not take it
        and wipe the debt."""
        owed, fresh = _payment("p1", refund_due_minor=12_000_000), _payment("p2")
        svc = _service([owed, fresh])

        assert await svc.refundable_minor("ver-1") == 12_000_000
        await svc.refund("ver-1", 12_000_000, "finance-1")

        assert [c.args[0] for c in svc._gateway.refund_charge.await_args_list] == ["ref-p2"]
        assert owed.refund_due_minor == 12_000_000


class TestRetryRefund:
    async def test_finance_retries_exactly_what_the_charge_still_owes(self, live):
        payment = _payment("p1", refund_due_minor=9_600_000)
        svc = _service([payment])

        await svc.retry_refund("p1", "finance-1")

        assert svc._gateway.refund_charge.await_args.args[:2] == ("ref-p1", 6_400)
        assert (payment.status, payment.refunded_amount_minor, payment.refund_due_minor) == (
            PaymentStatus.REFUNDED.value, 9_600_000, None,
        )

    async def test_a_retry_the_gateway_refuses_again_fails_and_keeps_the_debt(self, live):
        payment = _payment("p1", refund_due_minor=12_000_000)
        svc = _service([payment], refused={"ref-p1"})

        with pytest.raises(IntegrationException):
            await svc.retry_refund("p1", "finance-1")

        assert (payment.status, payment.refund_due_minor) == (PaymentStatus.SUCCEEDED.value, 12_000_000)

    async def test_a_charge_that_owes_nothing_cannot_be_refunded_here(self, live):
        """Only an approved request sends money: a retry resends an approved one, never starts one."""
        svc = _service([_payment("p1")])

        with pytest.raises(InvalidResourceStateException):
            await svc.retry_refund("p1", "finance-1")
        svc._gateway.refund_charge.assert_not_awaited()


class TestChargebackHold:
    async def test_a_charge_under_a_chargeback_is_held_and_the_rest_is_refunded(self, live):
        held = _payment("p1", chargeback_status="FLAGGED")
        svc = _service([held, _payment("p2")])

        outcome = await svc.refund("ver-1", 12_000_000, "finance-1")

        assert outcome.held_payment_ids == ["p1"]
        assert outcome.refunded_minor == 12_000_000
        assert held.status == PaymentStatus.SUCCEEDED.value
        assert [c.args[0] for c in svc._gateway.refund_charge.await_args_list] == ["ref-p2"]

    async def test_finance_cannot_retry_a_refund_under_a_chargeback(self, live):
        svc = _service([_payment("p1", chargeback_status="FLAGGED", refund_due_minor=12_000_000)])

        with pytest.raises(InvalidResourceStateException):
            await svc.retry_refund("p1", "finance-1")
        svc._gateway.refund_charge.assert_not_awaited()


class TestRefundable:
    async def test_it_is_what_a_refund_could_send_back_now(self):
        """Settled charges not under a chargeback — what a close can refund at most."""
        svc = _service([
            _payment("p1"),
            _payment("p2", amount_minor=3_000_000),
            _payment("p3", chargeback_status="FLAGGED"),
            _payment("p4", status=PaymentStatus.REFUNDED.value),
            _payment("p5", status=PaymentStatus.INITIATED.value),
        ])

        assert await svc.refundable_minor("ver-1") == 15_000_000

    async def test_an_unpaid_case_has_nothing_to_refund(self):
        assert await _service([]).refundable_minor("ver-1") == 0
