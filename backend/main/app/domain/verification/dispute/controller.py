"""Dispute controller (PRD §14.3).

Customer: /verifications/{id}/disputes (JWT-owned). Agent defence: /agents/disputes/{id}/defence
(JWT agent). Admin: /admin/disputes (RBAC RESOLVE_DISPUTE). Frontend services:
frontend/src/components/{portal,agents,admin}/libs/dispute-service.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.app.domain.verification.dispute.models import (
    AgentDefenceDto,
    DisputeDto,
    OpenDisputeDto,
    ResolveDisputeDto,
    dispute_to_dto as _to_dto,
)
from main.app.domain.verification.dispute.service import DisputeService
from main.appodus_utils.db.models import Page, SuccessResponse

dispute_router = APIRouter(prefix="/verifications", tags=["Verification Dispute"])
agent_dispute_router = APIRouter(prefix="/agents/disputes", tags=["Agent: Dispute Defence"])
admin_dispute_router = APIRouter(prefix="/admin/disputes", tags=["Admin: Disputes"])
dispute_service: DisputeService = di[DisputeService]


# ── Customer ──────────────────────────────────────────────────────

@dispute_router.post("/{verification_id}/disputes", response_model=SuccessResponse[DisputeDto])
async def open_dispute(verification_id: str, req: OpenDisputeDto, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    dispute = await dispute_service.open(verification_id, customer_id, req)
    return SuccessResponse[DisputeDto](data=_to_dto(dispute))


@dispute_router.get("/{verification_id}/disputes", response_model=SuccessResponse[List[DisputeDto]])
async def list_disputes(verification_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    customer_id = str(authorize.get_jwt_subject())
    rows = await dispute_service.list_for_verification(verification_id, customer_id)
    return SuccessResponse[List[DisputeDto]](data=[_to_dto(d) for d in rows])


# ── Agent defence (admin-mediated) ────────────────────────────────

@agent_dispute_router.get("", response_model=SuccessResponse[List[DisputeDto]])
async def my_open_disputes(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    rows = await dispute_service.list_open_for_agent(agent_id)
    return SuccessResponse[List[DisputeDto]](data=[_to_dto(d) for d in rows])


@agent_dispute_router.post("/{dispute_id}/defence", response_model=SuccessResponse[DisputeDto])
async def submit_defence(dispute_id: str, req: AgentDefenceDto, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    dispute = await dispute_service.agent_defend(dispute_id, agent_id, req.text)
    return SuccessResponse[DisputeDto](data=_to_dto(dispute))


# ── Admin ─────────────────────────────────────────────────────────

@admin_dispute_router.get("", response_model=SuccessResponse[Page[DisputeDto]])
async def list_open(
    page: int = 0, page_size: int = 10,
    _admin_id: str = Depends(require_permission(Permission.RESOLVE_DISPUTE)),
):
    return SuccessResponse[Page[DisputeDto]](data=await dispute_service.page_open(page, page_size))


@admin_dispute_router.get("/{dispute_id}", response_model=SuccessResponse[DisputeDto])
async def get_dispute(
    dispute_id: str, _admin_id: str = Depends(require_permission(Permission.RESOLVE_DISPUTE)),
):
    return SuccessResponse[DisputeDto](data=_to_dto(await dispute_service.get(dispute_id)))


@admin_dispute_router.post("/{dispute_id}/resolve", response_model=SuccessResponse[DisputeDto])
async def resolve_dispute(
    dispute_id: str, req: ResolveDisputeDto,
    admin_id: str = Depends(require_permission(Permission.RESOLVE_DISPUTE)),
):
    dispute = await dispute_service.resolve(dispute_id, req, admin_id)
    return SuccessResponse[DisputeDto](data=_to_dto(dispute))
