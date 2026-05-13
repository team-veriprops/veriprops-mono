"""Referral service — Phase 17 (S51).

Handles:
- Referral code generation (idempotent, 8-char slug)
- Claiming a referral at signup
- First-time discount + referral discount at payment initiation
- Crediting referrer when invitee completes first payment
"""
from __future__ import annotations

import random
import string
from typing import TYPE_CHECKING, Optional, Tuple

from kink import di, inject

from main.app.domain.admin_config.service import AdminConfigService
from main.app.domain.referral.models import (
    ClaimReferralDto,
    CreateReferralCodeDto,
    CreateReferralRedemptionDto,
    DiscountBreakdownDto,
    RedemptionStatus,
    ReferralCodeDto,
    ReferralStatsDto,
    UpdateReferralCodeDto,
    UpdateReferralRedemptionDto,
)
from main.app.domain.referral.repo import ReferralCodeRepo, ReferralRedemptionRepo
from main.app.domain.user.repo import UserRepo
from main.app.domain.user.models import UpdateUserDto
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ResourceNotFoundException,
    ValidationException,
)

if TYPE_CHECKING:
    from loguru import Logger

logger: "Logger" = di["logger"]

_BASE_URL = "https://veriprops.com"   # Frontend origin for referral links


def _generate_code(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class ReferralService:
    def __init__(
        self,
        code_repo: ReferralCodeRepo,
        redemption_repo: ReferralRedemptionRepo,
        user_repo: UserRepo,
        admin_config: AdminConfigService,
    ):
        self._codes = code_repo
        self._redemptions = redemption_repo
        self._users = user_repo
        self._config = admin_config

    async def get_or_create_code(self, user_id: str) -> ReferralCodeDto:
        """Return the user's existing referral code or create a new unique one."""
        row = await self._codes.get_by_owner(user_id)
        if row is None:
            # Retry up to 5 times to avoid rare collisions
            for _ in range(5):
                code = _generate_code()
                if await self._codes.get_by_code(code) is None:
                    row = await self._codes.create_return_model(
                        CreateReferralCodeDto(owner_id=user_id, code=code)
                    )
                    break
            else:
                raise ValidationException(message="Could not generate a unique referral code")
        return self._to_code_dto(row)

    async def get_my_stats(self, user_id: str) -> ReferralStatsDto:
        """Return referral stats and credit balance for the requesting user."""
        code_row = await self._codes.get_by_owner(user_id)
        user = await self._users.get_model(user_id)
        credit_balance_kobo = int(getattr(user, "credit_balance_kobo", 0) or 0)

        if code_row is None:
            return ReferralStatsDto(
                code="",
                referral_link="",
                total_invited=0,
                total_credited=0,
                pending_count=0,
                credit_balance_ngn=credit_balance_kobo / 100.0,
            )

        redemptions = await self._redemptions.list_for_code(str(code_row.id))
        credited = [r for r in redemptions if r.status == RedemptionStatus.CREDITED.value]
        pending = [r for r in redemptions if r.status == RedemptionStatus.PENDING.value]

        return ReferralStatsDto(
            code=code_row.code,
            referral_link=self._build_link(code_row.code),
            total_invited=len(redemptions),
            total_credited=len(credited),
            pending_count=len(pending),
            credit_balance_ngn=credit_balance_kobo / 100.0,
        )

    async def claim_referral(
        self, invitee_id: str, dto: ClaimReferralDto,
    ) -> None:
        """Record that an invitee signed up via a referral code.

        Idempotent — silently ignores if invitee already has a redemption.
        Rejects self-referral.
        """
        code_row = await self._codes.get_by_code(dto.code.upper())
        if code_row is None:
            raise ResourceNotFoundException(resource="ReferralCode")
        if code_row.owner_id == invitee_id:
            raise ValidationException(message="You cannot use your own referral code")

        existing = await self._redemptions.get_by_invitee(invitee_id)
        if existing:
            return  # already claimed — idempotent

        await self._redemptions.create_return_model(CreateReferralRedemptionDto(
            referral_code_id=str(code_row.id),
            invitee_id=invitee_id,
        ))
        # Increment usage counter on code
        await self._codes.update(str(code_row.id), UpdateReferralCodeDto(
            times_redeemed=(code_row.times_redeemed or 0) + 1,
        ))

    async def compute_discount(
        self,
        user_id: str,
        amount_kobo: int,
        is_first_payment: bool,
    ) -> DiscountBreakdownDto:
        """Compute applicable discounts for a payment.

        Called by PaymentService.initiate() before sending the amount to the
        payment gateway. Returns a breakdown; does NOT mutate any state yet.
        """
        first_time_pct = await self._config.get_int("first_time_discount_percent", fallback=10)
        max_pct = await self._config.get_int("max_discount_percent", fallback=20)

        redemption = await self._redemptions.get_by_invitee(user_id)
        has_pending_referral = (
            redemption is not None
            and redemption.status == RedemptionStatus.PENDING.value
        )

        first_time_discount_kobo = 0
        referral_discount_kobo = 0

        if is_first_payment:
            first_time_discount_kobo = int(amount_kobo * first_time_pct / 100)

        if is_first_payment and has_pending_referral:
            # Additional referral stacking discount (shares the same max cap)
            combined_pct = min(first_time_pct * 2, max_pct)
            total_discount_kobo = int(amount_kobo * combined_pct / 100)
            referral_discount_kobo = total_discount_kobo - first_time_discount_kobo
        else:
            total_discount_kobo = first_time_discount_kobo

        # Enforce max cap
        max_discount_kobo = int(amount_kobo * max_pct / 100)
        total_discount_kobo = min(total_discount_kobo, max_discount_kobo)
        final_amount_kobo = max(amount_kobo - total_discount_kobo, 100)  # min 1 NGN

        return DiscountBreakdownDto(
            original_amount_kobo=amount_kobo,
            first_time_discount_kobo=first_time_discount_kobo,
            referral_discount_kobo=referral_discount_kobo,
            total_discount_kobo=total_discount_kobo,
            final_amount_kobo=final_amount_kobo,
            first_time_discount_percent=float(first_time_pct),
            referral_discount_applied=has_pending_referral and is_first_payment,
        )

    async def credit_referrer_on_success(self, invitee_id: str) -> None:
        """Mark the redemption CREDITED and add credit to the referrer's balance.

        Called once from PaymentService after a payment webhook confirms success
        for the invitee's first payment.  Idempotent — if already credited, no-op.
        """
        redemption = await self._redemptions.get_by_invitee(invitee_id)
        if redemption is None:
            return  # no referral for this user — no-op
        if redemption.status == RedemptionStatus.CREDITED.value:
            return  # already credited — idempotent

        credit_ngn = await self._config.get_int("referral_credit_ngn", fallback=1000)
        credit_kobo = credit_ngn * 100

        # Mark redemption CREDITED
        await self._redemptions.update(str(redemption.id), UpdateReferralRedemptionDto(
            status=RedemptionStatus.CREDITED.value,
            credited_at=Utils.datetime_now(),
        ))

        # Add credit to referrer's balance
        code_row = await self._codes.get_model(redemption.referral_code_id)
        if code_row:
            referrer = await self._users.get_model(code_row.owner_id)
            if referrer:
                current = int(getattr(referrer, "credit_balance_kobo", 0) or 0)
                await self._users.update(code_row.owner_id, UpdateUserDto(
                    credit_balance_kobo=current + credit_kobo,
                ))

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _build_link(code: str) -> str:
        return f"{_BASE_URL}/auth/signup?ref={code}"

    @staticmethod
    def _to_code_dto(row) -> ReferralCodeDto:
        from main.app.domain.referral.service import _BASE_URL
        return ReferralCodeDto(
            id=str(row.id),
            owner_id=row.owner_id,
            code=row.code,
            times_redeemed=row.times_redeemed or 0,
            referral_link=f"{_BASE_URL}/auth/signup?ref={row.code}",
            date_created=row.date_created,
        )
