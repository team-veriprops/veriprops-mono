"""Unit tests for the cross-portal actionable-count aggregator (S6 / PRD §2.14)."""
from __future__ import annotations

import pytest

from main.app.domain.user.auth.cross_portal.service import CrossPortalService
from main.app.domain.user.auth.session.models import UserPersona


@pytest.fixture(autouse=True)
def _clear_sources():
    original = list(CrossPortalService._sources)
    CrossPortalService._sources.clear()
    yield
    CrossPortalService._sources[:] = original


class TestCrossPortalSummary:
    async def test_no_sources_yields_zero_per_persona(self):
        svc = CrossPortalService()
        result = await svc.summary("user-1", [UserPersona.CUSTOMER, UserPersona.AGENT])
        assert {p.persona for p in result.personas} == {UserPersona.CUSTOMER, UserPersona.AGENT}
        assert all(p.actionable_count == 0 for p in result.personas)

    async def test_single_persona_returns_one_entry(self):
        svc = CrossPortalService()
        result = await svc.summary("user-1", [UserPersona.CUSTOMER])
        assert len(result.personas) == 1

    async def test_registered_sources_are_summed_per_persona(self):
        async def source_a(user_id: str, persona: UserPersona) -> int:
            return 3 if persona == UserPersona.CUSTOMER else 0

        async def source_b(user_id: str, persona: UserPersona) -> int:
            return 2

        CrossPortalService.register_source(source_a)
        CrossPortalService.register_source(source_b)

        svc = CrossPortalService()
        result = await svc.summary("user-1", [UserPersona.CUSTOMER, UserPersona.AGENT])
        counts = {p.persona: p.actionable_count for p in result.personas}
        assert counts[UserPersona.CUSTOMER] == 5
        assert counts[UserPersona.AGENT] == 2
