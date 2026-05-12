"""Portal customer endpoints — tracking, evidence, report (S32, S34, S35, S36, S42)."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.responses import Response

from main.app.domain.verification.models import VerificationStatus
from main.app.domain.verification.portal.models import (
    AcknowledgeDto as _AcknowledgePortalDto,
    CustomerEvidenceItemDto,
    TrackingDto,
)
from main.app.domain.verification.portal.tracking import TrackingService
from main.app.domain.verification.portal.evidence import CustomerEvidenceService
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.report.assembly import ReportAssemblyService
from main.app.domain.verification.report.models import ReportDto
from main.app.domain.verification.report.pdf import PDFGeneratorService
from main.appodus_utils import Object
from main.appodus_utils.auth.jwt import AuthJWTBearer
from main.appodus_utils.response.success_response import SuccessResponse
from main.appodus_utils.router import AppRouter
from kink import di

portal_router = AppRouter(prefix="/portal/verifications", tags=["Portal — Verifications"])

_auth = AuthJWTBearer()


@portal_router.get("/{vid}/tracking", response_model=SuccessResponse[TrackingDto])
async def get_tracking(
    vid: str,
    svc: TrackingService = Depends(lambda: __import__("kink", fromlist=["di"]).di[TrackingService]),
    claims=Depends(_auth),
):
    result = await svc.get_tracking(vid, customer_id=claims.sub)
    return SuccessResponse.ok(result)


@portal_router.get("/{vid}/evidence", response_model=SuccessResponse[List[CustomerEvidenceItemDto]])
async def list_evidence(
    vid: str,
    svc: CustomerEvidenceService = Depends(lambda: __import__("kink", fromlist=["di"]).di[CustomerEvidenceService]),
    claims=Depends(_auth),
):
    items = await svc.list_evidence(vid, customer_id=claims.sub)
    return SuccessResponse.ok(items)


@portal_router.get("/{vid}/report", response_model=SuccessResponse[ReportDto])
async def get_report(
    vid: str,
    svc: ReportAssemblyService = Depends(lambda: __import__("kink", fromlist=["di"]).di[ReportAssemblyService]),
    claims=Depends(_auth),
):
    report = await svc.assemble(vid, customer_id=claims.sub)
    return SuccessResponse.ok(report)


@portal_router.post("/{vid}/report/acknowledge", response_model=SuccessResponse[bool])
async def acknowledge_report(
    vid: str,
    body: _AcknowledgePortalDto,
    request: Request,
    svc: ReportAssemblyService = Depends(lambda: __import__("kink", fromlist=["di"]).di[ReportAssemblyService]),
    claims=Depends(_auth),
):
    ip = body.ip_address or (request.client.host if request.client else None)
    await svc.record_acknowledgement(vid, customer_id=claims.sub, ip_address=ip)
    return SuccessResponse.ok(True)


@portal_router.get("/{vid}/report/pdf")
async def download_report_pdf(
    vid: str,
    svc: PDFGeneratorService = Depends(lambda: __import__("kink", fromlist=["di"]).di[PDFGeneratorService]),
    claims=Depends(_auth),
):
    pdf_bytes = await svc.generate(vid, customer_id=claims.sub)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="veriprops-report-{vid}.pdf"'},
    )


# ── Public lookup (S42) — no auth ─────────────────────────────────────────────

public_router = AppRouter(prefix="/public/verifications", tags=["Public — Verifications"])


class PublicVerificationSummaryDto(Object):
    vid: str
    tier: str
    property_type: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None
    status: str
    trust_band: Optional[str] = None
    report_date: Optional[str] = None


def _compute_trust_band(score: Optional[float]) -> Optional[str]:
    if score is None:
        return None
    if score >= 80:
        return "HIGH"
    if score >= 50:
        return "MED"
    return "LOW"


@public_router.get("/{vid}", response_model=SuccessResponse[PublicVerificationSummaryDto])
async def get_public_verification(vid: str):
    repo: VerificationRepo = di[VerificationRepo]
    row = await repo.get_by_vid(vid)
    if row is None or row.deleted:
        raise HTTPException(status_code=404, detail="Not found")

    status = VerificationStatus(row.status)

    # Private or non-terminal non-sharing states
    if status not in (VerificationStatus.COMPLETED, VerificationStatus.IN_PROGRESS,
                      VerificationStatus.DISPUTED):
        raise HTTPException(status_code=404, detail="Not found")

    from main.app.domain.verification.property.repo import PropertyRepo
    from main.app.domain.verification.report.repo import ReportVersionRepo
    prop_repo: PropertyRepo = di[PropertyRepo]
    prop = await prop_repo.get_model(row.property_id) if row.property_id else None

    # Compute trust band from latest trust score (no raw number exposed)
    trust_band: Optional[str] = None
    report_date: Optional[str] = None
    if status == VerificationStatus.COMPLETED:
        try:
            ver_detail = await repo.get_model(str(row.id))
            score = getattr(ver_detail, "trust_score", None)
            trust_band = _compute_trust_band(float(score) if score else None)
        except Exception:
            pass

    return SuccessResponse.ok(PublicVerificationSummaryDto(
        vid=row.vid,
        tier=row.tier,
        property_type=prop.property_type if prop else None,
        state=prop.state if prop else None,
        lga=prop.lga if prop else None,
        status=status.value,
        trust_band=trust_band,
        report_date=str(row.completed_at) if row.completed_at else None,
    ))
