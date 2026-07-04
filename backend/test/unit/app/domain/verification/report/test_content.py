"""Report content builder (§10.1): trust-score bands, opinion-framed verdict, tier-gated
sections, and the Legal Opinion go-live gate (D18)."""
from types import SimpleNamespace

import pytest

from main.app.core.state.status import VerificationTier
from main.app.domain.verification.report.content import (
    LEGAL_FOOTER_TEXT,
    build_report_content,
    trust_band,
)


def _report(score=95, findings=None, version=1):
    return SimpleNamespace(
        id="rep-1", verification_id="v-1", report_version=version,
        composite_trust_score=score, released_at=None,
        findings=findings if findings is not None else {
            "REGISTRY": {"title_search_result": "clean", "risk_level": "low"},
            "FIELD": {"inspection": "matches listing"},
            "SURVEYOR": {"boundary": "confirmed"},
        },
    )


class TestTrustBand:
    @pytest.mark.parametrize("score,band", [(95, "Safe"), (90, "Safe"), (75, "Caution"),
                                            (60, "Caution"), (40, "High Risk"), (0, "High Risk")])
    def test_bands(self, score, band):
        assert trust_band(score)[0] == band


class TestContent:
    def test_verdict_is_framed_as_opinion(self):
        c = build_report_content(report=_report(95), vid="VP-1", tier=VerificationTier.STANDARD,
                                 address="12 Lekki", legal_opinion_enabled=False)
        assert "professional opinion" in c.verdict.lower()
        assert c.trust_band == "Safe"
        assert c.trust_score == 95

    def test_standard_tier_sections(self):
        c = build_report_content(report=_report(), vid="VP-1", tier=VerificationTier.STANDARD,
                                 address=None, legal_opinion_enabled=True)
        titles = [s.title for s in c.sections]
        assert "Executive Summary" in titles
        assert "Registry & Title" in titles
        assert "Physical Findings" in titles
        assert "Boundary & Survey" in titles
        assert "Legal Opinion" not in titles  # Standard has no lawyer role

    def test_footer_text_matches_disclaimer(self):
        assert "professional opinion, not a legal guarantee" in LEGAL_FOOTER_TEXT
        assert "We reduce uncertainty. We do not eliminate it." in LEGAL_FOOTER_TEXT


class TestLegalOpinionGate:
    def _premium(self, enabled):
        findings = {
            "REGISTRY": {"ok": True}, "FIELD": {"ok": True}, "SURVEYOR": {"ok": True},
            "LAWYER": {"legal_opinion": "title is sound", "recommendation": "proceed"},
        }
        return build_report_content(report=_report(findings=findings), vid="VP-1",
                                    tier=VerificationTier.PREMIUM, address=None,
                                    legal_opinion_enabled=enabled)

    def test_legal_opinion_withheld_when_disabled(self):
        c = self._premium(enabled=False)
        legal = next(s for s in c.sections if s.is_legal_opinion)
        assert c.legal_opinion_included is False
        assert "title is sound" not in legal.body  # content withheld (§B gate, D18)

    def test_legal_opinion_shown_when_enabled(self):
        c = self._premium(enabled=True)
        legal = next(s for s in c.sections if s.is_legal_opinion)
        assert c.legal_opinion_included is True
        assert "title is sound" in legal.body
