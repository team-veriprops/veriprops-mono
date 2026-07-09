"""EarningsService — summary aggregation + the clearance/reserve sweep (§15.2)."""
from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.events import EventType
from main.app.domain.commission.models import CommissionStatus
from main.app.domain.earnings import service as earnings_module
from main.app.domain.earnings.service import EarningsService
from main.app.domain.payout.models import PayoutStatus
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx

NOW = Utils.datetime_now()
PAST = NOW - timedelta(days=1)


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

    monkeypatch.setattr(earnings_module, "publish_domain_event", _pub)
    return published


def _commission(cid, status=CommissionStatus.CLEARING, amount=100_000, reserve=10_000,
                clearing_until=PAST, reserve_until=PAST, reserve_released_at=None, agent="a-1"):
    return SimpleNamespace(
        id=cid, verification_id="v-1", agent_id=agent, role="REGISTRY", tier="BASIC",
        status=status.value, amount_minor=amount, reserve_amount_minor=reserve,
        clearing_until=clearing_until, reserve_until=reserve_until,
        reserve_released_at=reserve_released_at, date_created=NOW,
    )


def _payout(status=PayoutStatus.PAID, amount=50_000, adjustment=0):
    return SimpleNamespace(status=status.value, amount_minor=amount, adjustment_minor=adjustment)


def _make_service():
    svc = object.__new__(EarningsService)
    svc._commissions = AsyncMock()
    svc._payouts = AsyncMock()
    return svc


class TestSummary:
    async def test_summary_nets_paid_and_pending(self):
        svc = _make_service()
        svc._commissions.list_for_agent = AsyncMock(return_value=[
            _commission("c-1", status=CommissionStatus.AVAILABLE, reserve_released_at=PAST),
        ])
        svc._payouts.list_for_agent = AsyncMock(return_value=[
            _payout(PayoutStatus.PAID, 30_000),
            _payout(PayoutStatus.REQUESTED, 20_000),  # locks
        ])
        summary = await svc.summary("a-1")
        assert summary.available_minor == 50_000  # 100k − 30k paid − 20k pending
        assert summary.total_paid_minor == 30_000
        assert summary.pending_payout_minor == 20_000


class TestSweep:
    async def test_pass1_flips_clearing_to_available(self):
        svc = _make_service()
        c = _commission("c-1", status=CommissionStatus.CLEARING)
        svc._commissions.list_clearing_due = AsyncMock(return_value=[c])
        svc._commissions.list_reserve_due = AsyncMock(return_value=[])
        svc._commissions.update = AsyncMock()
        advanced = await svc.sweep_cleared()
        assert advanced == 1
        _, dto = svc._commissions.update.call_args[0]
        assert dto.status == CommissionStatus.AVAILABLE.value

    async def test_pass2_releases_reserve_once(self):
        svc = _make_service()
        row = _commission("c-1", status=CommissionStatus.AVAILABLE, reserve_released_at=None)
        svc._commissions.list_clearing_due = AsyncMock(return_value=[])
        svc._commissions.list_reserve_due = AsyncMock(return_value=[row])
        svc._commissions.get_model = AsyncMock(return_value=row)
        advanced = await svc.sweep_cleared()
        assert advanced == 1
        assert row.reserve_released_at is not None

    async def test_notifies_once_per_agent(self, stub_publish):
        svc = _make_service()
        svc._commissions.list_clearing_due = AsyncMock(return_value=[
            _commission("c-1", agent="a-1"), _commission("c-2", agent="a-1"),
        ])
        svc._commissions.list_reserve_due = AsyncMock(return_value=[])
        svc._commissions.update = AsyncMock()
        await svc.sweep_cleared()
        assert len(stub_publish) == 1  # deduped per agent
        assert stub_publish[0].type == EventType.COMMISSION_CLEARED

    async def test_sweep_idempotent_when_nothing_due(self):
        svc = _make_service()
        svc._commissions.list_clearing_due = AsyncMock(return_value=[])
        svc._commissions.list_reserve_due = AsyncMock(return_value=[])
        assert await svc.sweep_cleared() == 0
