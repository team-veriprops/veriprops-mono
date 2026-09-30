"""Finance's refund-approval queue (PRD §8.5, §18.1): every return of a customer's money.

URL shape: /admin/refund-requests — REFUND_PAYMENT (Finance and super admins). Approving is the
only way a customer refund leaves; rejecting sends nothing and puts a closing case back to work.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from kink import di

from main.app.domain.payment.refund_request.approval import RefundApprovalService, RefundDecisionDto
from main.app.domain.payment.refund_request.models import (
    DecideRefundRequestDto,
    RefundRequestDto,
    RefundRequestStatus,
)
from main.app.domain.payment.refund_request.service import RefundRequestService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import Page, SuccessResponse

refund_request_router = APIRouter(prefix="/admin/refund-requests", tags=["Admin: Refund approvals"])
refund_request_service: RefundRequestService = di[RefundRequestService]
refund_approval_service: RefundApprovalService = di[RefundApprovalService]


@refund_request_router.get("", response_model=SuccessResponse[Page[RefundRequestDto]])
async def list_refund_requests(
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=100),
    status: Optional[RefundRequestStatus] = Query(default=None),
    _admin_id: str = Depends(require_permission(Permission.REFUND_PAYMENT)),
):
    """Pending requests oldest first (the queue); any other view newest first (the record)."""
    return SuccessResponse[Page[RefundRequestDto]](data=await refund_request_service.page(page, page_size, status))


@refund_request_router.post("/{request_id}/approve", response_model=SuccessResponse[RefundDecisionDto])
async def approve_refund_request(
    request_id: str, req: DecideRefundRequestDto,
    admin_id: str = Depends(require_permission(Permission.REFUND_PAYMENT)),
):
    return SuccessResponse[RefundDecisionDto](data=await refund_approval_service.approve(request_id, admin_id, req.note))


@refund_request_router.post("/{request_id}/reject", response_model=SuccessResponse[RefundDecisionDto])
async def reject_refund_request(
    request_id: str, req: DecideRefundRequestDto,
    admin_id: str = Depends(require_permission(Permission.REFUND_PAYMENT)),
):
    return SuccessResponse[RefundDecisionDto](data=await refund_approval_service.reject(request_id, admin_id, req.note))
