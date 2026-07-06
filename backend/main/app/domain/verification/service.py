"""Verification service (PRD §5, §4.4).

Owns the resumable submission wizard (VID/DRAFT on step-1 load), pricing + 24h
price-lock, the VERIFICATION_TERMS consent snapshot, and the lifecycle transitions
DRAFT → SUBMITTED → PAYMENT_PENDING → PAID. Every status write is validated by the
verification state machine; post-payment status is projected by the derivation owner.
"""
from __future__ import annotations

import json
from datetime import timedelta
from typing import Optional

from kink import inject

from main.app.core.idempotency.service import IdempotencyService
from main.app.core.realtime import VerificationEventType
from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.core.sla import sla_due_date
from main.app.core.state.machine import verification_state_machine
from main.app.core.state.status import VerificationStatus, VerificationTier
from main.app.core.vid import generate_vid
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.property.service import PropertyService
from main.app.domain.system_config.models import ConfigKey
from main.app.domain.system_config.service import ConfigService
from main.app.domain.user.auth.consent.models import ConsentDocumentType
from main.app.domain.user.auth.consent.service import ConsentService
from main.app.domain.user.models import UpdateUserDto
from main.app.domain.user.service import UserService
from main.app.domain.verification.models import (
    CreateVerificationDto,
    PriceQuoteDto,
    PriceRefreshDto,
    SaveVerificationDraftDto,
    SubmitVerificationDto,
    UpdateVerificationDto,
    Verification,
)
from main.app.domain.verification.pricing import Discount, apply_discounts, indicative_charge_minor, price_ngn_kobo
from main.app.domain.verification.repo import VerificationRepo
from main.appodus_utils import Utils
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ForbiddenException, ResourceNotFoundException

