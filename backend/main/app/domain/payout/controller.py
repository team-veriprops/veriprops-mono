"""Payout controller (PRD §15.1).

Agent: /agents/payouts (JWT) — request withdrawal, history, cancel, stored bank accounts.
Finance: /admin/payouts (RBAC APPROVE_PAYOUT) — approve / hold / adjust / reject. Frontend
services: frontend/src/components/agents/payouts/libs/payout-service +
frontend/src/components/admin/finance/libs/admin-payout-service.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from kink import di
from libre_fastapi_jwt import AuthJWT

from main.app.domain.payout.bank_account.models import (
    AddBankAccountDto,
    AgentBankAccount,
    BankAccountDto,
)
from main.app.domain.payout.models import (
    PayoutDecisionDto,
    PayoutDto,
    RequestPayoutDto,
    payout_to_dto,
)
from main.app.domain.payout.service import PayoutService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.db.models import Page, SuccessResponse

payout_router = APIRouter(prefix="/agents/payouts", tags=["Agent: Payouts"])
admin_payout_router = APIRouter(prefix="/admin/payouts", tags=["Admin: Payouts (Finance)"])
payout_service: PayoutService = di[PayoutService]


def _bank_dto(a: AgentBankAccount) -> BankAccountDto:
    return BankAccountDto(
        id=a.id, bank_name=a.bank_name, account_number=a.account_number,
        account_name=a.account_name, is_default=a.is_default, date_created=a.date_created,
    )


# ── Agent ─────────────────────────────────────────────────────────

@payout_router.get("", response_model=SuccessResponse[Page[PayoutDto]])
async def my_payouts(page: int = 0, page_size: int = 10, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    return SuccessResponse[Page[PayoutDto]](data=await payout_service.page_for_agent(agent_id, page, page_size))


@payout_router.post("", response_model=SuccessResponse[PayoutDto])
async def request_payout(req: RequestPayoutDto, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    return SuccessResponse[PayoutDto](data=payout_to_dto(await payout_service.request(agent_id, req)))


@payout_router.post("/{payout_id}/cancel", response_model=SuccessResponse[PayoutDto])
async def cancel_payout(payout_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    return SuccessResponse[PayoutDto](data=payout_to_dto(await payout_service.cancel(agent_id, payout_id)))


@payout_router.get("/bank-accounts", response_model=SuccessResponse[List[BankAccountDto]])
async def my_bank_accounts(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    accounts = await payout_service.list_bank_accounts(agent_id)
    return SuccessResponse[List[BankAccountDto]](data=[_bank_dto(a) for a in accounts])


@payout_router.post("/bank-accounts", response_model=SuccessResponse[BankAccountDto])
async def add_bank_account(req: AddBankAccountDto, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    account = await payout_service.add_bank_account(agent_id, req)
    return SuccessResponse[BankAccountDto](data=_bank_dto(account))


@payout_router.delete("/bank-accounts/{account_id}", response_model=SuccessResponse[bool])
async def remove_bank_account(account_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    await payout_service.remove_bank_account(agent_id, account_id)
    return SuccessResponse[bool](data=True)


# ── Finance (APPROVE_PAYOUT) ──────────────────────────────────────

@admin_payout_router.get("", response_model=SuccessResponse[Page[PayoutDto]])
async def list_payouts(
    page: int = 0, page_size: int = 10, status: Optional[str] = None,
    _admin_id: str = Depends(require_permission(Permission.APPROVE_PAYOUT)),
):
    return SuccessResponse[Page[PayoutDto]](data=await payout_service.page_all(page, page_size, status))


@admin_payout_router.post("/{payout_id}/approve", response_model=SuccessResponse[PayoutDto])
async def approve_payout(
    payout_id: str, req: PayoutDecisionDto,
    admin_id: str = Depends(require_permission(Permission.APPROVE_PAYOUT)),
):
    return SuccessResponse[PayoutDto](data=payout_to_dto(await payout_service.approve(payout_id, admin_id, req)))


@admin_payout_router.post("/{payout_id}/hold", response_model=SuccessResponse[PayoutDto])
async def hold_payout(
    payout_id: str, req: PayoutDecisionDto,
    admin_id: str = Depends(require_permission(Permission.APPROVE_PAYOUT)),
):
    return SuccessResponse[PayoutDto](data=payout_to_dto(await payout_service.hold(payout_id, admin_id, req)))


@admin_payout_router.post("/{payout_id}/adjust", response_model=SuccessResponse[PayoutDto])
async def adjust_payout(
    payout_id: str, req: PayoutDecisionDto,
    admin_id: str = Depends(require_permission(Permission.APPROVE_PAYOUT)),
):
    return SuccessResponse[PayoutDto](data=payout_to_dto(await payout_service.adjust(payout_id, admin_id, req)))


@admin_payout_router.post("/{payout_id}/reject", response_model=SuccessResponse[PayoutDto])
async def reject_payout(
    payout_id: str, req: PayoutDecisionDto,
    admin_id: str = Depends(require_permission(Permission.APPROVE_PAYOUT)),
):
    return SuccessResponse[PayoutDto](data=payout_to_dto(await payout_service.reject(payout_id, admin_id, req)))


@admin_payout_router.post("/sweeps/commission-clearance", response_model=SuccessResponse[dict])
async def sweep_commission_clearance(
    _admin_id: str = Depends(require_permission(Permission.APPROVE_PAYOUT)),
):
    """Advance cleared commissions to available + notify agents (§15.2). Runs on a schedule
    in non-test envs; this endpoint triggers it on demand (idempotent)."""
    from main.app.domain.earnings.service import EarningsService
    advanced = await di[EarningsService].sweep_cleared()
    return SuccessResponse[dict](data={"advanced": advanced})
