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
from main.app.domain.user.auth.consent.models import ConsentDocumentType
from main.app.domain.user.auth.consent.service import ConsentService
from main.app.domain.verification.models import (
    CreateVerificationDto,
    PriceQuoteDto,
    SaveVerificationDraftDto,
    SubmitVerificationDto,
    UpdateVerificationDto,
    Verification,
)
from main.app.domain.verification.pricing import indicative_charge_minor, price_ngn_kobo
from main.app.domain.verification.repo import VerificationRepo
from main.appodus_utils import Utils
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ForbiddenException, ResourceNotFoundException

_CREATE_SCOPE = "verification.create"
_PRICE_LOCK_HOURS = 24


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
    ):
        self._repo = verification_repo
        self._property_service = property_service
        self._consent_service = consent_service
        self._idempotency = idempotency_service
        self._audit = audit_service

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

    # ── Pricing quote (PRD §5.2) ──────────────────────────────────

    def quote(self, tier: VerificationTier, currency: TransactionCurrency) -> PriceQuoteDto:
        ngn = price_ngn_kobo(tier)
        charge_minor, fx = indicative_charge_minor(ngn, currency)
        return PriceQuoteDto(
            tier=tier,
            price_ngn_minor=ngn,
            currency=currency,
            charge_amount_minor=charge_minor,
            fx_rate=fx,
        )

    # ── Submit: finalise property + tier + price-lock + consent ───

    async def submit(
        self, verification_id: str, customer_id: str, dto: SubmitVerificationDto, ip_address: Optional[str] = None
    ) -> Verification:
        verification = await self._require_owned(verification_id, customer_id)

        prop = await self._property_service.create(customer_id, dto.property)

        ngn = price_ngn_kobo(dto.tier)
        charge_minor, fx = indicative_charge_minor(ngn, dto.currency)

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
            price_locked_minor=ngn,
            currency=TransactionCurrency.NGN.value,
            charge_currency=dto.currency.value,
            charge_amount_minor=charge_minor,
            fx_rate_at_quote=fx,
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
        # PAID is the payment-confirmed moment (§12.2): SSE re-emit (status_changed) + the
        # customer payment-confirmed notification + email/SMS, one publish (§4.8, D20).
        await publish_domain_event(DomainEvent(
            type=EventType.PAYMENT_CONFIRMED, verification_id=verification_id,
            recipient_user_ids=(verification.customer_id,),
            sse_event=VerificationEventType.STATUS_CHANGED.value,
            data={"status": VerificationStatus.PAID.value},
        ))
        return await self._repo.get_model(verification_id)

    # ── helpers ───────────────────────────────────────────────────

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
