"""Cross-portal awareness DTOs (PRD §2.14). Reports a per-persona actionable
count; the frontend turns it into the "other hat" badge."""
from __future__ import annotations

from typing import List

from main.app.domain.user.auth.session.models import UserPersona
from main.appodus_utils import Object


class PersonaActionableCountDto(Object):
    persona: UserPersona
    actionable_count: int


class CrossPortalSummaryDto(Object):
    personas: List[PersonaActionableCountDto]
