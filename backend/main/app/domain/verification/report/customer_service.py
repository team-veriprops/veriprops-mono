"""Customer report experience service (PRD §10).

Assembles the customer-facing released report: ownership gate → released report →
content build (verdict, trust band, tier-dependent sections; Legal Opinion gated by
LEGAL_OPINION_ENABLED, D18) → access-gate acknowledgement state → PDF render via the
report_pdf facade. The same content object feeds the on-screen view and the PDF, so they
stay in parity (§10.2).
"""
from __future__ import annotations

from kink import inject

from main.app.config.settings import settings
from main.app.core.state.status import VerificationTier
from main.app.domain.property.repo import PropertyRepo
from main.app.domain.verification.report.acknowledgement.service import ReportAcknowledgementService
from main.app.domain.verification.report.content import LEGAL_FOOTER_TEXT, build_report_content
from main.app.domain.verification.report.models import CustomerReportDto
from main.app.domain.verification.report.service import ReportService
from main.app.domain.verification.service import VerificationService
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ResourceNotFoundException
from main.appodus_utils.integrations.report_pdf import (
    ReportPdfContext,
    ReportPdfProviderFactory,
    ReportPdfSection,
)


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class CustomerReportService:
    def __init__(
        self,
        verification_service: VerificationService,
        report_service: ReportService,
        acknowledgement_service: ReportAcknowledgementService,
        property_repo: PropertyRepo,
        pdf_factory: ReportPdfProviderFactory,
    ):
        self._verifications = verification_service
        self._reports = report_service
        self._acks = acknowledgement_service
        self._properties = property_repo
        self._pdf_factory = pdf_factory

    async def get_report(self, verification_id: str, customer_id: str) -> CustomerReportDto:
        content, _ = await self._build(verification_id, customer_id)
        return content

    async def acknowledge(self, verification_id: str, customer_id: str) -> CustomerReportDto:
        """Record the one-time access-gate acknowledgement against the current version (§10.1)."""
        content, report = await self._build(verification_id, customer_id)
        await self._acks.acknowledge(
            customer_id=customer_id, verification_id=verification_id,
            report_id=report.id, report_version=report.report_version,
        )
        content.acknowledged = True
        return content

    async def render_pdf(self, verification_id: str, customer_id: str) -> bytes:
        content, _ = await self._build(verification_id, customer_id)
        provider = self._pdf_factory.get_active_provider()
        return provider.render(self._to_pdf_context(content))

    async def build_shared_content(self, verification_id: str) -> CustomerReportDto:
        """The full released report for a named-recipient share (§13.2) — the share token
        is the authorization, so no customer-ownership gate. Acknowledgement is handled by
        the share's own disclaimer, not the customer access gate."""
        v = await self._verifications.get_by_id(verification_id)
        return await self._content_from_verification(v)

    # ── helpers ───────────────────────────────────────────────────

    async def _build(self, verification_id: str, customer_id: str):
        v = await self._verifications.get_owned(verification_id, customer_id)
        content = await self._content_from_verification(v)
        report = await self._reports.get_released(verification_id)
        content.acknowledged = await self._acks.is_acknowledged(
            customer_id, verification_id, report.report_version
        )
        return content, report

    async def _content_from_verification(self, v) -> CustomerReportDto:
        report = await self._reports.get_released(v.id)
        if report is None:
            raise ResourceNotFoundException(
                resource="report", message="No released report is available for this verification yet."
            )
        tier = VerificationTier(v.tier)
        address = None
        if v.property_id:
            prop = await self._properties.get_model(v.property_id)
            address = prop.address if prop else None
        return build_report_content(
            report=report, vid=v.vid, tier=tier, address=address,
            legal_opinion_enabled=settings.LEGAL_OPINION_ENABLED,
        )

    def _to_pdf_context(self, content: CustomerReportDto) -> ReportPdfContext:
        return ReportPdfContext(
            brand=settings.REPORT_BRAND_NAME,
            vid=content.vid,
            tier=content.tier.value if content.tier else None,
            address=content.address,
            report_version=content.report_version,
            released_on=content.released_at.strftime("%d %b %Y") if content.released_at else None,
            trust_score=content.trust_score or 0,
            trust_band=content.trust_band or "",
            trust_meaning=content.trust_meaning or "",
            verdict=content.verdict,
            sections=[
                ReportPdfSection(title=s.title, body=s.body, is_legal_opinion=s.is_legal_opinion)
                for s in content.sections
            ],
            footer_text=LEGAL_FOOTER_TEXT,
            qr_url=f"{settings.PUBLIC_APP_BASE_URL.rstrip('/')}/verify/{content.vid}",
            superseded=content.superseded,
        )
