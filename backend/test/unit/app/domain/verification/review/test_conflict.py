"""Cross-role conflict detection (§8.2) — pure rules."""
from main.app.core.state.status import AgentRole
from main.app.domain.verification.review.conflict import detect_conflicts


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

    def test_high_legal_risk_flagged(self):
        subs = {
            AgentRole.REGISTRY: {"title_search_result": "clean"},
            AgentRole.LAWYER: {"legal_opinion": "risky", "risk_level": "high", "recommendation": "hold"},
        }
        conflicts = detect_conflicts(subs)
        assert any(c.severity == "MEDIUM" for c in conflicts)

    def test_no_lawyer_no_conflict(self):
        subs = {AgentRole.REGISTRY: {"title_search_result": "encumbrance"}}
        assert detect_conflicts(subs) == []
