"""AgentReputationService — suggested-agent ranking, availability, coverage (§16.1)."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.core.state.status import AgentRole
from main.app.domain.system_config.models import ConfigKey
from main.app.domain.user.agent.coverage.models import AgentCoverageInputDto
from main.app.domain.user.agent.profile.models import AvailabilityStatus
from main.app.domain.user.agent.reputation.metrics import AgentMetrics
from main.app.domain.user.agent.reputation.service import AgentReputationService
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ValidationException

_CONFIG = {
    ConfigKey.AGENT_LOW_PERFORMANCE_THRESHOLD: 40,
    ConfigKey.AGENT_TOP_AGENT_ACCURACY_THRESHOLD: 90,
    ConfigKey.TASK_SLA_HOURS: 48,
    ConfigKey.AGENT_WIDE_COVERAGE_STATES: 6,
}


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


def _metrics(composite=80, accuracy=4.5, avg_quality=90):
    return AgentMetrics(
        total_jobs=5, completed_jobs=4, completion_rate=80, avg_quality=avg_quality,
        accuracy_score=accuracy, timeliness_rate=90, decline_count=0,
        composite_score=composite, active_since=None,
    )


def _profile(uid, roles=("FIELD",), availability=AvailabilityStatus.GREEN):
    return SimpleNamespace(id=f"p-{uid}", user_id=uid, approved_roles=list(roles),
                           availability=availability.value)


def _make_service(**overrides):
    svc = object.__new__(AgentReputationService)
    svc._profiles = AsyncMock()
    svc._coverage = AsyncMock()
    svc._credentials = AsyncMock()
    svc._tasks = AsyncMock()
    svc._verifications = AsyncMock()
    svc._properties = AsyncMock()
    svc._config = AsyncMock()
    svc._audit = MagicMock()
    svc._config.get_int = AsyncMock(side_effect=lambda k: _CONFIG[k])
    svc._credentials.list_for_user = AsyncMock(return_value=[])  # no credential requirement for FIELD
    svc._agent_name = AsyncMock(return_value="Agent Name")
    for k, v in overrides.items():
        setattr(svc, k, v)
    return svc


class TestSuggestedAgents:
    async def test_ranks_by_composite_and_filters(self):
        svc = _make_service()
        svc._verifications.get_model = AsyncMock(return_value=SimpleNamespace(property_id="prop-1"))
        svc._properties.get_model = AsyncMock(return_value=SimpleNamespace(state="lagos"))
        svc._profiles.list_by_status = AsyncMock(return_value=[
            _profile("a-hi"), _profile("a-lo"), _profile("a-registry", roles=("REGISTRY",)),
            _profile("a-fullcap"),
        ])
        # a-registry is not approved for FIELD → excluded; a-fullcap is at capacity → excluded.
        svc._coverage.list_for_user = AsyncMock(return_value=[SimpleNamespace(state="lagos")])
        svc._tasks.count_active_for_agent = AsyncMock(side_effect=lambda uid: 5 if uid == "a-fullcap" else 0)
        composites = {"a-hi": _metrics(90), "a-lo": _metrics(30), "a-fullcap": _metrics(70)}
        svc._compute = AsyncMock(side_effect=lambda uid: composites.get(uid, _metrics(50)))

        out = await svc.suggested_agents("v-1", AgentRole.FIELD)
        ids = [c.user_id for c in out]
        assert "a-registry" not in ids and "a-fullcap" not in ids   # filtered
        assert ids[0] == "a-hi"                                     # highest composite first
        assert out[0].top_agent is True                            # accuracy 90 ≥ threshold
        lo = next(c for c in out if c.user_id == "a-lo")
        assert lo.low_performance is True                          # composite 30 < 40
        assert ids[-1] == "a-lo"                                   # low performer sinks

    async def test_field_agent_out_of_area_excluded(self):
        svc = _make_service()
        svc._verifications.get_model = AsyncMock(return_value=SimpleNamespace(property_id="prop-1"))
        svc._properties.get_model = AsyncMock(return_value=SimpleNamespace(state="lagos"))
        svc._profiles.list_by_status = AsyncMock(return_value=[_profile("a-1")])
        svc._coverage.list_for_user = AsyncMock(return_value=[SimpleNamespace(state="kano")])
        svc._tasks.count_active_for_agent = AsyncMock(return_value=0)
        svc._compute = AsyncMock(return_value=_metrics(80))
        out = await svc.suggested_agents("v-1", AgentRole.FIELD)
        assert out == []  # Field is location-bound; kano ≠ lagos

    async def test_registry_agent_not_location_bound(self):
        svc = _make_service()
        svc._verifications.get_model = AsyncMock(return_value=SimpleNamespace(property_id="prop-1"))
        svc._properties.get_model = AsyncMock(return_value=SimpleNamespace(state="lagos"))
        svc._profiles.list_by_status = AsyncMock(return_value=[_profile("a-1", roles=("REGISTRY",))])
        svc._coverage.list_for_user = AsyncMock(return_value=[SimpleNamespace(state="kano")])
        svc._tasks.count_active_for_agent = AsyncMock(return_value=0)
        svc._compute = AsyncMock(return_value=_metrics(80))
        out = await svc.suggested_agents("v-1", AgentRole.REGISTRY)
        assert len(out) == 1  # remote-capable; coverage does not gate


class TestAvailability:
    async def test_effective_forces_red_at_capacity(self):
        svc = _make_service()
        svc._profiles.get_by_user_id = AsyncMock(return_value=_profile("a-1"))
        svc._profiles.update = AsyncMock()
        svc._tasks.count_active_for_agent = AsyncMock(return_value=5)  # at cap
        eff = await svc.set_availability("a-1", AvailabilityStatus.GREEN)
        assert eff == AvailabilityStatus.RED

    async def test_effective_respects_set_value_below_capacity(self):
        svc = _make_service()
        svc._profiles.get_by_user_id = AsyncMock(return_value=_profile("a-1"))
        svc._profiles.update = AsyncMock()
        svc._tasks.count_active_for_agent = AsyncMock(return_value=1)
        eff = await svc.set_availability("a-1", AvailabilityStatus.AMBER)
        assert eff == AvailabilityStatus.AMBER


class TestCoverage:
    async def test_rejects_unknown_state(self):
        svc = _make_service()
        with pytest.raises(ValidationException):
            await svc.set_coverage("a-1", [AgentCoverageInputDto(state="atlantis")])

    async def test_replaces_coverage(self):
        svc = _make_service()
        svc._coverage.list_for_user = AsyncMock(return_value=[
            SimpleNamespace(id="c-old", state="kano", lga=None, place=None, travel_radius_km=None),
        ])
        svc._coverage.soft_delete = AsyncMock()
        svc._coverage.create = AsyncMock()
        await svc.set_coverage("a-1", [AgentCoverageInputDto(state="Lagos")])
        svc._coverage.soft_delete.assert_awaited_once_with("c-old")
        svc._coverage.create.assert_awaited_once()
