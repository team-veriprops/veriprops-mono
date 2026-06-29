"""Cross-portal actionable-count aggregator (PRD §2.14).

Forward-compatible by design: actionable-count *sources* register themselves
here. Until later slices add sources (agent tasks → S11, notifications → S16),
the registry is empty and every persona reports 0 — so the badge is wired now
and lights up automatically when those domains land, with no change here."""
from __future__ import annotations

from typing import Awaitable, Callable, ClassVar, List

from kink import inject

from main.app.domain.user.auth.cross_portal.models import (
    CrossPortalSummaryDto,
    PersonaActionableCountDto,
)
from main.app.domain.user.auth.session.models import UserPersona

# (user_id, persona) -> actionable item count for that persona
PersonaCountSource = Callable[[str, UserPersona], Awaitable[int]]


@inject
class CrossPortalService:
    _sources: ClassVar[List[PersonaCountSource]] = []

    @classmethod
    def register_source(cls, source: PersonaCountSource) -> None:
        """Register a per-persona actionable-count source (called by later slices)."""
        cls._sources.append(source)

    async def summary(self, user_id: str, personas: List[UserPersona]) -> CrossPortalSummaryDto:
        counts: List[PersonaActionableCountDto] = []
        for persona in personas:
            total = 0
            for source in self._sources:
                total += await source(user_id, persona)
            counts.append(PersonaActionableCountDto(persona=persona, actionable_count=total))
        return CrossPortalSummaryDto(personas=counts)
