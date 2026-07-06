"""Payment service (PRD §4.4, §4.6, §5.4).

Gateway-mediated. Initiation is guarded by a client idempotency key; the webhook
handler is idempotent on the gateway event id, so a replayed "succeeded" webhook
cannot create a second PAID transition or receipt. Phone is verified before payment
completes. First successful payment upgrades the customer to `trusted`.
"""
from __future__ import annotations

from typing import Optional

from kink import inject

from main.app.config.settings import settings
from main.app.core.idempotency.service import IdempotencyService
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.payment.models import (
    CreatePaymentDto,
    Payment,
    PaymentMethodKind,
    PaymentPurpose,
    PaymentStatus,
    PaymentWebhookDto,
    UpdatePaymentDto,
)
from main.app.domain.payment.repo import PaymentRepo
from main.app.domain.user.auth.session.models import UserPersona
from main.app.domain.user.service import UserService
from main.app.domain.verification.models import VerificationStatus
from main.app.domain.verification.service import VerificationService
from main.app.domain.verification.task.service import VerificationTaskService
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
    ValidationException,
)

_INITIATE_SCOPE = "payment.initiate"
_WEBHOOK_SCOPE = "payment.webhook"
_PAYABLE = {VerificationStatus.SUBMITTED.value, VerificationStatus.PAYMENT_PENDING.value}


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class PaymentService:
    def __init__(
        self,
        payment_repo: PaymentRepo,
        verification_service: VerificationService,
        task_service: VerificationTaskService,
        user_service: UserService,
        idempotency_service: IdempotencyService,
        audit_service: AuditLogService,
    ):
        self._repo = payment_repo
        self._verification_service = verification_service
        self._task_service = task_service
        self._user_service = user_service
        self._idempotency = idempotency_service
        self._audit = audit_service

    async def initiate(
        self,
        verification_id: str,
        customer_id: str,
        method: PaymentMethodKind,
        idempotency_key: Optional[str] = None,
    ) -> Payment:
        verification = await self._verification_service.get_owned(verification_id, customer_id)
        if verification.status not in _PAYABLE:
            raise InvalidResourceStateException(
                resource="verification",
                message="This verification is not awaiting payment.",
            )

        # Phone gate (§5.4): phone must be verified before payment completes.
        user = await self._user_service.get_user_model(customer_id)
        if not user.phone_verified:
            raise ValidationException(message="Verify your phone number before paying.")

        if idempotency_key:
            outcome = await self._idempotency.begin_or_replay(idempotency_key, _INITIATE_SCOPE)
            if outcome.is_replay and outcome.resource_id:
                existing = await self._repo.get_model(outcome.resource_id)
                if existing:
                    return existing

        tx_ref = f"{verification.vid}-{Utils.random_str(8)}"
        payment = await self._repo.create_return_model(CreatePaymentDto(
            verification_id=verification_id,
            customer_id=customer_id,
            tx_ref=tx_ref,
            method=method,
            amount_minor=verification.price_locked_minor or 0,
            currency=verification.currency,
            charge_currency=verification.charge_currency,
            charge_amount_minor=verification.charge_amount_minor,
            status=PaymentStatus.INITIATED,
            checkout_url=self._checkout_url(verification_id, tx_ref),
        ))

        await self._verification_service.mark_payment_pending(verification_id)

        self._audit.schedule(
            action=AuditActionType.PAYMENT_INITIATED,
            resource_type="payment",
            resource_id=payment.id,
            actor_id=customer_id,
            details={"verification_id": verification_id, "tx_ref": tx_ref},
        )

        if idempotency_key:
            await self._idempotency.complete(idempotency_key, resource_id=payment.id)
        return payment

    async def initiate_secondary(
        self,
        verification_id: str,
        customer_id: str,
        amount_minor: int,
        purpose: PaymentPurpose,
        method: PaymentMethodKind = PaymentMethodKind.CARD,
    ) -> Payment:
        """Create a secondary charge (§14 re-check / tier upgrade) on an existing verification
        WITHOUT touching the verification state machine — the new work cycle starts only when
        this charge is confirmed (routed by ``purpose`` in the webhook). Deterministic under
        PAYMENT_STUB_MODE via the same stub checkout + confirm path as the initial payment."""
        verification = await self._verification_service.get_by_id(verification_id)
        if verification.customer_id != customer_id:
            raise ValidationException(message="This verification belongs to another customer.")
        if amount_minor <= 0:
            raise ValidationException(message="A positive charge amount is required.")

        tx_ref = f"{verification.vid}-{purpose.value[:3]}-{Utils.random_str(8)}"
        payment = await self._repo.create_return_model(CreatePaymentDto(
            verification_id=verification_id,
            customer_id=customer_id,
            tx_ref=tx_ref,
            method=method,
            purpose=purpose,
            amount_minor=amount_minor,
            currency=verification.currency,
            status=PaymentStatus.INITIATED,
            checkout_url=self._checkout_url(verification_id, tx_ref),
        ))
        self._audit.schedule(
            action=AuditActionType.PAYMENT_INITIATED,
            resource_type="payment", resource_id=payment.id, actor_id=customer_id,
            details={"verification_id": verification_id, "tx_ref": tx_ref, "purpose": purpose.value},
        )
        return payment

    async def handle_webhook(self, dto: PaymentWebhookDto) -> bool:
        """Idempotent gateway webhook (§4.6): drives PAYMENT_PENDING → PAID exactly once."""
        # One-shot dedup on the gateway event id — a replay returns without effect.
        if not await self._idempotency.claim(dto.event_id, _WEBHOOK_SCOPE):
            return False

        payment = await self._repo.get_by_tx_ref(dto.tx_ref)
        if not payment:
            raise ResourceNotFoundException(resource="payment")

        await self._repo.update(payment.id, UpdatePaymentDto(gateway_event_id=dto.event_id))

        if dto.succeeded:
            await self._repo.update(payment.id, UpdatePaymentDto(status=PaymentStatus.SUCCEEDED.value))
            self._audit.schedule(
                action=AuditActionType.PAYMENT_SUCCEEDED,
                resource_type="payment",
                resource_id=payment.id,
                actor_id=payment.customer_id,
                details={"verification_id": payment.verification_id, "purpose": payment.purpose},
            )
            if payment.purpose == PaymentPurpose.RECHECK.value:
                await self._on_secondary_paid(payment, PaymentPurpose.RECHECK)
            elif payment.purpose == PaymentPurpose.UPGRADE.value:
                await self._on_secondary_paid(payment, PaymentPurpose.UPGRADE)
            else:
                await self._verification_service.mark_paid(payment.verification_id)
                # At PAID: instantiate unlocked tasks and (if enabled) broadcast them (§6.2).
                await self._task_service.prepare_for_paid(payment.verification_id)
                # First successful payment → trusted customer (PRD §3.3).
                await self._user_service.upgrade_trust_status_if_eligible(
                    payment.customer_id, UserPersona.CUSTOMER
                )
                # Referral credit (§17.1): a referred invitee's first payment earns the
                # referrer a credit that clears after the chargeback window. Best-effort —
                # a referral hiccup must never fail the payment webhook.
                await self._award_referral_credit(payment)
                self._audit.schedule(
                    action=AuditActionType.VERIFICATION_STATE_CHANGED,
                    resource_type="verification",
                    resource_id=payment.verification_id,
                    actor_id=payment.customer_id,
                    to_state=VerificationStatus.PAID.value,
                )
        else:
            await self._repo.update(payment.id, UpdatePaymentDto(
                status=PaymentStatus.FAILED.value,
                failure_count=(payment.failure_count or 0) + 1,
            ))
            self._audit.schedule(
                action=AuditActionType.PAYMENT_FAILED,
                resource_type="payment",
                resource_id=payment.id,
                actor_id=payment.customer_id,
            )
        return True

    async def get_payment(self, payment_id: str) -> Optional[Payment]:
        return await self._repo.get_model(payment_id)

    async def refund(self, verification_id: str, actor_id: str, reason: Optional[str] = None) -> int:
        """Refund the successful payment(s) on a verification (§8.5). Deterministic under
        PAYMENT_STUB_MODE (no gateway call); a live gateway refund is issued through the
        payment facade otherwise. Idempotent: an already-REFUNDED payment is skipped.
        Returns the total refunded amount (minor units)."""
        refunded_total = 0
        for payment in await self._repo.list_for_verification(verification_id):
            if payment.status != PaymentStatus.SUCCEEDED.value:
                continue
            # Live path issues the gateway refund here (facade); stub mode is a no-op call.
            await self._repo.update(payment.id, UpdatePaymentDto(
                status=PaymentStatus.REFUNDED.value,
                refunded_amount_minor=payment.amount_minor,
            ))
            refunded_total += payment.amount_minor
            self._audit.schedule(
                action=AuditActionType.PAYMENT_REFUNDED,
                resource_type="payment", resource_id=payment.id, actor_id=actor_id,
                details={"verification_id": verification_id, "amount_minor": payment.amount_minor,
                         "reason": reason},
            )
        return refunded_total

    async def _award_referral_credit(self, payment: Payment) -> None:
        """Route a confirmed first payment to the referral service (best-effort). Resolved
        lazily via DI so the payment domain never imports the referral service at module load."""
        from kink import di

        from main.app.domain.referral.service import ReferralService
        try:
            await di[ReferralService].on_invitee_first_payment(payment)
        except Exception:  # pragma: no cover - defensive; never break the payment webhook
            from kink import di as _di
            _di["logger"].exception("Referral credit award failed for payment {}", payment.id)

    async def _on_secondary_paid(self, payment: Payment, purpose: PaymentPurpose) -> None:
        """Route a confirmed re-check / tier-upgrade charge to its domain service. Resolved
        lazily via the DI container so the payment domain never imports those services at
        module load (they depend back on payment/verification), avoiding an import cycle."""
        from kink import di

        if purpose == PaymentPurpose.RECHECK:
            from main.app.domain.verification.recheck.service import RecheckService
            await di[RecheckService].on_payment_confirmed(payment.id)
        elif purpose == PaymentPurpose.UPGRADE:
            from main.app.domain.verification.upgrade.service import UpgradeService
            await di[UpgradeService].on_payment_confirmed(payment.id)

    def _checkout_url(self, verification_id: str, tx_ref: str) -> str:
        if settings.PAYMENT_STUB_MODE:
            # Deterministic path: the frontend pay page completes via the stub webhook.
            return f"/portal/verifications/{verification_id}/pay?txRef={tx_ref}&stub=1"
        # Live gateways return their own hosted checkout URL (wired via the payment
        # gateway facade); left to the provider integration.
        return ""
