"""Refunds (§8.5, §15): each payment is refunded on its own, and a gateway failure is recoverable.

A verification can hold several settled charges (the initial payment plus re-check or upgrade
charges). Each is claimed, then refunded at the gateway. If the gateway refuses one, that
payment alone goes back to SUCCEEDED, so our record never says "refunded" while the money
stays put. The others stay REFUNDED, the caller learns which failed, and finance can retry
it later from the refunds-to-retry list.
"""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.config.settings import IntegratedPlatform, settings
from main.app.core.state.status import VerificationStatus
from main.app.domain.audit.models import AuditActionType
from main.app.domain.payment.models import PaymentStatus, RefundOutcome
from main.app.domain.payment.service import PaymentService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import InvalidResourceStateException
from main.appodus_utils.integrations.exception.exceptions import IntegrationException


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
    base = dict(
        id=pid, tx_ref=f"ref-{pid}", verification_id="ver-1", customer_id="cust-1",
        status=PaymentStatus.SUCCEEDED.value, provider=IntegratedPlatform.PAYSTACK.value,
        amount_minor=12_000_000, currency="NGN", charge_currency="USD", charge_amount_minor=8_000,
        chargeback_status=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _service(payments, refused=()):
    """*refused*: tx_refs the gateway declines to refund."""
    svc = object.__new__(PaymentService)
    svc._payment_repo = MagicMock()
    svc._verification_service = MagicMock()
    svc._audit = MagicMock()
    rows = {p.id: p for p in payments}

    async def _claim(pid, from_statuses, to_status, **values):
        row = rows[pid]
        if row.status not in {getattr(s, "value", s) for s in from_statuses}:
            return None
        row.status = to_status.value
        return row

    svc._payment_repo.list_for_verification = AsyncMock(return_value=list(payments))
    svc._payment_repo.get_model = AsyncMock(side_effect=lambda pid: rows.get(pid))
    svc._payment_repo.claim_transition = AsyncMock(side_effect=_claim)

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
    async def test_each_settled_charge_is_refunded_at_the_gateway_in_what_was_charged(self, live):
        svc = _service([_payment("p1"), _payment("p2", charge_currency=None, charge_amount_minor=None, amount_minor=500_000)])

        outcome = await svc.refund("ver-1", "admin-1", reason="failed verification")

        assert outcome == RefundOutcome(refunded_minor=12_500_000)
        calls = [c.args for c in svc._gateway.refund_charge.await_args_list]
        assert calls == [("ref-p1", 8_000, "failed verification"), ("ref-p2", 500_000, "failed verification")]
        assert _actions(svc) == [AuditActionType.PAYMENT_REFUNDED, AuditActionType.PAYMENT_REFUNDED]

    async def test_a_refused_refund_puts_only_that_payment_back_and_reports_it(self, live):
        first, second = _payment("p1"), _payment("p2")
        svc = _service([first, second], refused={"ref-p2"})

        outcome = await svc.refund("ver-1", "admin-1", reason="x")

        assert outcome == RefundOutcome(refunded_minor=12_000_000, failed_payment_ids=["p2"])
        assert outcome.held_payment_ids == []
        assert first.status == PaymentStatus.REFUNDED.value
        assert second.status == PaymentStatus.SUCCEEDED.value
        assert _actions(svc) == [AuditActionType.PAYMENT_REFUNDED, AuditActionType.PAYMENT_REFUND_FAILED]

    async def test_a_payment_already_refunded_is_skipped(self, live):
        svc = _service([_payment("p1", status=PaymentStatus.REFUNDED.value), _payment("p2", status=PaymentStatus.FAILED.value)])

        assert await svc.refund("ver-1", "admin-1") == RefundOutcome()
        svc._gateway.refund_charge.assert_not_awaited()

    async def test_the_stub_path_moves_no_money(self, stub):
        svc = _service([_payment("p1", provider=None)])

        outcome = await svc.refund("ver-1", "admin-1")

        assert outcome.refunded_minor == 12_000_000
        svc._gateway.refund_charge.assert_not_awaited()


class TestRetryRefund:
    @pytest.fixture
    def verification_status(self):
        return VerificationStatus.FAILED.value

    def _svc(self, payment, verification_status, refused=()):
        svc = _service([payment], refused=refused)
        svc._verification_service.get_by_id = AsyncMock(return_value=SimpleNamespace(status=verification_status))
        return svc

    @pytest.mark.parametrize("status", [VerificationStatus.FAILED.value, VerificationStatus.REFUNDED.value])
    async def test_finance_retries_a_refund_the_gateway_refused(self, live, status):
        payment = _payment("p1")
        svc = self._svc(payment, status)

        await svc.retry_refund("p1", "finance-1")

        assert payment.status == PaymentStatus.REFUNDED.value
        svc._gateway.refund_charge.assert_awaited_once()

    async def test_a_retry_the_gateway_refuses_again_fails_and_leaves_the_payment_settled(self, live):
        payment = _payment("p1")
        svc = self._svc(payment, VerificationStatus.FAILED.value, refused={"ref-p1"})

        with pytest.raises(IntegrationException):
            await svc.retry_refund("p1", "finance-1")

        assert payment.status == PaymentStatus.SUCCEEDED.value

    async def test_a_payment_whose_verification_was_not_refunded_cannot_be_refunded_here(self, live):
        svc = self._svc(_payment("p1"), VerificationStatus.COMPLETED.value)

        with pytest.raises(InvalidResourceStateException):
            await svc.retry_refund("p1", "finance-1")
        svc._gateway.refund_charge.assert_not_awaited()

    async def test_a_payment_that_is_not_settled_cannot_be_refunded(self, live):
        svc = self._svc(_payment("p1", status=PaymentStatus.REFUNDED.value), VerificationStatus.FAILED.value)

        with pytest.raises(InvalidResourceStateException):
            await svc.retry_refund("p1", "finance-1")


class TestChargebackHold:
    async def test_a_payment_under_a_chargeback_is_held_not_refunded(self, live):
        held = _payment("p1", chargeback_status="FLAGGED")
        svc = _service([held, _payment("p2")])

        outcome = await svc.refund("ver-1", "admin-1")

        assert outcome.held_payment_ids == ["p1"]
        assert outcome.refunded_minor == 12_000_000
        assert held.status == PaymentStatus.SUCCEEDED.value
        assert [c.args[0] for c in svc._gateway.refund_charge.await_args_list] == ["ref-p2"]

    async def test_finance_cannot_retry_a_refund_under_a_chargeback(self, live):
        svc = _service([_payment("p1", chargeback_status="FLAGGED")])
        svc._verification_service.get_by_id = AsyncMock(return_value=SimpleNamespace(status=VerificationStatus.FAILED.value))

        with pytest.raises(InvalidResourceStateException):
            await svc.retry_refund("p1", "finance-1")
        svc._gateway.refund_charge.assert_not_awaited()
