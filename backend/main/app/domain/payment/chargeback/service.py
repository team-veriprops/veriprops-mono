"""Chargeback service (PRD §6a).

Idempotent gateway webhook flags the payment and freezes related commissions
(§6a.2) **without touching the verification state machine** (§6a.1). It auto-assembles
the rebuttal pack from existing audit artefacts. Admin submits the pack; the
network-controlled outcome (won/lost) resumes or reverses commissions and restores
or refunds the payment.
"""
from __future__ import annotations

from typing import Optional

from kink import inject

from main.app.config.settings import settings
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.repo import AuditLogRepo
from main.app.domain.audit.service import AuditLogService
from main.app.domain.commission.service import CommissionService
from main.app.domain.payment.chargeback.models import (
    Chargeback,
    ChargebackStatus,
    ChargebackWebhookDto,
    CreateChargebackDto,
    UpdateChargebackDto,
)
from main.app.domain.payment.chargeback.repo import ChargebackRepo
from main.app.domain.payment.models import PaymentStatus, UpdatePaymentDto
from main.app.domain.payment.repo import PaymentRepo
from main.app.domain.user.auth.consent.service import ConsentService
from main.app.domain.verification.repo import VerificationRepo
from main.appodus_utils import Utils
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
)

_PACK_PAGE_SIZE = settings.CHARGEBACK_PACK_PAGE_SIZE


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class ChargebackService:
    def __init__(
        self,
        chargeback_repo: ChargebackRepo,
        payment_repo: PaymentRepo,
        verification_repo: VerificationRepo,
        commission_service: CommissionService,
        consent_service: ConsentService,
        audit_repo: AuditLogRepo,
        audit_service: AuditLogService,
    ):
        self._chargeback_repo = chargeback_repo
        self._payment_repo = payment_repo
        self._verification_repo = verification_repo
        self._commissions = commission_service
        self._consent_service = consent_service
        self._audit_repo = audit_repo
        self._audit = audit_service

    async def handle_webhook(self, dto: ChargebackWebhookDto) -> Optional[Chargeback]:
        """Flag the payment + freeze commissions + assemble the rebuttal pack (§6a.2).

        Idempotent on the gateway event id — a replayed chargeback webhook returns the
        existing row without re-freezing or duplicating."""
        existing = await self._chargeback_repo.get_by_event_id(dto.event_id)
        if existing:
            return existing

        payment = await self._payment_repo.get_by_tx_ref(dto.tx_ref)
        if not payment:
            raise ResourceNotFoundException(resource="payment")

        pack = await self._assemble_rebuttal_pack(payment.verification_id, payment.customer_id)
        chargeback = await self._chargeback_repo.create_return_model(CreateChargebackDto(
            payment_id=payment.id,
            verification_id=payment.verification_id,
            gateway_event_id=dto.event_id,
            status=ChargebackStatus.FLAGGED,
            reason=dto.reason,
            amount_minor=dto.amount_minor if dto.amount_minor is not None else payment.amount_minor,
            currency=TransactionCurrency(payment.currency),
            rebuttal_pack=pack,
        ))

        await self._payment_repo.update(payment.id, UpdatePaymentDto(
            chargeback_status=ChargebackStatus.FLAGGED.value
        ))
        # §6a.2 — commission freeze happens on flag, not on outcome.
        frozen = await self._commissions.freeze_for_verification(
            payment.verification_id, actor_id=None
        )

        self._audit.schedule(
            action=AuditActionType.CHARGEBACK_FLAGGED,
            resource_type="chargeback",
            resource_id=chargeback.id,
            actor_id=None,
            details={"verification_id": payment.verification_id,
                     # payment.id is a uuid.UUID on the ORM row — hex it for the JSON column.
                     "payment_id": Utils.uuid_to_hex(payment.id),
                     "commissions_frozen": frozen},
        )
        return chargeback

    async def submit_rebuttal(self, chargeback_id: str, admin_id: str) -> Chargeback:
        chargeback = await self._get(chargeback_id)
        if chargeback.status != ChargebackStatus.FLAGGED.value:
            raise InvalidResourceStateException(
                resource="chargeback", message="Only a flagged chargeback can be rebutted."
            )
        await self._chargeback_repo.update(chargeback_id, UpdateChargebackDto(
            status=ChargebackStatus.REBUTTAL_SUBMITTED.value
        ))
        self._audit.schedule(
            action=AuditActionType.CHARGEBACK_REBUTTAL_SUBMITTED,
            resource_type="chargeback",
            resource_id=chargeback_id,
            actor_id=admin_id,
        )
        return await self._chargeback_repo.get_model(chargeback_id)

    async def resolve(self, chargeback_id: str, won: bool, admin_id: str) -> Chargeback:
        chargeback = await self._get(chargeback_id)
        if chargeback.status in (ChargebackStatus.WON.value, ChargebackStatus.LOST.value):
            raise InvalidResourceStateException(
                resource="chargeback", message="This chargeback is already resolved."
            )

        if won:
            await self._chargeback_repo.update(chargeback_id, UpdateChargebackDto(status=ChargebackStatus.WON.value))
            await self._payment_repo.update(chargeback.payment_id, UpdatePaymentDto(
                chargeback_status=ChargebackStatus.WON.value
            ))
            resumed = await self._commissions.unfreeze_for_verification(
                chargeback.verification_id, actor_id=admin_id
            )
            self._audit.schedule(
                action=AuditActionType.CHARGEBACK_WON,
                resource_type="chargeback",
                resource_id=chargeback_id,
                actor_id=admin_id,
                details={"commissions_resumed": resumed},
            )
        else:
            await self._chargeback_repo.update(chargeback_id, UpdateChargebackDto(status=ChargebackStatus.LOST.value))
            # Payment reversed by the bank — record the reversal on our side.
            await self._payment_repo.update(chargeback.payment_id, UpdatePaymentDto(
                chargeback_status=ChargebackStatus.LOST.value,
                status=PaymentStatus.FAILED.value,
                refunded_amount_minor=chargeback.amount_minor,
            ))
            reversed_count = await self._commissions.reverse_for_verification(
                chargeback.verification_id, actor_id=admin_id
            )
            self._audit.schedule(
                action=AuditActionType.CHARGEBACK_LOST,
                resource_type="chargeback",
                resource_id=chargeback_id,
                actor_id=admin_id,
                details={"commissions_reversed": reversed_count,
                         "repeat_offender_review": chargeback.verification_id},
            )
        await self._set_resolved_at(chargeback_id)
        return await self._chargeback_repo.get_model(chargeback_id)

    async def list_for_verification(self, verification_id: str):
        return await self._chargeback_repo.list_for_verification(verification_id)

    async def count_open(self) -> int:
        """Unresolved chargebacks needing admin attention (§6a) — flagged or with a
        rebuttal submitted but not yet won/lost."""
        return await self._chargeback_repo.count_by_status([
            ChargebackStatus.FLAGGED.value,
            ChargebackStatus.REBUTTAL_SUBMITTED.value,
        ])

    # ── rebuttal pack (§6a.2) ─────────────────────────────────────

    async def _assemble_rebuttal_pack(self, verification_id: str, customer_id: str) -> dict:
        """Compile the gateway-submission pack from existing audit artefacts: consent
        records, the audit trail, and payment/receipt. The released report and evidence
        hashes are appended as those domains land (S11/S12)."""
        verification = await self._verification_repo.get_model(verification_id)
        audit_rows, _ = await self._audit_repo.list_for_resource(
            "verification", verification_id, offset=0, limit=_PACK_PAGE_SIZE
        )
        consents = await self._consent_service.list_for_user(customer_id, page=0, page_size=100)
        payments = await self._payment_repo.list_for_verification(verification_id)

        return {
            "assembled_at": Utils.datetime_now().isoformat(),
            "verification": {
                "id": verification_id,
                "vid": getattr(verification, "vid", None),
                "status": getattr(verification, "status", None),
                "tier": getattr(verification, "tier", None),
                "price_locked_minor": getattr(verification, "price_locked_minor", None),
            } if verification else None,
            "consent_records": [
                {"document_type": c.document_type, "consent_version": c.consent_version,
                 "accepted_at": c.accepted_at.isoformat() if c.accepted_at else None,
                 "ip_address": c.ip_address}
                for c in consents.items
            ],
            "audit_trail": [
                {"action": r.action, "from_state": r.from_state, "to_state": r.to_state,
                 "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None}
                for r in audit_rows
            ],
            "payments": [
                {"tx_ref": p.tx_ref, "status": p.status, "amount_minor": p.amount_minor,
                 "currency": p.currency, "charge_currency": p.charge_currency}
                for p in payments
            ],
            # TODO(gap): still placeholders — wire the released report + evidence content
            # hashes into the pack (shape kept stable) — PRD "Known Gaps & Roadmap".
            "report": None,
            "evidence_hashes": [],
        }

    # ── helpers ───────────────────────────────────────────────────

    async def _get(self, chargeback_id: str) -> Chargeback:
        chargeback = await self._chargeback_repo.get_model(chargeback_id)
        if not chargeback:
            raise ResourceNotFoundException(resource="chargeback")
        return chargeback

    async def _set_resolved_at(self, chargeback_id: str) -> None:
        chargeback = await self._chargeback_repo.get_model(chargeback_id)
        chargeback.resolved_at = Utils.datetime_now()
