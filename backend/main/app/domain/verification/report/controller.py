"""Customer report controller (PRD §10).

URL shape: /verifications/{id}/report — customer-owned (JWT subject must own the
verification). Frontend service: frontend/src/components/portal/libs/report-service.
The released report entity/versioning is admin-produced (S12); this exposes the
customer-facing view, the one-time access-gate acknowledgement, and the branded PDF.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.verification.report.customer_service import CustomerReportService
from main.app.domain.verification.report.models import CustomerReportDto
from main.appodus_utils.db.models import SuccessResponse

customer_report_router = APIRouter(prefix="/verifications", tags=["Verification Report"])
report_service: CustomerReportService = di[CustomerReportService]


@customer_report_router.get(
    "/{verification_id}/report", response_model=SuccessResponse[CustomerReportDto]
)
async def get_report(verification_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    report = await report_service.get_report(verification_id, customer_id)
    return SuccessResponse[CustomerReportDto](data=report)


@customer_report_router.post(
    "/{verification_id}/report/acknowledge", response_model=SuccessResponse[CustomerReportDto]
)
async def acknowledge_report(verification_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    report = await report_service.acknowledge(verification_id, customer_id)
    return SuccessResponse[CustomerReportDto](data=report)


@customer_report_router.get("/{verification_id}/report/pdf")
async def download_report_pdf(verification_id: str, authorize: AuthJWT = Depends()):
    """Server-side branded PDF (§10.1) — re-downloadable anytime, legal footer on every page."""
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    pdf_bytes = await report_service.render_pdf(verification_id, customer_id)
    filename = f"veriprops-report-{verification_id}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
