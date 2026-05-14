"""Commission endpoints — S47."""
from __future__ import annotations

from typing import List, Optional

from fastapi import Depends, Query

from main.app.domain.commission.models import (
    CommissionPreviewDto,
    CommissionRuleDto,
    CreateCommissionRuleDto,
    EarningDto,
    EarningsSummaryDto,
    UpdateCommissionRuleDto,
)
from main.app.domain.commission.service import CommissionService
from main.appodus_utils.auth.jwt import AuthJWTBearer, JWTClaims
from main.appodus_utils.db.models import Page
from main.appodus_utils.response.success_response import SuccessResponse
from main.appodus_utils.router import AppRouter
from kink import di

commission_router = AppRouter(tags=["Commission"])

_auth = AuthJWTBearer()
_admin_auth = AuthJWTBearer(required_permissions=["MANAGE_VERIFICATIONS"])
_finance_auth = AuthJWTBearer(required_permissions=["APPROVE_PAYOUT"])


@commission_router.get("/agent/earnings", response_model=SuccessResponse[EarningsSummaryDto])
async def get_earnings_summary(claims: JWTClaims = Depends(_auth)):
    svc: CommissionService = di[CommissionService]
    summary = await svc.get_earnings_summary(claims.sub)
    return SuccessResponse.ok(summary)


@commission_router.get("/agent/earnings/jobs", response_model=SuccessResponse[List[EarningDto]])
async def list_earnings(claims: JWTClaims = Depends(_auth)):
    svc: CommissionService = di[CommissionService]
    items = await svc.list_earnings(claims.sub)
    return SuccessResponse.ok(items)


@commission_router.get("/admin/commission-rules", response_model=SuccessResponse[List[CommissionRuleDto]])
async def list_rules(claims: JWTClaims = Depends(_admin_auth)):
    svc: CommissionService = di[CommissionService]
    rules = await svc.list_rules()
    return SuccessResponse.ok(rules)


@commission_router.post("/admin/commission-rules", response_model=SuccessResponse[CommissionRuleDto])
async def create_rule(dto: CreateCommissionRuleDto, claims: JWTClaims = Depends(_admin_auth)):
    svc: CommissionService = di[CommissionService]
    rule = await svc.create_rule(dto)
    return SuccessResponse.ok(rule)


@commission_router.put("/admin/commission-rules/{rule_id}", response_model=SuccessResponse[CommissionRuleDto])
async def update_rule(rule_id: str, dto: UpdateCommissionRuleDto, claims: JWTClaims = Depends(_admin_auth)):
    svc: CommissionService = di[CommissionService]
    rule = await svc.update_rule(rule_id, dto)
    return SuccessResponse.ok(rule)


@commission_router.get("/admin/commission/breakdown", response_model=Page[EarningDto])
async def admin_commission_breakdown(
    agent_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(0, ge=0),
    page_size: int = Query(25, ge=1, le=100),
    _: JWTClaims = Depends(_finance_auth),
):
    svc: CommissionService = di[CommissionService]
    return await svc.admin_list_earnings(
        agent_id=agent_id, status=status, page=page, page_size=page_size,
    )
