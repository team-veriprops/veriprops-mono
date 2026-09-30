"""FinanceService.summary (§18.1): the Finance landing tiles, unchanged by moving out of the
controller. Pinned to the exact payload the controller used to build from the repos."""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.finance.models import FinanceSummaryDto
from main.app.domain.finance.service import FinanceService
from main.app.domain.payout.models import PayoutStatus
from main.appodus_utils.db.session import db_session_ctx


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


async def test_the_summary_composes_revenue_and_every_count():
    payments, commissions, payouts = MagicMock(), MagicMock(), MagicMock()
    payments.sum_collected_revenue = AsyncMock(return_value=4_500_000)
    payments.count_by_status = AsyncMock(return_value={"SUCCEEDED": 3, "REFUNDED": 1})
    commissions.count_by_status = AsyncMock(return_value={"CLEARING": 2})
    payouts.count_by_status = AsyncMock(return_value={PayoutStatus.REQUESTED.value: 5, "PAID": 1})
    svc = FinanceService(payment_repo=payments, commission_repo=commissions, payout_repo=payouts)

    assert await svc.summary() == FinanceSummaryDto(
        revenue_minor=4_500_000,
        payments_by_status={"SUCCEEDED": 3, "REFUNDED": 1},
        commissions_by_status={"CLEARING": 2},
        payouts_by_status={PayoutStatus.REQUESTED.value: 5, "PAID": 1},
        pending_payouts=5,
    )


async def test_no_requested_payouts_is_zero_pending():
    payments, commissions, payouts = MagicMock(), MagicMock(), MagicMock()
    payments.sum_collected_revenue = AsyncMock(return_value=0)
    payments.count_by_status = AsyncMock(return_value={})
    commissions.count_by_status = AsyncMock(return_value={})
    payouts.count_by_status = AsyncMock(return_value={})

    summary = await FinanceService(payment_repo=payments, commission_repo=commissions, payout_repo=payouts).summary()

    assert summary.pending_payouts == 0
