"""Agent application HTTP routes — PRD Phase 3.

URL shape: `/users/agents/...`

Authenticated user routes are gated by JWT presence. Admin routes are gated by
`require_permission(Permission.APPROVE_AGENT)` per PRD §4.1 RBAC.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

import json
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.config.settings import settings
from main.app.domain.user.agent.kyc.models import AdminKycReviewDto, KycRecordDto
from main.app.domain.user.agent.kyc.webhook import validate_dojah_signature
from main.app.domain.user.agent.models import (
    AdminAgentApplicationDto,
    AgentApplicationDto,
    AgentApplicationStatus,
    BvnVerifyDto,
    BvnVerificationResultDto,
    CredentialsStepDto,
    KycDocumentsDto,
    RejectApplicationDto,
    SubmitApplicationDto,
    TypesStepDto,
)
from main.app.domain.user.agent.service import AgentApplicationService
from main.app.domain.user.auth.utils.permissions import (
    Permission,
    require_permission,
)
from main.appodus_utils.common.client_utils import ClientUtils
from main.appodus_utils.db.models import Page, SuccessResponse
from main.appodus_utils.exception.exceptions import ForbiddenException

logger: Logger = di["logger"]

agent_service: AgentApplicationService = di[AgentApplicationService]

agent_router = APIRouter(prefix="/agents", tags=["Agents"])


# ─── Applicant-facing routes ─────────────────────────────────────

@agent_router.get("/me/application", response_model=SuccessResponse[AgentApplicationDto])
async def get_my_application(authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    dto = await agent_service.get_or_create_for_user(user_id)
    return SuccessResponse[AgentApplicationDto](data=dto)


@agent_router.post("/me/application/types", response_model=SuccessResponse[AgentApplicationDto])
async def update_types(req: TypesStepDto, authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    dto = await agent_service.update_types(user_id, req)
    return SuccessResponse[AgentApplicationDto](data=dto)


@agent_router.post("/me/application/kyc/bvn", response_model=SuccessResponse[BvnVerificationResultDto])
async def verify_bvn(req: BvnVerifyDto, authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    result = await agent_service.verify_bvn(user_id, req)
    return SuccessResponse[BvnVerificationResultDto](data=result)


@agent_router.post("/me/application/kyc/documents", response_model=SuccessResponse[AgentApplicationDto])
async def record_kyc_documents(req: KycDocumentsDto, authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    dto = await agent_service.record_kyc_documents(user_id, req)
    return SuccessResponse[AgentApplicationDto](data=dto)


@agent_router.post("/me/application/credentials", response_model=SuccessResponse[AgentApplicationDto])
async def update_credentials(req: CredentialsStepDto, authorize: AuthJWT = Depends()):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    dto = await agent_service.update_credentials(user_id, req)
    return SuccessResponse[AgentApplicationDto](data=dto)


@agent_router.post("/me/application/submit", response_model=SuccessResponse[AgentApplicationDto])
async def submit_application(
    req: SubmitApplicationDto, request: Request, authorize: AuthJWT = Depends(),
):
    authorize.jwt_required()
    user_id = authorize.get_jwt_subject()
    dto = await agent_service.submit(
        user_id,
        req,
        ip_address=ClientUtils.get_client_ip(request),
        device_fingerprint=request.headers.get("X-Device-Fingerprint"),
    )
    return SuccessResponse[AgentApplicationDto](data=dto)


# ─── KYC webhook (no auth — validated by HMAC) ───────────────────

@agent_router.post("/kyc/webhook")
async def kyc_webhook(request: Request):
    body = await request.body()
    sig = request.headers.get("X-Dojah-Signature", "")
    if not validate_dojah_signature(body, sig, settings.DOJAH_WEBHOOK_SECRET):
        raise ForbiddenException("invalid webhook signature")
    payload = json.loads(body)
    await agent_service.process_kyc_webhook(payload)
    return {"received": True}


# ─── Admin routes ─────────────────────────────────────────────────

@agent_router.get(
    "/admin/applications",
    response_model=Page[AdminAgentApplicationDto],
)
async def admin_list_applications(
    status: Optional[AgentApplicationStatus] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _: str = Depends(require_permission(Permission.APPROVE_AGENT)),
):
    return await agent_service.list_for_admin(status=status, page=page, page_size=page_size)


@agent_router.post(
    "/admin/applications/{application_id}/approve",
    response_model=SuccessResponse[AgentApplicationDto],
)
async def admin_approve(
    application_id: str,
    admin_id: str = Depends(require_permission(Permission.APPROVE_AGENT)),
):
    dto = await agent_service.approve(application_id, admin_id)
    return SuccessResponse[AgentApplicationDto](data=dto)


@agent_router.post(
    "/admin/applications/{application_id}/reject",
    response_model=SuccessResponse[AgentApplicationDto],
)
async def admin_reject(
    application_id: str,
    req: RejectApplicationDto,
    admin_id: str = Depends(require_permission(Permission.APPROVE_AGENT)),
):
    dto = await agent_service.reject(application_id, admin_id, req.reason)
    return SuccessResponse[AgentApplicationDto](data=dto)


@agent_router.get(
    "/admin/kyc/review",
    response_model=Page[KycRecordDto],
)
async def admin_list_kyc_under_review(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _: str = Depends(require_permission(Permission.APPROVE_AGENT)),
):
    return await agent_service.list_kyc_under_review(page=page, page_size=page_size)


@agent_router.post(
    "/admin/kyc/{record_id}/review",
    response_model=SuccessResponse[KycRecordDto],
)
async def admin_review_kyc(
    record_id: str,
    req: AdminKycReviewDto,
    admin_id: str = Depends(require_permission(Permission.APPROVE_AGENT)),
):
    dto = await agent_service.admin_review_kyc(record_id, admin_id, req)
    return SuccessResponse[KycRecordDto](data=dto)
