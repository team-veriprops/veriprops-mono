"""Role submission validation (PRD §7.3).

Each role captures a different structured form on submit. Rather than four ORM
shapes, the payload is JSON validated here against a per-role required-field set —
the single place the four role forms are enforced. Keeps the wire contract explicit
while letting each form evolve without a migration.
"""
from __future__ import annotations

from typing import Any, Dict, List

from main.app.core.state.status import AgentRole
from main.appodus_utils.exception.exceptions import ValidationException

# Required keys per role form (§7.3). Values must be present and non-empty.
_REQUIRED_FIELDS: Dict[AgentRole, List[str]] = {
    AgentRole.REGISTRY: ["registered_owner", "title_search_result", "search_reference"],
    AgentRole.FIELD: ["occupancy_status", "physical_condition"],
    AgentRole.SURVEYOR: ["area_sqm", "beacon_status"],
    AgentRole.LAWYER: ["legal_opinion", "risk_level", "recommendation"],
}


def validate_submission(role: AgentRole, payload: Dict[str, Any]) -> None:
    """Raise ``ValidationException`` if the role's submission form is incomplete."""
    if not isinstance(payload, dict):
        raise ValidationException(message="Submission payload must be an object.")
    required = _REQUIRED_FIELDS.get(role, [])
    missing = [f for f in required if payload.get(f) in (None, "", [], {})]
    if missing:
        raise ValidationException(
            message=f"Missing required {role.value} fields: {', '.join(missing)}."
        )
