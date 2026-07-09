"""Cross-role conflict detection (PRD §8.2).

Pure, deterministic rules over the per-role submission payloads. Surfaces
contradictions the admin should resolve before releasing — e.g. the registry flags an
encumbrance while the lawyer recommends proceeding, or a high legal risk was raised.
Returns a list of conflicts; an empty list means the submissions are internally
consistent (release may proceed once every role is approved).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from main.app.core.state.status import AgentRole

# Keywords that indicate a title defect in the registry findings.
_ENCUMBRANCE_MARKERS = ("encumbr", "dispute", "caveat", "lien", "lis pendens", "not clean")
_PROCEED_MARKERS = ("proceed", "no objection", "clear to")
_HIGH_RISK = ("high",)


class ReviewConflict:
    """A detected contradiction between role submissions."""

    def __init__(self, severity: str, roles: List[AgentRole], message: str):
        self.severity = severity
        self.roles = roles
        self.message = message

    def as_dict(self) -> Dict[str, Any]:
        return {"severity": self.severity, "roles": [r.value for r in self.roles], "message": self.message}


def _text(payload: Optional[Dict[str, Any]], *keys: str) -> str:
    if not payload:
        return ""
    return " ".join(str(payload.get(k, "")) for k in keys).lower()


def detect_conflicts(submissions: Dict[AgentRole, Optional[Dict[str, Any]]]) -> List[ReviewConflict]:
    """Return the conflicts across the provided per-role submission payloads."""
    conflicts: List[ReviewConflict] = []

    registry = submissions.get(AgentRole.REGISTRY)
    lawyer = submissions.get(AgentRole.LAWYER)

    registry_text = _text(registry, "title_search_result", "encumbrances")
    has_encumbrance = bool(registry) and (
        any(m in registry_text for m in _ENCUMBRANCE_MARKERS)
        or bool(registry.get("encumbrances"))
    )

    if lawyer is not None:
        lawyer_text = _text(lawyer, "legal_opinion", "recommendation")
        lawyer_proceeds = any(m in lawyer_text for m in _PROCEED_MARKERS)
        if has_encumbrance and lawyer_proceeds:
            conflicts.append(ReviewConflict(
                severity="HIGH", roles=[AgentRole.REGISTRY, AgentRole.LAWYER],
                message="Registry flags a title encumbrance but the legal opinion recommends proceeding.",
            ))
        if _text(lawyer, "risk_level").strip() in _HIGH_RISK:
            conflicts.append(ReviewConflict(
                severity="MEDIUM", roles=[AgentRole.LAWYER],
                message="Lawyer flagged a HIGH legal risk — review before release.",
            ))

    return conflicts
