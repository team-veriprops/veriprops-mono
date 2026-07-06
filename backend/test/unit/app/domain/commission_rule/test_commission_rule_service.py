"""CommissionRuleService — default rates reproduce the prior flat model + kobo-exact
commission math (§15.1 / D30). Repos mocked, no DB."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.config.settings import settings
from main.app.core.state.status import AgentRole, VerificationTier
from main.app.domain.commission_rule.service import CommissionRuleService
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


def _make_service(rules_by_key=None):
    svc = object.__new__(CommissionRuleService)
    svc._repo = AsyncMock()
    svc._weights = AsyncMock()
    svc._audit = SimpleNamespace(schedule=lambda **k: None)
    rules = rules_by_key or {}

    async def _get(role, tier):
        return rules.get((role, tier))

    svc._repo.get_for_role_tier = AsyncMock(side_effect=_get)
    return svc


class TestDefaultRate:
    def test_default_rate_reproduces_flat_model(self):
        # weight_percent/100 × AGENT_COMMISSION_SHARE, in basis points.
        share = settings.AGENT_COMMISSION_SHARE
        assert CommissionRuleService._default_rate_bps(100) == round(100 * 100 * share)
        assert CommissionRuleService._default_rate_bps(40) == round(40 * 100 * share)
        assert CommissionRuleService._default_rate_bps(0) == 0


class TestCommissionMinor:
    async def test_commission_is_price_times_rate_exact_kobo(self):
        rule = SimpleNamespace(rate_bps=4000)  # 40%
        svc = _make_service({(AgentRole.REGISTRY.value, VerificationTier.BASIC.value): rule})
        amount = await svc.commission_minor(5_000_000, AgentRole.REGISTRY, VerificationTier.BASIC)
        assert amount == 2_000_000  # 5,000,000 × 4000 / 10,000

    async def test_missing_rule_yields_zero(self):
        svc = _make_service({})
        amount = await svc.commission_minor(5_000_000, AgentRole.LAWYER, VerificationTier.PREMIUM)
        assert amount == 0

    async def test_share_bps_reads_rule(self):
        rule = SimpleNamespace(rate_bps=1600)
        svc = _make_service({(AgentRole.FIELD.value, VerificationTier.STANDARD.value): rule})
        assert await svc.get_agent_share_bps(AgentRole.FIELD, VerificationTier.STANDARD) == 1600
