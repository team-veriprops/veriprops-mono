"""Closing a paid case (PRD §6.4): the quote an admin confirms, then the close.

URL shape: /admin/verifications/{id}/closure-quote and /close — MANAGE_VERIFICATIONS. The close
never sends money: a refund it owes waits for Finance (/admin/refund-requests).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from kink import di

from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.app.domain.verification.closure.models import (
    ClosureQuoteDto,
    ClosureResultDto,
    CloseCaseDto,
    CloseReason,
)
from main.app.domain.verification.closure.service import CaseClosureService
from main.appodus_utils.db.models import SuccessResponse

closure_router = APIRouter(prefix="/admin/verifications", tags=["Admin: Case closure"])
closure_service: CaseClosureService = di[CaseClosureService]


@closure_router.get("/{verification_id}/closure-quote", response_model=SuccessResponse[ClosureQuoteDto])
async def closure_quote(
    verification_id: str,
    reason: CloseReason = Query(...),
    amount_minor: Optional[int] = Query(default=None, ge=0),
    _admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    """What closing for *reason* would do: the refund, how the case ends, each agent's outcome."""
    return SuccessResponse[ClosureQuoteDto](data=await closure_service.quote(verification_id, reason, amount_minor))


@closure_router.post("/{verification_id}/close", response_model=SuccessResponse[ClosureResultDto])
async def close_case(
    verification_id: str,
    req: CloseCaseDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    return SuccessResponse[ClosureResultDto](data=await closure_service.close(verification_id, req, admin_id))
