"""Earnings controller (PRD §15.1).

Agent-facing earnings dashboard. URL shape: /agents/earnings. Frontend service:
frontend/src/components/agents/earnings/libs/earnings-service.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.earnings.models import EarningJobDto, EarningsSummaryDto
from main.app.domain.earnings.service import EarningsService
from main.appodus_utils.db.models import Page, SuccessResponse

earnings_router = APIRouter(prefix="/agents/earnings", tags=["Agent: Earnings"])
earnings_service: EarningsService = di[EarningsService]


@earnings_router.get("", response_model=SuccessResponse[EarningsSummaryDto])
async def my_earnings(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    return SuccessResponse[EarningsSummaryDto](data=await earnings_service.summary(agent_id))


@earnings_router.get("/jobs", response_model=SuccessResponse[Page[EarningJobDto]])
async def my_earning_jobs(page: int = 0, page_size: int = 10, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    return SuccessResponse[Page[EarningJobDto]](
        data=await earnings_service.jobs_page(agent_id, page, page_size)
    )
