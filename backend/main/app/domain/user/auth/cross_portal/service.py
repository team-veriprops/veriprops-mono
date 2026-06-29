"""Cross-portal actionable-count aggregator (PRD §2.14).

Count sources register themselves here. The registry starts empty (agent tasks
and notifications register theirs in later slices), so every persona reports 0
until then."""
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
        cls._sources.append(source)

    async def summary(self, user_id: str, personas: List[UserPersona]) -> CrossPortalSummaryDto:
        counts: List[PersonaActionableCountDto] = []
        for persona in personas:
            total = 0
            for source in self._sources:
                total += await source(user_id, persona)
            counts.append(PersonaActionableCountDto(persona=persona, actionable_count=total))
        return CrossPortalSummaryDto(personas=counts)
