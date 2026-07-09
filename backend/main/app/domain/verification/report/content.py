"""Report content builder (PRD §10.1) — the single source for the on-screen report and
the PDF, so they stay in parity.

Pure and deterministic: turns the released report's immutable ``findings`` snapshot plus
the tier into the plain-language verdict, the trust-score band, and the collapsible,
tier-dependent sections. The Premium Legal Opinion section is built here but its content
is withheld unless ``LEGAL_OPINION_ENABLED`` (D18 / §B go-live gate).
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from main.app.core.state.dependencies import roles_for_tier
from main.app.core.state.status import AgentRole, VerificationTier
from main.app.domain.verification.report.models import CustomerReportDto, ReportSectionDto

# §3.5 legal footer — required verbatim on every report page and every PDF page (§10.1).
LEGAL_FOOTER_TEXT = (
    "This report represents a professional opinion, not a legal guarantee. Findings are "
    "based on information available at the time of verification. Veriprops — Jurisdiction: "
    'Nigeria. "We reduce uncertainty. We do not eliminate it."'
)

# Trust-score bands (§10.1): 90+ Safe / 60–89 Caution / 0–59 High Risk.
_BAND_SAFE = "Safe"
_BAND_CAUTION = "Caution"
_BAND_HIGH_RISK = "High Risk"

# Role → report section title (§10.1).
_ROLE_SECTION_TITLE = {
    AgentRole.REGISTRY: "Registry & Title",
    AgentRole.FIELD: "Physical Findings",
    AgentRole.SURVEYOR: "Boundary & Survey",
    AgentRole.LAWYER: "Legal Opinion",
}


def trust_band(score: int) -> Tuple[str, str]:
    """Band + plain-language meaning for a composite trust score (§10.1)."""
    if score >= 90:
        return _BAND_SAFE, "Low risk — the findings support proceeding with normal diligence."
    if score >= 60:
        return _BAND_CAUTION, "Some risks were found — review the details carefully before proceeding."
    return _BAND_HIGH_RISK, "Significant risks were found — we would not proceed without resolving these."


def _verdict(band: str) -> str:
    """Plain-language verdict lead (§10.1), framed as professional opinion, never
    instruction. Final wording is on the §B legal sign-off list; this is the safe default."""
    if band == _BAND_SAFE:
        return (
            "In our professional opinion, this property's records are consistent and we found no "
            "material issues at this stage. As with any verification, we reduce uncertainty — we do "
            "not eliminate it."
        )
    if band == _BAND_CAUTION:
        return (
            "In our professional opinion, this property carries some risks worth weighing carefully "
            "before you proceed. The sections below set out what we found so you can make an informed "
            "decision."
        )
    return (
        "In our professional opinion, the risks we found here are significant. We would want them "
        "fully resolved before committing to this property. The sections below explain why."
    )


def _humanize(key: str) -> str:
    return key.replace("_", " ").strip().capitalize()


def _render_payload(payload: Optional[Dict[str, Any]]) -> str:
    if not payload:
        return "No findings were recorded for this section."
    lines = []
    for key, value in payload.items():
        if isinstance(value, (list, tuple)):
            value = ", ".join(str(v) for v in value) if value else "none"
        lines.append(f"{_humanize(key)}: {value}")
    return "\n".join(lines)


def build_report_content(
    *,
    report,
    vid: str,
    tier: VerificationTier,
    address: Optional[str],
    legal_opinion_enabled: bool,
) -> CustomerReportDto:
    """Compose the customer report DTO from a RELEASED report (§10.1)."""
    score = report.composite_trust_score or 0
    band, meaning = trust_band(score)
    verdict = _verdict(band)
    findings: Dict[str, Any] = report.findings or {}
    tier_roles = set(roles_for_tier(tier))

    sections = [
        ReportSectionDto(
            key="executive_summary",
            title="Executive Summary",
            body=f"{verdict}\n\nTrust score: {score}/100 ({band}). {meaning}",
        )
    ]

    legal_included = False
    for role in roles_for_tier(tier):
        payload = findings.get(role.value)
        if role == AgentRole.LAWYER:
            legal_included = legal_opinion_enabled
            body = (
                _render_payload(payload)
                if legal_opinion_enabled
                else "The Legal Opinion is being finalised and will be available shortly."
            )
            sections.append(ReportSectionDto(
                key="legal_opinion", title=_ROLE_SECTION_TITLE[role], body=body, is_legal_opinion=True,
            ))
            continue
        sections.append(ReportSectionDto(
            key=role.value.lower(),
            title=_ROLE_SECTION_TITLE[role],
            body=_render_payload(payload),
        ))

    # Risk summary aggregates any per-role risk signals for a quick scan.
    risk_bits = [
        f"{_ROLE_SECTION_TITLE.get(AgentRole(r), r)}: {p.get('risk_level')}"
        for r, p in findings.items()
        if isinstance(p, dict) and p.get("risk_level") and AgentRole(r) in tier_roles
    ]
    sections.append(ReportSectionDto(
        key="risk_summary", title="Risk Summary",
        body="\n".join(risk_bits) if risk_bits else f"Overall trust score {score}/100 ({band}).",
    ))

    # Customer-submitted documents appendix (§10.1). Customer-vs-agent upload
    # attribution is surfaced once the property-documents pipeline lands (follow-up).
    sections.append(ReportSectionDto(
        key="customer_documents", title="Customer-Submitted Documents",
        body="Documents you submitted are on file and were available to the verifying agents.",
    ))

    return CustomerReportDto(
        id=report.id,
        verification_id=report.verification_id,
        vid=vid,
        tier=tier,
        address=address,
        report_version=report.report_version,
        released_at=report.released_at,
        trust_score=score,
        trust_band=band,
        trust_meaning=meaning,
        verdict=verdict,
        sections=sections,
        legal_opinion_included=legal_included,
    )
