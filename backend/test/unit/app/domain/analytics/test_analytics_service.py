"""AnalyticsService (§18.1, D38) — pure aggregation over mocked repo pulls."""
from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from main.app.core.state.status import VerificationStatus, VerificationTier
from main.app.domain.analytics.service import AnalyticsService
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx

V1, V2, V3 = UUID(int=1), UUID(int=2), UUID(int=3)


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


def _row(vid, tier, status, paid=True, state="Lagos", days=3):
    now = Utils.datetime_now()
    return {
        "id": vid, "tier": tier.value if tier else None, "status": status.value,
        "paid_at": now - timedelta(days=days) if paid else None,
        "updated": now, "state": state,
    }


def _make_service():
    svc = object.__new__(AnalyticsService)
    svc._verifications = AsyncMock()
    svc._payments = AsyncMock()
    svc._tasks = AsyncMock()
    svc._reports = AsyncMock()
    return svc


class TestFunnel:
    async def test_counts_each_stage(self):
        svc = _make_service()
        svc._verifications.analytics_snapshot = AsyncMock(return_value=[
            _row(V1, VerificationTier.BASIC, VerificationStatus.COMPLETED),
            _row(V2, VerificationTier.STANDARD, VerificationStatus.PAID),
            _row(V3, None, VerificationStatus.DRAFT, paid=False),
        ])
        funnel = await svc.funnel()
        assert funnel.created == 3
        assert funnel.submitted == 2   # not DRAFT
        assert funnel.paid == 2
        assert funnel.completed == 1
        assert 0.0 < funnel.completion_rate <= 1.0


class TestTimeByTier:
    async def test_avg_days_for_completed(self):
        svc = _make_service()
        svc._verifications.analytics_snapshot = AsyncMock(return_value=[
            _row(V1, VerificationTier.BASIC, VerificationStatus.COMPLETED, days=4),
        ])
        rows = await svc.time_by_tier()
        basic = next(r for r in rows if r.tier == VerificationTier.BASIC)
        assert basic.completed_count == 1
        assert 3.5 <= basic.avg_days <= 4.5


class TestRevenue:
    async def test_revenue_by_tier_and_location(self):
        svc = _make_service()
        svc._verifications.analytics_snapshot = AsyncMock(return_value=[
            _row(V1, VerificationTier.PREMIUM, VerificationStatus.COMPLETED, state="Lagos"),
            _row(V2, VerificationTier.BASIC, VerificationStatus.PAID, state="Abuja"),
        ])
        svc._payments.revenue_by_verification = AsyncMock(return_value={
            Utils.uuid_to_hex(V1): 30_000_000, Utils.uuid_to_hex(V2): 5_000_000,
        })
        rev = await svc.revenue()
        assert rev.total_minor == 35_000_000
        premium = next(t for t in rev.by_tier if t.tier == VerificationTier.PREMIUM)
        assert premium.revenue_minor == 30_000_000
        assert rev.by_location[0].revenue_minor == 30_000_000  # sorted desc


class TestRegional:
    async def test_regional_rolls_up_by_state(self):
        svc = _make_service()
        svc._verifications.analytics_snapshot = AsyncMock(return_value=[
            _row(V1, VerificationTier.BASIC, VerificationStatus.IN_PROGRESS, state="Lagos"),
            _row(V2, VerificationTier.BASIC, VerificationStatus.COMPLETED, state="Lagos"),
        ])
        svc._payments.revenue_by_verification = AsyncMock(return_value={Utils.uuid_to_hex(V2): 5_000_000})
        svc._reports.list_released_scores = AsyncMock(return_value={Utils.uuid_to_hex(V2): 90})
        rows = await svc.regional()
        lagos = next(r for r in rows if r.state == "Lagos")
        assert lagos.active == 1 and lagos.completed == 1
        assert lagos.revenue_minor == 5_000_000
        assert lagos.avg_trust_score == 90.0


class TestAgentTrends:
    async def test_groups_by_month(self):
        svc = _make_service()
        now = Utils.datetime_now()
        svc._tasks.list_approved_since = AsyncMock(return_value=[(now, 100), (now, 80)])
        trends = await svc.agent_trends()
        assert len(trends.points) == 1
        assert trends.points[0].completed_tasks == 2
        assert trends.points[0].avg_quality == 90.0
