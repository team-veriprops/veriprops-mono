"""TrustScoreWeightService (§8.3): sum-to-100 validation + composite computation."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.state.status import AgentRole, VerificationTier
from main.app.domain.verification.scoring.service import TrustScoreWeightService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ValidationException


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


def _weight(tier, role, pct):
    return SimpleNamespace(id=f"{tier.value}-{role.value}", tier=tier.value, role=role.value, weight_percent=pct)


def _make_service(existing=None):
    svc = object.__new__(TrustScoreWeightService)
    svc._repo = MagicMock()
    svc._audit = MagicMock()
    state = {"rows": list(existing or [])}

    async def _get(tier, role):
        return next((w for w in state["rows"] if w.tier == tier and w.role == role), None)

    async def _list_for_tier(tier):
        return [w for w in state["rows"] if w.tier == tier]

    async def _update(wid, dto):
        w = next((w for w in state["rows"] if w.id == wid), None)
        if w and dto.weight_percent is not None:
            w.weight_percent = dto.weight_percent
        return w

    async def _create(dto):
        w = _weight(dto.tier, dto.role, dto.weight_percent)
        state["rows"].append(w)
        return w

    svc._repo.get_for_tier_role = AsyncMock(side_effect=_get)
    svc._repo.list_for_tier = AsyncMock(side_effect=_list_for_tier)
    svc._repo.update = AsyncMock(side_effect=_update)
    svc._repo.create_return_model = AsyncMock(side_effect=_create)
    svc._state = state
    return svc


class TestSetTierWeights:
    async def test_rejects_when_not_summing_to_100(self):
        svc = _make_service()
        with pytest.raises(ValidationException):
            await svc.set_tier_weights(
                VerificationTier.STANDARD,
                {AgentRole.REGISTRY: 50, AgentRole.FIELD: 30, AgentRole.SURVEYOR: 30},
                "admin-1",
            )

    async def test_rejects_missing_role(self):
        svc = _make_service()
        with pytest.raises(ValidationException):
            await svc.set_tier_weights(
                VerificationTier.STANDARD, {AgentRole.REGISTRY: 100}, "admin-1"
            )

    async def test_accepts_valid_sum(self):
        svc = _make_service()
        await svc.set_tier_weights(
            VerificationTier.STANDARD,
            {AgentRole.REGISTRY: 40, AgentRole.FIELD: 30, AgentRole.SURVEYOR: 30},
            "admin-1",
        )
        assert len(svc._state["rows"]) == 3


class TestCompositeScore:
    async def test_full_quality_gives_100(self):
        rows = [
            _weight(VerificationTier.STANDARD, AgentRole.REGISTRY, 40),
            _weight(VerificationTier.STANDARD, AgentRole.FIELD, 30),
            _weight(VerificationTier.STANDARD, AgentRole.SURVEYOR, 30),
        ]
        svc = _make_service(rows)
        score = await svc.compute_composite(
            VerificationTier.STANDARD,
            {AgentRole.REGISTRY: 100, AgentRole.FIELD: 100, AgentRole.SURVEYOR: 100},
        )
        assert score == 100

    async def test_weighted_blend(self):
        rows = [
            _weight(VerificationTier.STANDARD, AgentRole.REGISTRY, 40),
            _weight(VerificationTier.STANDARD, AgentRole.FIELD, 30),
            _weight(VerificationTier.STANDARD, AgentRole.SURVEYOR, 30),
        ]
        svc = _make_service(rows)
        # 0.4*80 + 0.3*100 + 0.3*100 = 32 + 30 + 30 = 92
        score = await svc.compute_composite(
            VerificationTier.STANDARD,
            {AgentRole.REGISTRY: 80, AgentRole.FIELD: 100, AgentRole.SURVEYOR: 100},
        )
        assert score == 92
