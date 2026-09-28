"""PayoutService — an agent withdraws to a saved, bank-resolved account, net of the transfer
fee; finance approves, holds, adjusts, rejects, and retries a failed transfer (§15.1).

Approval no longer pays: it queues the payout for the next disbursement (see
`test_payout_disbursement.py`). Every action starts from a fixed set of statuses, and the
DTO lists exactly the actions its payout's status allows, so a screen never offers a move
the backend would refuse.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.config.settings import IntegratedPlatform
from main.app.core.events import EventType
from main.app.domain.audit.models import AuditActionType
from main.app.domain.payout import service as payout_module
from main.app.domain.payout.models import (
    PayoutAction,
    PayoutDecisionDto,
    PayoutStatus,
    QuotePayoutDto,
    RequestPayoutDto,
    admin_payout_to_dto,
    payout_to_dto,
)
from main.app.domain.payout.service import PayoutService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
    ValidationException,
)
from main.appodus_utils.integrations.exception.exceptions import IntegrationException, IntegrationFatalException
from main.appodus_utils.integrations.payment.gateway.models import GatewayTransfer, GatewayTransferStatus
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
    session.execute = AsyncMock()  # the per-agent payout advisory lock
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


@pytest.fixture(autouse=True)
def stub_publish(monkeypatch):
    published = []

    async def _pub(event):
        published.append(event)

    monkeypatch.setattr(payout_module, "publish_domain_event", _pub)
    return published


def _payout(pid="p-1", status=PayoutStatus.REQUESTED, agent="a-1", amount=50_000, fee=1_000, adjustment=0):
    return SimpleNamespace(
        id=pid, agent_id=agent, amount_minor=amount, currency="NGN", status=status.value,
        adjustment_minor=adjustment, fee_minor=fee, note=None, decided_at=None, decided_by=None,
        deleted=False, bank_name="Guaranty Trust Bank", bank_code="058", provider=None,
        account_number="0123456789", account_name="TEST ACCOUNT 6789", requested_at=None,
        sla_due_at=None, failure_reason=None, transfer_reference=None, gateway_transfer_id=None,
        transfer_attempts=0, sent_at=None, settled_at=None, date_created=datetime.now(timezone.utc),
    )


def _account(bank_code="058", provider=None):
    return SimpleNamespace(
        id="ba-1", agent_id="a-1", bank_name="Guaranty Trust Bank", bank_code=bank_code,
        account_number="0123456789", account_name="TEST ACCOUNT 6789", provider=provider, deleted=False,
    )


def _make_service(available=100_000, fee=1_000, account=None):
    svc = object.__new__(PayoutService)
    svc._payout_repo = AsyncMock()
    svc._earnings = AsyncMock()
    svc._banks = AsyncMock()
    svc._banks.get_owned = AsyncMock(return_value=account or _account())
    svc._audit = MagicMock()
    svc._config = AsyncMock()
    svc._config.get_int = AsyncMock(return_value=2)  # PAYOUT_SLA_BUSINESS_DAYS default
    svc._earnings.available_minor = AsyncMock(return_value=available)
    svc._gateways = MagicMock()
    svc._transfers = AsyncMock()
    svc._transfers.quote_fee = AsyncMock(return_value=fee)
    svc._gateways.transfers = MagicMock(return_value=svc._transfers)
    svc._disbursement = AsyncMock()
    # Decisions are claims on the row the test's get_model serves.
    svc._payout_repo.claim_transition = fake_claim_transition(
        lambda _id: svc._payout_repo.get_model.return_value
    )
    svc._payout_repo.create_return_model = AsyncMock(side_effect=lambda dto: _payout(
        amount=dto.amount_minor, fee=dto.fee_minor,
    ))
    return svc


def _request(amount=50_000):
    return RequestPayoutDto(amount_minor=amount, bank_account_id="ba-1")


class TestRequest:
    async def test_rejects_non_positive(self):
        with pytest.raises(ValidationException):
            await _make_service().request("a-1", _request(amount=0))

    async def test_rejects_over_available(self):
        with pytest.raises(ValidationException):
            await _make_service(available=10_000).request("a-1", _request(amount=50_000))

    async def test_a_withdrawal_goes_only_to_the_agents_own_saved_account(self):
        svc = _make_service()
        svc._banks.get_owned = AsyncMock(side_effect=ResourceNotFoundException(resource="bank_account"))

        with pytest.raises(ResourceNotFoundException):
            await svc.request("a-1", _request())
        svc._banks.get_owned.assert_awaited_once_with("a-1", "ba-1")

    async def test_an_account_saved_before_bank_resolution_must_be_added_again(self):
        # It has no bank code, so no gateway could pay it.
        svc = _make_service(account=_account(bank_code=None))

        with pytest.raises(ValidationException):
            await svc.request("a-1", _request())
        svc._payout_repo.create_return_model.assert_not_called()

    async def test_the_fee_is_quoted_by_the_accounts_own_gateway_and_recorded(self):
        svc = _make_service(fee=2_500, account=_account(provider=IntegratedPlatform.PAYSTACK.value))

        out = await svc.request("a-1", _request(amount=50_000))

        svc._gateways.transfers.assert_called_once_with(IntegratedPlatform.PAYSTACK)
        dto = svc._payout_repo.create_return_model.call_args.args[0]
        assert (dto.fee_minor, dto.bank_code, dto.provider) == (2_500, "058", IntegratedPlatform.PAYSTACK.value)
        assert (dto.bank_name, dto.account_number, dto.account_name) == (
            "Guaranty Trust Bank", "0123456789", "TEST ACCOUNT 6789",
        )
        assert payout_to_dto(out).net_minor == 47_500

    async def test_a_withdrawal_the_fee_would_swallow_is_refused(self):
        svc = _make_service(fee=1_000)

        with pytest.raises(ValidationException):
            await svc.request("a-1", _request(amount=1_000))

    async def test_creates_request_with_sla(self):
        svc = _make_service(available=100_000)
        out = await svc.request("a-1", _request())
        assert out.requested_at is not None
        assert out.sla_due_at is not None
        actions = [c.kwargs["action"] for c in svc._audit.schedule.call_args_list]
        assert AuditActionType.PAYOUT_REQUESTED in actions


class TestQuote:
    async def test_the_agent_sees_the_fee_and_what_reaches_their_bank(self):
        svc = _make_service(fee=2_500)

        quote = await svc.quote("a-1", QuotePayoutDto(amount_minor=50_000, bank_account_id="ba-1"))

        assert (quote.amount_minor, quote.fee_minor, quote.net_minor) == (50_000, 2_500, 47_500)

    async def test_a_quote_is_only_for_the_agents_own_account(self):
        svc = _make_service()
        svc._banks.get_owned = AsyncMock(side_effect=ResourceNotFoundException(resource="bank_account"))

        with pytest.raises(ResourceNotFoundException):
            await svc.quote("a-1", QuotePayoutDto(amount_minor=50_000, bank_account_id="ba-9"))


class TestFinanceDecisions:
    async def test_approval_queues_the_payout_for_disbursement(self, stub_publish):
        svc = _make_service()
        p = _payout(status=PayoutStatus.REQUESTED)
        svc._payout_repo.get_model = AsyncMock(return_value=p)

        await svc.approve("p-1", "fin-1", PayoutDecisionDto())

        # Money moves only when the batch runs; approval is finance's word, not the bank's.
        assert p.status == PayoutStatus.APPROVED.value
        assert p.decided_by == "fin-1"
        assert stub_publish[0].type == EventType.PAYOUT_APPROVED

    async def test_hold_fires_held_event_with_reason(self, stub_publish):
        svc = _make_service()
        svc._payout_repo.get_model = AsyncMock(return_value=_payout())
        await svc.hold("p-1", "fin-1", PayoutDecisionDto(note="verify account"))
        assert stub_publish[0].type == EventType.PAYOUT_HELD
        assert stub_publish[0].data["reason"] == "verify account"

    async def test_an_approved_payout_can_be_pulled_back_before_the_batch_runs(self):
        svc = _make_service()
        p = _payout(status=PayoutStatus.APPROVED)
        svc._payout_repo.get_model = AsyncMock(return_value=p)

        await svc.hold("p-1", "fin-1", PayoutDecisionDto(note="query"))

        assert p.status == PayoutStatus.HELD.value

    @pytest.mark.parametrize("status", [PayoutStatus.PROCESSING, PayoutStatus.PAID, PayoutStatus.REJECTED])
    async def test_a_payout_in_flight_or_finished_cannot_be_decided(self, status):
        svc = _make_service()
        svc._payout_repo.get_model = AsyncMock(return_value=_payout(status=status))
        for decide in (svc.approve, svc.hold, svc.reject, svc.adjust):
            with pytest.raises(InvalidResourceStateException):
                await decide("p-1", "fin-1", PayoutDecisionDto(adjustment_minor=0))

    async def test_rejecting_releases_the_funds_and_tells_the_agent(self, stub_publish):
        svc = _make_service()
        p = _payout(status=PayoutStatus.FAILED)
        svc._payout_repo.get_model = AsyncMock(return_value=p)

        await svc.reject("p-1", "fin-1", PayoutDecisionDto(note="account closed"))

        assert p.status == PayoutStatus.REJECTED.value
        assert [e.type for e in stub_publish] == [EventType.PAYOUT_REJECTED]
        assert stub_publish[0].data["reason"] == "account closed"

    @pytest.mark.parametrize("decide", ["approve", "hold"])
    async def test_an_adjustment_carried_by_a_decision_is_checked_against_the_fee_too(self, decide):
        svc = _make_service()
        p = _payout(amount=50_000, fee=1_000)
        svc._payout_repo.get_model = AsyncMock(return_value=p)

        with pytest.raises(ValidationException):
            await getattr(svc, decide)("p-1", "fin-1", PayoutDecisionDto(adjustment_minor=-50_000))
        assert p.status == PayoutStatus.REQUESTED.value

    async def test_a_payout_from_before_bank_resolution_cannot_be_approved(self):
        svc = _make_service()
        p = _payout()
        p.bank_code = None
        svc._payout_repo.get_model = AsyncMock(return_value=p)

        with pytest.raises(ValidationException):
            await svc.approve("p-1", "fin-1", PayoutDecisionDto())
        assert p.status == PayoutStatus.REQUESTED.value
        assert set(admin_payout_to_dto(p).allowed_actions) == {PayoutAction.HOLD, PayoutAction.ADJUST, PayoutAction.REJECT}

    async def test_an_adjustment_the_fee_would_swallow_is_refused(self):
        svc = _make_service()
        p = _payout(amount=50_000, fee=1_000)
        svc._payout_repo.get_model = AsyncMock(return_value=p)

        with pytest.raises(ValidationException):
            await svc.adjust("p-1", "fin-1", PayoutDecisionDto(adjustment_minor=-49_000))
        assert p.adjustment_minor == 0


class TestRetry:
    async def test_a_failed_transfer_goes_back_into_the_next_batch(self):
        svc = _make_service()
        p = _payout(status=PayoutStatus.FAILED)
        p.failure_reason = "Insufficient balance"
        p.transfer_reference = "vp-po-0123456789abcdef0123456789abcdef-1"
        svc._payout_repo.get_model = AsyncMock(return_value=p)
        svc._transfers.get_transfer = AsyncMock(return_value=GatewayTransfer(
            reference=p.transfer_reference, gateway_transfer_id="TRF_1",
            status=GatewayTransferStatus.FAILED, amount_minor=49_000,
        ))

        await svc.retry("p-1", "fin-1")

        assert p.status == PayoutStatus.APPROVED.value
        assert p.failure_reason is None
        actions = [c.kwargs["action"] for c in svc._audit.schedule.call_args_list]
        assert actions == [AuditActionType.PAYOUT_RETRIED]

    async def test_a_retry_is_refused_when_the_last_attempt_actually_went_through(self, stub_publish):
        # The one way a retry could pay twice: the "failed" transfer landed after all.
        svc = _make_service()
        p = _payout(status=PayoutStatus.FAILED)
        p.transfer_reference = "vp-po-0123456789abcdef0123456789abcdef-1"
        svc._payout_repo.get_model = AsyncMock(return_value=p)
        svc._transfers.get_transfer = AsyncMock(return_value=GatewayTransfer(
            reference=p.transfer_reference, gateway_transfer_id="TRF_1",
            status=GatewayTransferStatus.SUCCEEDED, amount_minor=49_000,
        ))
        svc._disbursement = AsyncMock()

        with pytest.raises(InvalidResourceStateException):
            await svc.retry("p-1", "fin-1")

        assert p.status == PayoutStatus.FAILED.value
        svc._disbursement.settle_from_gateway.assert_awaited_once_with(p.transfer_reference)

    @pytest.mark.parametrize("lookup", [
        "pending",
        IntegrationException("unreachable"),
    ])
    async def test_a_retry_waits_until_the_last_attempt_is_known_to_have_failed(self, lookup):
        svc = _make_service()
        p = _payout(status=PayoutStatus.FAILED)
        p.transfer_reference = "vp-po-0123456789abcdef0123456789abcdef-1"
        svc._payout_repo.get_model = AsyncMock(return_value=p)
        svc._transfers.get_transfer = AsyncMock(
            side_effect=lookup if isinstance(lookup, Exception) else None,
            return_value=GatewayTransfer(
                reference=p.transfer_reference, gateway_transfer_id="TRF_1",
                status=GatewayTransferStatus.PENDING, amount_minor=49_000,
            ),
        )

        with pytest.raises(InvalidResourceStateException):
            await svc.retry("p-1", "fin-1")
        assert p.status == PayoutStatus.FAILED.value

    @pytest.mark.parametrize("status", [PayoutStatus.REQUESTED, PayoutStatus.PROCESSING, PayoutStatus.PAID])
    async def test_only_a_failed_transfer_can_be_retried(self, status):
        svc = _make_service()
        svc._payout_repo.get_model = AsyncMock(return_value=_payout(status=status))

        with pytest.raises(InvalidResourceStateException):
            await svc.retry("p-1", "fin-1")


class TestCancel:
    async def test_owner_cancels_pending(self):
        svc = _make_service()
        p = _payout(status=PayoutStatus.REQUESTED)
        svc._payout_repo.get_model = AsyncMock(return_value=p)
        await svc.cancel("a-1", "p-1")
        assert p.status == PayoutStatus.CANCELLED.value

    async def test_cannot_cancel_non_pending(self):
        svc = _make_service()
        svc._payout_repo.get_model = AsyncMock(return_value=_payout(status=PayoutStatus.APPROVED))
        with pytest.raises(InvalidResourceStateException):
            await svc.cancel("a-1", "p-1")


class TestAllowedActions:
    @pytest.mark.parametrize("status, finance, agent", [
        (PayoutStatus.REQUESTED, {PayoutAction.APPROVE, PayoutAction.HOLD, PayoutAction.ADJUST, PayoutAction.REJECT},
         {PayoutAction.CANCEL}),
        (PayoutStatus.HELD, {PayoutAction.APPROVE, PayoutAction.ADJUST, PayoutAction.REJECT}, set()),
        (PayoutStatus.APPROVED, {PayoutAction.HOLD, PayoutAction.ADJUST, PayoutAction.REJECT}, set()),
        (PayoutStatus.PROCESSING, set(), set()),
        (PayoutStatus.FAILED, {PayoutAction.RETRY, PayoutAction.ADJUST, PayoutAction.REJECT}, set()),
        (PayoutStatus.PAID, set(), set()),
        (PayoutStatus.REJECTED, set(), set()),
        (PayoutStatus.CANCELLED, set(), set()),
    ])
    def test_each_audience_sees_only_the_moves_its_status_allows(self, status, finance, agent):
        p = _payout(status=status)
        assert set(admin_payout_to_dto(p).allowed_actions) == finance
        assert set(payout_to_dto(p).allowed_actions) == agent

    def test_the_gateways_own_words_reach_finance_only(self):
        p = _payout(status=PayoutStatus.FAILED)
        p.failure_reason = "DISBURSE FAILED: Insufficient funds"
        assert admin_payout_to_dto(p).failure_reason == p.failure_reason
        assert "failure_reason" not in payout_to_dto(p).model_dump()


class TestQueue:
    async def test_finance_sees_what_waits_and_what_is_still_with_the_bank(self):
        svc = _make_service()
        svc._payout_repo.approved_totals = AsyncMock(return_value=(3, 150_000))
        svc._payout_repo.count_in_status = AsyncMock(return_value=2)

        queue = await svc.disbursement_queue()

        assert (queue.count, queue.total_minor, queue.in_flight) == (3, 150_000, 2)
        svc._payout_repo.count_in_status.assert_awaited_once_with(PayoutStatus.PROCESSING)


class TestUnresolvedAccountAtQuote:
    async def test_live_mode_refuses_to_quote_an_account_no_gateway_resolved(self):
        svc = _make_service()
        svc._gateways.transfers = MagicMock(side_effect=IntegrationFatalException("re-add"))

        with pytest.raises(ValidationException):
            await svc.quote("a-1", QuotePayoutDto(amount_minor=50_000, bank_account_id="ba-1"))
