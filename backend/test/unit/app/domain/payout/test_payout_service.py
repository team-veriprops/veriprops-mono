"""PayoutService — request draws down available; finance approve/hold/reject/cancel (§15.1)."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.events import EventType
from main.app.domain.audit.models import AuditActionType
from main.app.domain.payout import service as payout_module
from main.app.domain.payout.models import (
    PayoutDecisionDto,
    PayoutStatus,
    RequestPayoutDto,
)
from main.app.domain.payout.service import PayoutService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ValidationException,
)


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
def stub_publish(monkeypatch):
    published = []

    async def _pub(event):
        published.append(event)

    monkeypatch.setattr(payout_module, "publish_domain_event", _pub)
    return published


def _payout(pid="p-1", status=PayoutStatus.REQUESTED, agent="a-1", amount=50_000):
    return SimpleNamespace(
        id=pid, agent_id=agent, amount_minor=amount, status=status.value,
        adjustment_minor=0, note=None, decided_at=None, deleted=False,
        bank_name="GT", account_number="0001", account_name="A", requested_at=None,
        sla_due_at=None,
    )


def _make_service(available=100_000):
    svc = object.__new__(PayoutService)
    svc._repo = AsyncMock()
    svc._earnings = AsyncMock()
    svc._banks = AsyncMock()
    svc._audit = MagicMock()
    svc._earnings.available_minor = AsyncMock(return_value=available)
    return svc


class TestRequest:
    async def test_rejects_non_positive(self):
        svc = _make_service()
        with pytest.raises(ValidationException):
            await svc.request("a-1", RequestPayoutDto(amount_minor=0, bank_name="GT",
                                                      account_number="1", account_name="A"))

    async def test_rejects_over_available(self):
        svc = _make_service(available=10_000)
        with pytest.raises(ValidationException):
            await svc.request("a-1", RequestPayoutDto(amount_minor=50_000, bank_name="GT",
                                                      account_number="1", account_name="A"))

    async def test_creates_request_with_sla(self):
        svc = _make_service(available=100_000)
        created = _payout()
        svc._repo.create_return_model = AsyncMock(return_value=created)
        out = await svc.request("a-1", RequestPayoutDto(
            amount_minor=50_000, bank_name="GT", account_number="1", account_name="A"))
        assert out.requested_at is not None
        assert out.sla_due_at is not None
        actions = [c.kwargs["action"] for c in svc._audit.schedule.call_args_list]
        assert AuditActionType.PAYOUT_REQUESTED in actions

    async def test_one_time_requires_full_details(self):
        svc = _make_service(available=100_000)
        with pytest.raises(ValidationException):
            await svc.request("a-1", RequestPayoutDto(amount_minor=10_000, bank_name="GT"))


class TestFinanceDecisions:
    async def test_approve_marks_paid_and_fires_event(self, stub_publish):
        svc = _make_service()
        p = _payout(status=PayoutStatus.REQUESTED)
        svc._repo.get_model = AsyncMock(return_value=p)
        svc._repo.update = AsyncMock()
        await svc.approve("p-1", "fin-1", PayoutDecisionDto())
        _, dto = svc._repo.update.call_args[0]
        assert dto.status == PayoutStatus.PAID.value
        assert stub_publish[0].type == EventType.PAYOUT_APPROVED

    async def test_hold_fires_held_event_with_reason(self, stub_publish):
        svc = _make_service()
        svc._repo.get_model = AsyncMock(return_value=_payout())
        svc._repo.update = AsyncMock()
        await svc.hold("p-1", "fin-1", PayoutDecisionDto(note="verify account"))
        assert stub_publish[0].type == EventType.PAYOUT_HELD
        assert stub_publish[0].data["reason"] == "verify account"

    async def test_cannot_decide_finalised_payout(self):
        svc = _make_service()
        svc._repo.get_model = AsyncMock(return_value=_payout(status=PayoutStatus.PAID))
        with pytest.raises(InvalidResourceStateException):
            await svc.approve("p-1", "fin-1", PayoutDecisionDto())


class TestCancel:
    async def test_owner_cancels_pending(self):
        svc = _make_service()
        svc._repo.get_model = AsyncMock(return_value=_payout(status=PayoutStatus.REQUESTED))
        svc._repo.update = AsyncMock()
        await svc.cancel("a-1", "p-1")
        _, dto = svc._repo.update.call_args[0]
        assert dto.status == PayoutStatus.CANCELLED.value

    async def test_cannot_cancel_non_pending(self):
        svc = _make_service()
        svc._repo.get_model = AsyncMock(return_value=_payout(status=PayoutStatus.PAID))
        with pytest.raises(InvalidResourceStateException):
            await svc.cancel("a-1", "p-1")