_CREATE_SCOPE = "verification.create"
_PRICE_LOCK_HOURS = 24
_ABANDONMENT_AGE_HOURS = 24


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class VerificationService:
    def __init__(
        self,
        verification_repo: VerificationRepo,
        property_service: PropertyService,
        consent_service: ConsentService,
        idempotency_service: IdempotencyService,
        audit_service: AuditLogService,
        config_service: ConfigService,
        user_service: UserService,
    ):
        self._repo = verification_repo
        self._property_service = property_service
        self._consent_service = consent_service
        self._idempotency = idempotency_service
        self._audit = audit_service
        self._config = config_service
        self._users = user_service

    # ── Draft (VID/DRAFT on step-1 load; idempotent create) ───────

    async def create_draft(self, customer_id: str, idempotency_key: Optional[str] = None) -> Verification:
        if idempotency_key:
            outcome = await self._idempotency.begin_or_replay(idempotency_key, _CREATE_SCOPE)
            if outcome.is_replay and outcome.resource_id:
                existing = await self._repo.get_model(outcome.resource_id)
                if existing:
                    return existing

        verification = await self._repo.create_return_model(CreateVerificationDto(
            vid=generate_vid(),
            customer_id=customer_id,
            status=VerificationStatus.DRAFT,
        ))
        if idempotency_key:
            await self._idempotency.complete(idempotency_key, resource_id=verification.id)
        return verification

    async def save_draft(self, verification_id: str, customer_id: str, dto: SaveVerificationDraftDto) -> Verification:
        verification = await self._require_owned(verification_id, customer_id)
        await self._repo.update(verification_id, UpdateVerificationDto(
            draft_step=dto.step,
            draft_payload=json.dumps(dto.payload),
        ))
        return await self._repo.get_model(verification_id)

    async def get_owned(self, verification_id: str, customer_id: str) -> Verification:
        return await self._require_owned(verification_id, customer_id)

    async def get_by_id(self, verification_id: str) -> Verification:
        """Ownership-free fetch for internal service callers (e.g. tokenised report shares,
        where the share token — not the JWT — is the authorization)."""
        verification = await self._repo.get_model(verification_id)
        if not verification:
            raise ResourceNotFoundException(resource="verification")
        return verification

    # ── Pricing quote (PRD §5.2, §17.1 discounts) ─────────────────

    async def quote(
        self, customer_id: str, tier: VerificationTier, currency: TransactionCurrency
    ) -> PriceQuoteDto:
        ngn = price_ngn_kobo(tier)
        discount = await self._compute_discount(customer_id, ngn)
        # The foreign figure is indicative on the NET amount the customer will be charged.
        charge_minor, fx = indicative_charge_minor(discount.net_minor, currency)
        return PriceQuoteDto(
            tier=tier,
            price_ngn_minor=ngn,
            currency=currency,
            charge_amount_minor=charge_minor,
            fx_rate=fx,
            first_time_discount_minor=discount.first_time_minor,
            referral_credit_applied_minor=discount.referral_applied_minor,
            total_discount_minor=discount.total_discount_minor,
            net_price_ngn_minor=discount.net_minor,
            discount_cap_hit=discount.cap_hit,
        )

    async def _compute_discount(
        self, customer_id: str, base_kobo: int, exclude_verification_id: Optional[str] = None
    ) -> Discount:
        """Resolve the first-time + referral discount for a customer (§17.1). First-time =
        no prior paid verification; referral credit = the customer's spendable balance."""
        first_time = not await self._repo.has_paid_verification(customer_id, exclude_verification_id)
        user = await self._users.get_user_model(customer_id)
        return apply_discounts(
            base_kobo,
            first_time=first_time,
            first_time_pct=await self._config.get_int(ConfigKey.FIRST_TIME_DISCOUNT_PERCENT),
            referral_credit_kobo=user.credit_balance_kobo or 0,
            max_discount_pct=await self._config.get_int(ConfigKey.MAX_DISCOUNT_PERCENT),
        )

    # ── Submit: finalise property + tier + price-lock + consent ───

    async def submit(
        self, verification_id: str, customer_id: str, dto: SubmitVerificationDto, ip_address: Optional[str] = None
    ) -> Verification:
        verification = await self._require_owned(verification_id, customer_id)

        prop = await self._property_service.create(customer_id, dto.property)

        ngn = price_ngn_kobo(dto.tier)
        # Apply first-time + referral discounts (§17.1); the NET amount is the locked price.
        discount = await self._compute_discount(customer_id, ngn, exclude_verification_id=verification_id)
        charge_minor, fx = indicative_charge_minor(discount.net_minor, dto.currency)

        # VERIFICATION_TERMS single bundled acceptance (§5.3) — evidentiary record.
        await self._consent_service.record_user_consent(
            user_id=customer_id,
            document_type=ConsentDocumentType.VERIFICATION_TERMS,
            consent_version=dto.consent.consent_version,
            ip_address=ip_address,
        )

        self._assert_transition(verification.status, VerificationStatus.SUBMITTED)
        await self._repo.update(verification_id, UpdateVerificationDto(
            property_id=prop.id,
            tier=dto.tier.value,
            status=VerificationStatus.SUBMITTED.value,
            price_locked_minor=discount.net_minor,
            currency=TransactionCurrency.NGN.value,
            charge_currency=dto.currency.value,
            charge_amount_minor=charge_minor,
            fx_rate_at_quote=fx,
            first_time_discount_minor=discount.first_time_minor,
            referral_credit_applied_minor=discount.referral_applied_minor,
            consent_snapshot_id=f"{ConsentDocumentType.VERIFICATION_TERMS.value}@{dto.consent.consent_version}",
        ))
        await self._set_price_lock(verification_id)

        self._audit.schedule(
            action=AuditActionType.VERIFICATION_SUBMITTED,
            resource_type="verification",
            resource_id=verification_id,
            actor_id=customer_id,
            from_state=VerificationStatus.DRAFT.value,
            to_state=VerificationStatus.SUBMITTED.value,
            ip_address=ip_address,
        )
        return await self._repo.get_model(verification_id)

    # ── Payment-driven transitions (called by PaymentService) ─────

    async def mark_payment_pending(self, verification_id: str) -> Verification:
        verification = await self._repo.get_model(verification_id)
        if not verification:
            raise ResourceNotFoundException(resource="verification")
        self._assert_transition(verification.status, VerificationStatus.PAYMENT_PENDING)
        await self._repo.update(
            verification_id, UpdateVerificationDto(status=VerificationStatus.PAYMENT_PENDING.value)
        )
        return await self._repo.get_model(verification_id)

    async def mark_paid(self, verification_id: str) -> Verification:
        verification = await self._repo.get_model(verification_id)
        if not verification:
            raise ResourceNotFoundException(resource="verification")
        # Idempotent: a replayed webhook that finds PAID must not double-transition.
        if verification.status == VerificationStatus.PAID.value:
            return verification
        self._assert_transition(verification.status, VerificationStatus.PAID)
        tier = VerificationTier(verification.tier) if verification.tier else VerificationTier.BASIC
        await self._repo.update(
            verification_id, UpdateVerificationDto(status=VerificationStatus.PAID.value)
        )
        await self._set_paid_timestamps(verification_id, tier)
        # Debit any referral credit spent on this verification from the customer's balance
        # (§17.1). mark_paid is idempotent (early-returns when already PAID), so this fires once.
        await self._debit_applied_referral_credit(verification)
        # PAID is the payment-confirmed moment (§12.2): SSE re-emit (status_changed) + the
        # customer payment-confirmed notification + email/SMS, one publish (§4.8, D20).
        await publish_domain_event(DomainEvent(
            type=EventType.PAYMENT_CONFIRMED, verification_id=verification_id,
            recipient_user_ids=(verification.customer_id,),
            sse_event=VerificationEventType.STATUS_CHANGED.value,
            data={"status": VerificationStatus.PAID.value},
        ))
        return await self._repo.get_model(verification_id)

    # ── Re-lock guard (§17.1 abandonment): never silently re-price ─

    async def refresh_price_lock_if_expired(self, verification_id: str, customer_id: str) -> PriceRefreshDto:
        """Re-lock an expired price before payment. If the fresh net price differs from what
        the customer last saw, ``price_changed`` is true so the pay page shows the mandatory
        "price updated" interstitial before charging (§17.1) — no silent re-pricing."""
        verification = await self._require_owned(verification_id, customer_id)
        previous = verification.price_locked_minor or 0
        not_expired = (
            verification.price_lock_expires_at is not None
            and verification.price_lock_expires_at > Utils.datetime_now()
        )
        if verification.tier is None or not_expired:
            return PriceRefreshDto(
                price_changed=False, previous_price_minor=previous, net_price_minor=previous,
                first_time_discount_minor=verification.first_time_discount_minor or 0,
                referral_credit_applied_minor=verification.referral_credit_applied_minor or 0,
                price_lock_expires_at=verification.price_lock_expires_at,
            )

        tier = VerificationTier(verification.tier)
        discount = await self._compute_discount(
            customer_id, price_ngn_kobo(tier), exclude_verification_id=verification_id
        )
        charge_minor, fx = indicative_charge_minor(
            discount.net_minor, TransactionCurrency(verification.charge_currency)
            if verification.charge_currency else TransactionCurrency.NGN
        )
        await self._repo.update(verification_id, UpdateVerificationDto(
            price_locked_minor=discount.net_minor,
            charge_amount_minor=charge_minor,
            fx_rate_at_quote=fx,
            first_time_discount_minor=discount.first_time_minor,
            referral_credit_applied_minor=discount.referral_applied_minor,
        ))
        await self._set_price_lock(verification_id)
        refreshed = await self._repo.get_model(verification_id)
        return PriceRefreshDto(
            price_changed=discount.net_minor != previous,
            previous_price_minor=previous,
            net_price_minor=discount.net_minor,
            first_time_discount_minor=discount.first_time_minor,
            referral_credit_applied_minor=discount.referral_applied_minor,
            price_lock_expires_at=refreshed.price_lock_expires_at,
        )

    # ── Abandoned-draft recovery sweep (§17.1) ────────────────────

    async def sweep_abandoned_drafts(self) -> int:
        """Fire a one-time recovery email for each unpaid verification untouched for 24h
        (§17.1). ``recovery_reminded_at`` is stamped so the email is sent exactly once.
        Returns the number of drafts reminded."""
        cutoff = Utils.datetime_now() - timedelta(hours=_ABANDONMENT_AGE_HOURS)
        reminded = 0
        for verification in await self._repo.list_abandoned_drafts(cutoff):
            row = await self._repo.get_model(verification.id)
            if row is None or row.recovery_reminded_at is not None:
                continue
            row.recovery_reminded_at = Utils.datetime_now()
            reminded += 1
            await publish_domain_event(DomainEvent(
                type=EventType.ABANDONMENT_RECOVERY,
                verification_id=verification.id,
                recipient_user_ids=(verification.customer_id,),
                data={"vid": verification.vid},
            ))
        return reminded

    # ── helpers ───────────────────────────────────────────────────

    async def _debit_applied_referral_credit(self, verification: Verification) -> None:
        applied = verification.referral_credit_applied_minor or 0
        if applied <= 0:
            return
        user = await self._users.get_user_model(verification.customer_id)
        # Clamp: never drive the balance negative if credit was spent elsewhere meanwhile.
        debit = min(applied, user.credit_balance_kobo or 0)
        if debit <= 0:
            return
        await self._users.update_user(
            verification.customer_id,
            UpdateUserDto(credit_balance_kobo=(user.credit_balance_kobo or 0) - debit),
        )

    async def _require_owned(self, verification_id: str, customer_id: str) -> Verification:
        verification = await self._repo.get_model(verification_id)
        if not verification:
            raise ResourceNotFoundException(resource="verification")
        if verification.customer_id != customer_id:
            raise ForbiddenException(message="This verification belongs to another customer.")
        return verification

    def _assert_transition(self, current: str, target: VerificationStatus) -> None:
        verification_state_machine.assert_can_transition(current, target.value, resource="Verification")

    async def _set_price_lock(self, verification_id: str) -> None:
        # price_lock_expires_at is a datetime → set on the model (not the update DTO
        # path, which json-encodes datetimes; see CLAUDE.md GenericRepo note).
        verification = await self._repo.get_model(verification_id)
        verification.price_lock_expires_at = Utils.datetime_now() + timedelta(hours=_PRICE_LOCK_HOURS)

    async def _set_paid_timestamps(self, verification_id: str, tier: VerificationTier) -> None:
        verification = await self._repo.get_model(verification_id)
        now = Utils.datetime_now()
        verification.paid_at = now
        verification.sla_due_date = sla_due_date(now, tier)
