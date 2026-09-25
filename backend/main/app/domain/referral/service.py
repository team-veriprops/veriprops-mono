"""Referral service (PRD §17.1, D34/D35).

Owns the shareable link, the signup linkage, the anti-farming gate, and the two-stage
referral-credit lifecycle. A credit is created PENDING on the invitee's first payment and
only clears to the referrer's spendable ``credit_balance_kobo`` after the payment passes
the chargeback window (§15.2) — closing the refer-then-charge-back loop.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from kink import inject

from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.domain.payment.models import Payment
from main.app.domain.payment.repo import PaymentRepo
from main.app.domain.referral.credit.models import (
    CreateReferralCreditDto,
    ReferralCredit,
    ReferralCreditDto,
    ReferralCreditStatus,
)
from main.app.domain.referral.credit.repo import ReferralCreditRepo
from main.app.domain.referral.models import (
    CreateReferralDto,
    Referral,
    ReferralSummaryDto,
)
from main.app.domain.referral.repo import ReferralRepo
from main.app.domain.system_config.models import ConfigKey
from main.app.domain.system_config.service import ConfigService
from main.app.domain.user.service import UserService
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional

_CODE_LENGTH = 8
_KOBO_PER_NGN = 100


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class ReferralService:
    def __init__(
        self,
        referral_repo: ReferralRepo,
        referral_credit_repo: ReferralCreditRepo,
        payment_repo: PaymentRepo,
        user_service: UserService,
        config_service: ConfigService,
    ):
        self._referrals = referral_repo
        self._credits = referral_credit_repo
        self._payments = payment_repo
        self._users = user_service
        self._config = config_service

    # ── Link ──────────────────────────────────────────────────────

    async def get_or_create_link(self, user_id: str) -> Referral:
        """The user's referral link, created on first use. Runs on a page load, so two tabs
        opening at once must converge on one link rather than race into the constraint."""
        existing = await self._referrals.get_for_referrer(user_id)
        if existing is not None:
            return existing
        link, _ = await self._referrals.insert_or_get(
            CreateReferralDto(referrer_user_id=user_id, code=await self._unique_code()).model_dump(by_alias=False),
            ["referrer_user_id"],
        )
        return link

    async def resolve_referrer_id(self, code: str) -> Optional[str]:
        """The referrer's user id for a referral code, or None if the code is unknown
        (an invalid ``?ref=`` never blocks signup — it is simply ignored)."""
        if not code:
            return None
        referral = await self._referrals.get_by_code(code.strip().upper())
        return referral.referrer_user_id if referral is not None else None

    async def summary(self, user_id: str) -> ReferralSummaryDto:
        link = await self.get_or_create_link(user_id)
        credits = await self._credits.list_for_referrer(user_id)
        pending = sum(c.amount_minor for c in credits if c.status == ReferralCreditStatus.PENDING.value)
        lifetime = sum(c.amount_minor for c in credits if c.status == ReferralCreditStatus.CLEARED.value)
        user = await self._users.get_user_model(user_id)
        reward_ngn = await self._config.get_int(ConfigKey.REFERRAL_CREDIT_NGN)
        return ReferralSummaryDto(
            code=link.code,
            share_path=f"/auth/signup?ref={link.code}",
            referral_credit_ngn=reward_ngn,
            available_credit_minor=user.credit_balance_kobo or 0,
            pending_credit_minor=pending,
            lifetime_credit_minor=lifetime,
            credits=[self._credit_dto(c) for c in credits],
        )

    # ── Credit lifecycle ──────────────────────────────────────────

    async def on_invitee_first_payment(self, payment: Payment) -> Optional[ReferralCredit]:
        """Record a referral credit for the referrer when a referred invitee first pays.

        Anti-farming (§17.1, D34): a referrer and invitee sharing a verified phone or a
        card fingerprint are the same human — the credit is voided, not paid. Idempotent:
        a second call for the same invitee is a no-op (a credit is earned once, on the
        invitee's first payment). Best-effort — never raises into the payment webhook.
        """
        invitee = await self._users.get_user_model(payment.customer_id)
        referrer_id = getattr(invitee, "referred_by", None)
        if not referrer_id:
            return None
        # One credit per invitee — their first payment. Guards replays + later payments.
        if await self._credits.get_for_invitee(Utils.uuid_to_hex(invitee.id)) is not None:
            return None

        void_reason = await self._anti_farming_reason(invitee, referrer_id, payment)
        amount_minor = await self._config.get_int(ConfigKey.REFERRAL_CREDIT_NGN) * _KOBO_PER_NGN
        window_days = await self._config.get_int(ConfigKey.CHARGEBACK_WINDOW_DAYS)
        clearing_until = Utils.datetime_now() + timedelta(days=window_days)

        # One credit per invitee, enforced by the insert: a concurrent payment webhook for the
        # same invitee can't mint a second.
        credit, created = await self._credits.insert_or_get(
            CreateReferralCreditDto(
                referrer_user_id=referrer_id,
                invitee_user_id=Utils.uuid_to_hex(invitee.id),
                verification_id=payment.verification_id,
                amount_minor=amount_minor,
                status=ReferralCreditStatus.VOID if void_reason else ReferralCreditStatus.PENDING,
                clearing_until=None if void_reason else clearing_until,
                void_reason=void_reason,
            ).model_dump(by_alias=False),
            unique_index="uq_referral_credits_invitee",
        )
        return credit if created else None

    async def sweep_referral_credits(self) -> int:
        """Clear PENDING credits whose chargeback window has passed (§17.1): add the amount
        to the referrer's spendable balance and notify them once. Idempotent — a CLEARED row
        is never revisited. Returns the number of credits cleared."""
        now = Utils.datetime_now()
        cleared = 0
        for credit in await self._credits.list_pending_due(now):
            # Claimed first: an overlapping sweep that listed the same credit finds it
            # CLEARED and skips it, so the balance is credited once.
            row = await self._credits.claim_transition(
                credit.id, [ReferralCreditStatus.PENDING], ReferralCreditStatus.CLEARED, cleared_at=now,
            )
            if row is None:
                continue
            await self._users.add_credit_balance(row.referrer_user_id, row.amount_minor)
            cleared += 1
            await publish_domain_event(DomainEvent(
                type=EventType.REFERRAL_CREDIT_EARNED,
                recipient_user_ids=(row.referrer_user_id,),
                data={"amount_minor": row.amount_minor},
            ))
        return cleared

    # ── helpers ───────────────────────────────────────────────────

    async def _anti_farming_reason(self, invitee, referrer_id: str, payment: Payment) -> Optional[str]:
        if Utils.uuid_to_hex(invitee.id) == referrer_id or str(invitee.id) == referrer_id:
            return "self_referral"
        referrer = await self._users.get_user_model(referrer_id)
        if referrer is None:
            return None
        if (
            invitee.phone_verified and referrer.phone_verified
            and invitee.phone_e164 and invitee.phone_e164 == referrer.phone_e164
        ):
            return "duplicate_phone"
        if payment.card_fingerprint:
            referrer_fingerprints = await self._payments.list_card_fingerprints_for_customer(referrer_id)
            if payment.card_fingerprint in referrer_fingerprints:
                return "duplicate_card"
        return None

    async def _unique_code(self) -> str:
        for _ in range(5):
            code = Utils.random_str(_CODE_LENGTH).upper()
            if await self._referrals.get_by_code(code) is None:
                return code
        # Astronomically unlikely; widen the entropy on the final attempt.
        return Utils.random_str(_CODE_LENGTH + 4).upper()

    @staticmethod
    def _credit_dto(c: ReferralCredit) -> ReferralCreditDto:
        return ReferralCreditDto(
            id=c.id, invitee_user_id=c.invitee_user_id, verification_id=c.verification_id,
            amount_minor=c.amount_minor, status=ReferralCreditStatus(c.status),
            clearing_until=c.clearing_until, cleared_at=c.cleared_at, date_created=c.date_created,
        )
