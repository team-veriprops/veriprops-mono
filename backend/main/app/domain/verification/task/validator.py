"""Role submission validation (PRD §12.2).

Each role captures a different structured form on submit. Rather than four ORM
shapes, the payload is JSON validated here against a per-role required-field set —
the single place the four role forms are enforced. Keeps the wire contract explicit
while letting each form evolve without a migration.
"""
from __future__ import annotations

import enum
from typing import Any, Dict, List, Type

from main.app.core.state.status import AgentRole
from main.app.domain.verification.task.models import LegalRiskLevel
from main.appodus_utils.exception.exceptions import ValidationException

# Required keys per role form (§12.2). Values must be present and non-empty.
_REQUIRED_FIELDS: Dict[AgentRole, List[str]] = {
    AgentRole.REGISTRY: ["registered_owner", "title_search_result", "search_reference"],
    AgentRole.FIELD: ["occupancy_status", "physical_condition"],
    AgentRole.SURVEYOR: ["area_sqm", "beacon_status"],
    AgentRole.LAWYER: ["legal_opinion", "risk_level", "recommendation"],
}

# Fields answered from a fixed set. The stored value is the enum's, whatever casing was sent,
# so rules that read it (the HIGH-risk review conflict) compare against the enum.
_CHOICE_FIELDS: Dict[AgentRole, Dict[str, Type[enum.Enum]]] = {
    AgentRole.LAWYER: {"risk_level": LegalRiskLevel},
}


def _choice_label(member: enum.Enum) -> str:
    return str(member.value).replace("_", " ").capitalize()


def validate_submission(role: AgentRole, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return the role's submission with its choice fields normalised to their enum values.

    Raises ``ValidationException`` if the form is incomplete or a choice field holds a value
    outside its set. The caller's payload is not modified.
    """
    if not isinstance(payload, dict):
        raise ValidationException(message="Submission payload must be an object.")
    required = _REQUIRED_FIELDS.get(role, [])
    missing = [f for f in required if payload.get(f) in (None, "", [], {})]
    if missing:
        raise ValidationException(
            message=f"Missing required {role.value} fields: {', '.join(missing)}."
        )

    normalised = dict(payload)
    for field, choices in _CHOICE_FIELDS.get(role, {}).items():
        if field not in normalised:
            continue
        typed = str(normalised[field]).strip().upper()
        try:
            normalised[field] = choices(typed).value
        except ValueError:
            options = ", ".join(_choice_label(m) for m in choices)
            label = field.replace("_", " ").capitalize()
            raise ValidationException(message=f"{label} must be one of {options}.") from None
    return normalised
