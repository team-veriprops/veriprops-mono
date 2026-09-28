"""Payout controller (PRD §15.1).

Agent: /agents/payouts (JWT) — banks and account resolution, fee quote, request withdrawal,
history, cancel, stored bank accounts.
Finance: /admin/payouts (RBAC APPROVE_PAYOUT) — approve / hold / adjust / reject / retry, the
disbursement queue, and the disburse button. Frontend services:
frontend/src/components/agents/payouts/libs/payout-service +
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
    BankDto,
    ResolveBankAccountDto,
    ResolvedBankAccountDto,
)
from main.app.domain.payout.disbursement import PayoutDisbursementService
from main.app.domain.payout.models import (
    AdminPayoutDto,
    DisbursementOutcomeDto,
    DisbursementQueueDto,
    PayoutDecisionDto,
    PayoutDto,
    PayoutQuoteDto,
    QuotePayoutDto,
    RequestPayoutDto,
    admin_payout_to_dto,
    payout_to_dto,
)
from main.app.domain.payout.service import PayoutService
from main.app.domain.user.auth.utils.permissions import Permission, require_permission
from main.appodus_utils.common.rate_limit import RateLimiter
from main.appodus_utils.db.models import Page, SuccessResponse

payout_router = APIRouter(prefix="/agents/payouts", tags=["Agent: Payouts"])
admin_payout_router = APIRouter(prefix="/admin/payouts", tags=["Admin: Payouts (Finance)"])
payout_service: PayoutService = di[PayoutService]
disbursement_service: PayoutDisbursementService = di[PayoutDisbursementService]

# An account lookup reveals whose account a number is: enough for saving one's own accounts,
# too few to walk a bank's number range.
_resolve_rate_limit = RateLimiter(scope="bank_account_resolve", limit=10, window_seconds=60)


def _bank_dto(a: AgentBankAccount) -> BankAccountDto:
    return BankAccountDto(
        id=a.id, bank_name=a.bank_name, bank_code=a.bank_code, account_number=a.account_number,
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


@payout_router.post("/quote", response_model=SuccessResponse[PayoutQuoteDto])
async def quote_payout(req: QuotePayoutDto, authorize: AuthJWT = Depends()):
    """The transfer fee on a withdrawal, and what would reach the bank."""
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    return SuccessResponse[PayoutQuoteDto](data=await payout_service.quote(agent_id, req))


@payout_router.post("/{payout_id}/cancel", response_model=SuccessResponse[PayoutDto])
async def cancel_payout(payout_id: str, authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    return SuccessResponse[PayoutDto](data=payout_to_dto(await payout_service.cancel(agent_id, payout_id)))


@payout_router.get("/banks", response_model=SuccessResponse[List[BankDto]])
async def list_banks(authorize: AuthJWT = Depends()):
    """The banks an account can be saved with, from the paying gateway's own list."""
    await authorize.jwt_required()
    return SuccessResponse[List[BankDto]](data=await payout_service.list_banks())


@payout_router.post("/bank-accounts/resolve", response_model=SuccessResponse[ResolvedBankAccountDto])
async def resolve_bank_account(
    req: ResolveBankAccountDto, authorize: AuthJWT = Depends(), _: None = Depends(_resolve_rate_limit),
):
    """The name the bank holds for an account, shown before the agent saves it."""
    await authorize.jwt_required()
    return SuccessResponse[ResolvedBankAccountDto](data=await payout_service.resolve_bank_account(req))


@payout_router.get("/bank-accounts", response_model=SuccessResponse[List[BankAccountDto]])
async def my_bank_accounts(authorize: AuthJWT = Depends()):
    await authorize.jwt_required()
    agent_id = str(authorize.get_jwt_subject())
    accounts = await payout_service.list_bank_accounts(agent_id)
    return SuccessResponse[List[BankAccountDto]](data=[_bank_dto(a) for a in accounts])


@payout_router.post("/bank-accounts", response_model=SuccessResponse[BankAccountDto])
async def add_bank_account(
    req: AddBankAccountDto, authorize: AuthJWT = Depends(), _: None = Depends(_resolve_rate_limit),
):
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

