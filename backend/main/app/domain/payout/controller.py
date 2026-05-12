"""Payout endpoints — S48."""
from __future__ import annotations

from typing import List

from fastapi import Depends

from main.app.domain.payout.models import (
    AdjustPayoutDto,
    BankAccountDto,
    CreateBankAccountDto,
    HoldPayoutDto,
    PayoutDto,
    WithdrawalRequestDto,
)
from main.app.domain.payout.service import PayoutService
from main.appodus_utils.auth.jwt import AuthJWTBearer, JWTClaims
from main.appodus_utils.response.success_response import SuccessResponse
from main.appodus_utils.router import AppRouter
from kink import di

payout_router = AppRouter(tags=["Payouts"])

_auth = AuthJWTBearer()
_finance_auth = AuthJWTBearer(required_permissions=["APPROVE_PAYOUT"])


@payout_router.get("/agent/bank-accounts", response_model=SuccessResponse[List[BankAccountDto]])
async def list_bank_accounts(claims: JWTClaims = Depends(_auth)):
    svc: PayoutService = di[PayoutService]
    items = await svc.list_bank_accounts(claims.sub)
    return SuccessResponse.ok(items)


@payout_router.post("/agent/bank-accounts", response_model=SuccessResponse[BankAccountDto])
async def add_bank_account(dto: CreateBankAccountDto, claims: JWTClaims = Depends(_auth)):
    svc: PayoutService = di[PayoutService]
    result = await svc.add_bank_account(claims.sub, dto)
    return SuccessResponse.ok(result)


@payout_router.post("/agent/payouts", response_model=SuccessResponse[PayoutDto])
async def request_withdrawal(dto: WithdrawalRequestDto, claims: JWTClaims = Depends(_auth)):
    svc: PayoutService = di[PayoutService]
    result = await svc.submit_withdrawal(claims.sub, dto)
    return SuccessResponse.ok(result)


@payout_router.get("/agent/payouts", response_model=SuccessResponse[List[PayoutDto]])
async def list_my_payouts(claims: JWTClaims = Depends(_auth)):
    svc: PayoutService = di[PayoutService]
    items = await svc.list_payouts(claims.sub)
    return SuccessResponse.ok(items)


@payout_router.get("/admin/payouts", response_model=SuccessResponse[List[PayoutDto]])
async def list_all_payouts(claims: JWTClaims = Depends(_finance_auth)):
    svc: PayoutService = di[PayoutService]
    items = await svc.list_all_payouts()
    return SuccessResponse.ok(items)


@payout_router.post("/admin/payouts/{payout_id}/approve", response_model=SuccessResponse[PayoutDto])
async def approve_payout(payout_id: str, claims: JWTClaims = Depends(_finance_auth)):
    svc: PayoutService = di[PayoutService]
    result = await svc.approve(payout_id, claims.sub)
    return SuccessResponse.ok(result)


@payout_router.post("/admin/payouts/{payout_id}/hold", response_model=SuccessResponse[PayoutDto])
async def hold_payout(payout_id: str, dto: HoldPayoutDto, claims: JWTClaims = Depends(_finance_auth)):
    svc: PayoutService = di[PayoutService]
    result = await svc.hold(payout_id, dto, claims.sub)
    return SuccessResponse.ok(result)


@payout_router.put("/admin/payouts/{payout_id}/adjust", response_model=SuccessResponse[PayoutDto])
async def adjust_payout(payout_id: str, dto: AdjustPayoutDto, claims: JWTClaims = Depends(_finance_auth)):
    svc: PayoutService = di[PayoutService]
    result = await svc.adjust(payout_id, dto, claims.sub)
    return SuccessResponse.ok(result)
