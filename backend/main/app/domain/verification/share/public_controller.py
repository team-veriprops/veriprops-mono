"""Public (unauthenticated) lookup + share controller (PRD §13.1, §13.2).

URL shape: /public/... — **no JWT**. The VID (public lookup) or the share token is the only
authorization. Every response is summary-only unless a named-recipient token unlocks the full
report after a disclaimer acknowledgement. Frontend: /verify/[vid] and /shared/[token].
"""
from __future__ import annotations

from fastapi import APIRouter
from kink import di

from main.app.domain.verification.share.models import PublicSummaryDto, SharedReportDto
from main.app.domain.verification.share.service import ShareService
from main.appodus_utils.db.models import SuccessResponse

public_share_router = APIRouter(prefix="/public", tags=["Public Lookup & Sharing"])
share_service: ShareService = di[ShareService]


@public_share_router.get(
    "/verify/{vid}", response_model=SuccessResponse[PublicSummaryDto]
)
async def public_lookup(vid: str):
    """Unauthenticated VID lookup (§13.1) — summary only, never the numeric score/address."""
    summary = await share_service.public_lookup(vid)
    return SuccessResponse[PublicSummaryDto](data=summary)


@public_share_router.get(
    "/shared/{token}", response_model=SuccessResponse[SharedReportDto]
)
async def resolve_shared(token: str):
    """Resolve a share token (§13.2). Summary for a link; full report for a named recipient
    after the disclaimer is acknowledged. Revoked/expired tokens read as not-found (§13.3)."""
    view = await share_service.resolve_shared(token)
    return SuccessResponse[SharedReportDto](data=view)


@public_share_router.post(
    "/shared/{token}/acknowledge", response_model=SuccessResponse[SharedReportDto]
)
async def acknowledge_shared(token: str):
    """Record a named recipient's one-time disclaimer acknowledgement, then return the report."""
    view = await share_service.acknowledge_shared(token)
    return SuccessResponse[SharedReportDto](data=view)
