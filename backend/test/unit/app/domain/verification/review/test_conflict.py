"""Cross-role conflict detection (§8.2) — pure rules."""
import pytest

from main.app.core.state.status import AgentRole
from main.app.domain.verification.review.conflict import ConflictSeverity, detect_conflicts
from main.app.domain.verification.task.models import LegalRiskLevel


class TestConflictDetection:
    def test_no_conflict_for_clean_submissions(self):
        subs = {
            AgentRole.REGISTRY: {"title_search_result": "clean", "registered_owner": "A"},
            AgentRole.LAWYER: {"legal_opinion": "sound", "risk_level": "low", "recommendation": "proceed"},
        }
        assert detect_conflicts(subs) == []

    def test_encumbrance_vs_proceed_is_high_conflict(self):
        subs = {
            AgentRole.REGISTRY: {"title_search_result": "encumbrance found", "encumbrances": ["mortgage"]},
            AgentRole.LAWYER: {"legal_opinion": "ok", "risk_level": "low", "recommendation": "proceed"},
        }
        conflicts = detect_conflicts(subs)
        assert any(c.severity == "HIGH" for c in conflicts)

    # "high" is how submissions read before the risk level became an enum; they still count.
    @pytest.mark.parametrize("risk_level", [LegalRiskLevel.HIGH.value, "high", " High "])
    def test_a_high_legal_risk_is_an_advisory_medium_conflict(self, risk_level):
        subs = {
            AgentRole.REGISTRY: {"title_search_result": "clean"},
            AgentRole.LAWYER: {"legal_opinion": "risky", "risk_level": risk_level, "recommendation": "hold"},
        }
        conflicts = detect_conflicts(subs)
        assert [c.severity for c in conflicts] == [ConflictSeverity.MEDIUM]

    @pytest.mark.parametrize("risk_level", [LegalRiskLevel.LOW.value, LegalRiskLevel.MEDIUM.value])
    def test_a_lower_legal_risk_raises_nothing(self, risk_level):
        subs = {AgentRole.LAWYER: {"legal_opinion": "ok", "risk_level": risk_level, "recommendation": "hold"}}
        assert detect_conflicts(subs) == []

    def test_no_lawyer_no_conflict(self):
        subs = {AgentRole.REGISTRY: {"title_search_result": "encumbrance"}}
        assert detect_conflicts(subs) == []


def test_severity_goes_on_the_wire_as_the_same_string():
    """The admin console reads "HIGH"/"MEDIUM"; the enum must not change what it receives."""
    from main.app.domain.verification.review.conflict import ConflictSeverity, ReviewConflict

    conflict = ReviewConflict(severity=ConflictSeverity.HIGH, roles=[AgentRole.LAWYER], message="m")
    assert conflict.as_dict()["severity"] == "HIGH"
    assert [s.value for s in ConflictSeverity] == ["HIGH", "MEDIUM", "LOW"]
