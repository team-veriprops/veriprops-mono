"""Portal customer endpoints — tracking, evidence, report (S32, S34, S35, S36)."""
from __future__ import annotations

from typing import List

from fastapi import Depends, Request
from fastapi.responses import Response

from main.app.domain.verification.portal.models import (
    AcknowledgeDto as _AcknowledgePortalDto,
    CustomerEvidenceItemDto,
    TrackingDto,
)
from main.app.domain.verification.portal.tracking import TrackingService
from main.app.domain.verification.portal.evidence import CustomerEvidenceService
from main.app.domain.verification.report.assembly import ReportAssemblyService
from main.app.domain.verification.report.models import ReportDto
from main.app.domain.verification.report.pdf import PDFGeneratorService
from main.appodus_utils.auth.jwt import AuthJWTBearer
from main.appodus_utils.response.success_response import SuccessResponse
from main.appodus_utils.router import AppRouter

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