@admin_payout_router.get("", response_model=SuccessResponse[Page[AdminPayoutDto]])
async def list_payouts(
    page: int = 0, page_size: int = 10, status: Optional[str] = None,
    _admin_id: str = Depends(require_permission(Permission.APPROVE_PAYOUT)),
):
    return SuccessResponse[Page[AdminPayoutDto]](data=await payout_service.page_all(page, page_size, status))


@admin_payout_router.get("/disbursement-queue", response_model=SuccessResponse[DisbursementQueueDto])
async def disbursement_queue(_admin_id: str = Depends(require_permission(Permission.APPROVE_PAYOUT))):
    """Approved payouts waiting for the next batch, and the gateway balance they will draw."""
    return SuccessResponse[DisbursementQueueDto](data=await payout_service.disbursement_queue())


@admin_payout_router.post("/disburse", response_model=SuccessResponse[DisbursementOutcomeDto])
async def disburse(admin_id: str = Depends(require_permission(Permission.APPROVE_PAYOUT))):
    """Send approved payouts now — the same batch the daily sweep runs. Bounded per call;
    ``remaining`` says how many are still waiting."""
    return SuccessResponse[DisbursementOutcomeDto](data=await disbursement_service.run(actor_id=admin_id))


@admin_payout_router.post("/{payout_id}/approve", response_model=SuccessResponse[AdminPayoutDto])
async def approve_payout(
    payout_id: str, req: PayoutDecisionDto,
    admin_id: str = Depends(require_permission(Permission.APPROVE_PAYOUT)),
):
    return SuccessResponse[AdminPayoutDto](data=admin_payout_to_dto(await payout_service.approve(payout_id, admin_id, req)))


@admin_payout_router.post("/{payout_id}/hold", response_model=SuccessResponse[AdminPayoutDto])
async def hold_payout(
    payout_id: str, req: PayoutDecisionDto,
    admin_id: str = Depends(require_permission(Permission.APPROVE_PAYOUT)),
):
    return SuccessResponse[AdminPayoutDto](data=admin_payout_to_dto(await payout_service.hold(payout_id, admin_id, req)))


@admin_payout_router.post("/{payout_id}/adjust", response_model=SuccessResponse[AdminPayoutDto])
async def adjust_payout(
    payout_id: str, req: PayoutDecisionDto,
    admin_id: str = Depends(require_permission(Permission.APPROVE_PAYOUT)),
):
    return SuccessResponse[AdminPayoutDto](data=admin_payout_to_dto(await payout_service.adjust(payout_id, admin_id, req)))


@admin_payout_router.post("/{payout_id}/reject", response_model=SuccessResponse[AdminPayoutDto])
async def reject_payout(
    payout_id: str, req: PayoutDecisionDto,
    admin_id: str = Depends(require_permission(Permission.APPROVE_PAYOUT)),
):
    return SuccessResponse[AdminPayoutDto](data=admin_payout_to_dto(await payout_service.reject(payout_id, admin_id, req)))


@admin_payout_router.post("/{payout_id}/retry", response_model=SuccessResponse[AdminPayoutDto])
async def retry_payout(
    payout_id: str, admin_id: str = Depends(require_permission(Permission.APPROVE_PAYOUT)),
):
    """Send a failed transfer again, in the next batch, under a new reference."""
    return SuccessResponse[AdminPayoutDto](data=admin_payout_to_dto(await payout_service.retry(payout_id, admin_id)))


@admin_payout_router.post("/sweeps/commission-clearance", response_model=SuccessResponse[dict])
async def sweep_commission_clearance(
    _admin_id: str = Depends(require_permission(Permission.APPROVE_PAYOUT)),
):
    """Advance cleared commissions to available + notify agents (§15.2). Runs on a schedule
    in non-test envs; this endpoint triggers it on demand (idempotent)."""
    from main.app.domain.earnings.service import EarningsService
    advanced = await di[EarningsService].sweep_cleared()
    return SuccessResponse[dict](data={"advanced": advanced})
