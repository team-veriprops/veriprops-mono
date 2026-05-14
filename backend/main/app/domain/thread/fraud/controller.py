"""Admin fraud-flag review endpoints (S38 / S57)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from kink import di

from main.app.domain.thread.fraud.models import FraudFlagDto, FraudFlagHistoryPageDto, ReviewFraudFlagDto
from main.app.domain.thread.fraud.service import FraudDetectionService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import SuccessResponse

fraud_router = APIRouter(prefix="/admin/fraud-flags", tags=["Admin — Fraud Flags"])
fraud_svc: FraudDetectionService = di[FraudDetectionService]


@fraud_router.get("", response_model=SuccessResponse[List[FraudFlagDto]])
async def list_pending_flags(
    _: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    flags = await fraud_svc.list_pending()
    return SuccessResponse.ok(flags)


@fraud_router.get("/history", response_model=SuccessResponse[FraudFlagHistoryPageDto])
async def list_fraud_flag_history(
    reviewed: Optional[bool] = Query(default=None),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=20, ge=1, le=100),
    _: str = Depends(require_permission(Permission.VIEW_ADMIN_PANEL)),
):
    result = await fraud_svc.list_history(
        reviewed=reviewed,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return SuccessResponse.ok(result)


@fraud_router.post("/{flag_id}/review", response_model=SuccessResponse[FraudFlagDto])
async def review_flag(
    flag_id: str,
    body: ReviewFraudFlagDto,
    admin_id: str = Depends(require_permission(Permission.MANAGE_VERIFICATIONS)),
):
    flag = await fraud_svc.review(flag_id, body, reviewer_id=admin_id)
    return SuccessResponse.ok(flag)
