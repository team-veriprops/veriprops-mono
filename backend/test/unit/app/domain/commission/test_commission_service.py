"""Unit tests for CommissionService (S47)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.commission.models import (
    CreateCommissionRuleDto,
    EarningStatus,
)
from main.app.domain.commission.service import CommissionService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ResourceNotFoundException


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


def _mock_rule(rule_id="r-1", role="SURVEYOR", tier="STANDARD", percentage=10.0):
    r = MagicMock()
    r.id = rule_id
    r.role = role
    r.tier = tier
    r.percentage = percentage
    r.effective_date = "2025-01-01"
    r.date_created = str(datetime.now(timezone.utc))
    return r


def _mock_earning(earning_id="e-1", agent_id="agent-1", status=EarningStatus.PENDING.value, net_amount=100.0):
    e = MagicMock()
    e.id = earning_id
    e.agent_id = agent_id
    e.task_id = "task-1"
    e.verification_id = "ver-1"
    e.gross_amount = 1000.0
    e.commission_pct = 10.0
    e.net_amount = net_amount
    e.status = status
    e.computed_at = str(datetime.now(timezone.utc))
    e.date_created = str(datetime.now(timezone.utc))
    return e


def _make_svc(rule=None, earnings=None, created_earning=None):
    rule_repo = MagicMock()
    rule_repo.get_for_role_and_tier = AsyncMock(return_value=rule)
    rule_repo.get_all = AsyncMock(return_value=[rule] if rule else [])
    rule_repo.create = AsyncMock(return_value=rule or _mock_rule())
    rule_repo.update = AsyncMock()
    rule_repo.get_model = AsyncMock(return_value=rule or _mock_rule())

    earning_repo = MagicMock()
    earning_repo.create = AsyncMock(return_value=created_earning or _mock_earning())
    earning_repo.list_for_agent = AsyncMock(return_value=earnings or [])
    earning_repo.sum_available = AsyncMock(return_value=0)

    svc = CommissionService(rule_repo=rule_repo, earning_repo=earning_repo)
    return svc, rule_repo, earning_repo


class TestGetRate:
    async def test_returns_percentage_for_matching_rule(self):
        rule = _mock_rule(percentage=15.0)
        svc, _, _ = _make_svc(rule=rule)
        rate = await svc.get_rate("SURVEYOR", "STANDARD")
        assert rate == 15.0

    async def test_returns_none_when_no_rule(self):
        svc, _, _ = _make_svc(rule=None)
        rate = await svc.get_rate("LAWYER", "BASIC")
        assert rate is None


class TestComputeAndRecord:
    async def test_net_amount_is_gross_times_rate_over_100(self):
        rule = _mock_rule(percentage=10.0)
        earning = _mock_earning(net_amount=100.0)
        svc, _, earning_repo = _make_svc(rule=rule, created_earning=earning)

        result = await svc.compute_and_record(
            task_id="task-1",
            agent_id="agent-1",
            verification_id="ver-1",
            role="SURVEYOR",
            tier="STANDARD",
            gross_amount=1000.0,
        )

        # net = 1000 * 10 / 100 = 100
        call_dto = earning_repo.create.call_args[0][0]
        assert call_dto.net_amount == 100.0
        assert call_dto.commission_pct == 10.0

    async def test_creates_earning_row_once(self):
        rule = _mock_rule(percentage=5.0)
        svc, _, earning_repo = _make_svc(rule=rule)

        await svc.compute_and_record(
            task_id="t-1", agent_id="a-1", verification_id="v-1",
            role="SURVEYOR", tier="BASIC", gross_amount=500.0,
        )

        earning_repo.create.assert_called_once()

    async def test_uses_zero_rate_when_no_rule(self):
        svc, _, earning_repo = _make_svc(rule=None)

        await svc.compute_and_record(
            task_id="t-1", agent_id="a-1", verification_id="v-1",
            role="SURVEYOR", tier="BASIC", gross_amount=500.0,
        )

        call_dto = earning_repo.create.call_args[0][0]
        assert call_dto.net_amount == 0.0


class TestGetEarningsSummary:
    async def test_aggregates_pending_and_paid(self):
        earnings = [
            _mock_earning(status=EarningStatus.PENDING.value, net_amount=200.0),
            _mock_earning(status=EarningStatus.PAID.value, net_amount=100.0),
            _mock_earning(status=EarningStatus.PENDING.value, net_amount=50.0),
        ]
        svc, _, _ = _make_svc(earnings=earnings)

        summary = await svc.get_earnings_summary("agent-1")

        assert summary.total_lifetime == pytest.approx(350.0)
        assert summary.total_pending == pytest.approx(250.0)
        assert summary.total_paid == pytest.approx(100.0)

    async def test_empty_earnings_returns_zeros(self):
        svc, _, _ = _make_svc(earnings=[])
        summary = await svc.get_earnings_summary("agent-1")
        assert summary.total_lifetime == 0.0
        assert summary.total_pending == 0.0
        assert summary.total_paid == 0.0
