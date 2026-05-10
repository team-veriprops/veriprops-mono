"""Payment service.

Drives verification state via the state machine. Webhook idempotency is
enforced by deduping on `provider_ref`. Customer trust elevation fires
exactly once per customer, on the first SUCCEEDED payment.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

import json
from typing import Any, Dict, Optional

from kink import di, inject

from main.app.domain.payment.models import (
    ConfirmWireDto,
    CreatePaymentAttemptDto,
    CreatePaymentDto,
    InitiatePaymentDto,
    InitiatePaymentResultDto,
    Payment,
    PaymentDto,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    UpdatePaymentDto,
    WireProofDto,
)
from main.app.domain.payment.repo import PaymentAttemptRepo, PaymentRepo
from main.app.domain.user.auth.session.models import SecurityEventType
from main.app.domain.user.auth.session.service import SessionService
from main.app.domain.user.models import TrustStatus, UpdateUserDto
from main.app.domain.user.repo import UserRepo
from main.app.domain.verification.models import (
    PricingSnapshotDto,
    VerificationStatus,
)
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.service import VerificationService
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
    ValidationException,
)
from main.appodus_utils.integrations.factory import PaymentGatewayFactory
from main.appodus_utils.integrations.payment.gateway.models import (
    CustomerInfo,
    Customizations,
    PaymentInitRequest,
)
from main.appodus_utils.integrations.payment.gateway.paystack.models import PaystackBankTransferChargeRequest
from main.appodus_utils.integrations.payment.gateway.paystack.payment import PaystackPaymentGateway
from main.app.config.settings import IntegratedPlatform, settings

logger: Logger = di["logger"]


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class PaymentService:
    def __init__(
        self,
        payment_repo: PaymentRepo,
        attempt_repo: PaymentAttemptRepo,
        verification_repo: VerificationRepo,
        verification_service: VerificationService,
        session_service: SessionService,
        user_repo: UserRepo,
        gateway_factory: PaymentGatewayFactory,
    ):
        self._payment_repo = payment_repo
        self._attempt_repo = attempt_repo
        self._verification_repo = verification_repo
        self._verification_service = verification_service
        self._session_service = session_service
        self._user_repo = user_repo
        self._gateway_factory = gateway_factory

    # ── Initiation ────────────────────────────────────────────────

    async def initiate(
        self, customer_id: str, dto: InitiatePaymentDto,
    ) -> InitiatePaymentResultDto:
        verification = await self._verification_repo.get_model(dto.verification_id)
        if verification is None:
            raise ResourceNotFoundException(resource="Verification")
        if str(verification.customer_id) != customer_id:
            raise ValidationException(message="Verification not owned by current user")
        if verification.status not in (
            VerificationStatus.SUBMITTED.value,
            VerificationStatus.PAYMENT_PENDING.value,
        ):
            raise InvalidResourceStateException(
                resource="Verification",
                message="Verification is not awaiting payment",
            )
        if not verification.pricing_snapshot:
            raise InvalidResourceStateException(
                resource="Verification",
                message="No pricing snapshot — select a tier first",
            )
        snapshot = PricingSnapshotDto.model_validate(json.loads(verification.pricing_snapshot))

        user = await self._user_repo.get_model(customer_id)
        if user is None:
            raise ResourceNotFoundException(resource="User")

        provider = (
            PaymentProvider.PAYSTACK
            if dto.method == PaymentMethod.BANK_TRANSFER
            else PaymentProvider.FLUTTERWAVE
        )
        status = self._initial_status_for_method(dto.method)
        await self._payment_repo.create(CreatePaymentDto(
            verification_id=str(verification.id),
            provider=provider,
            amount_minor=snapshot.total_amount_minor,
            currency=snapshot.currency,
            method=dto.method,
            status=status,
        ))
        # Re-fetch most recent payment.
        from main.app.domain.payment.models import SearchPaymentDto
        page = await self._payment_repo.get_page(SearchPaymentDto(
            page=1, page_size=1, verification_id=str(verification.id),
        ))
        payment = page.items[0] if page.items else None
        if payment is None:
            raise InvalidResourceStateException(
                resource="Payment",
                message="Payment record could not be created",
            )

        # Move verification → PAYMENT_PENDING (idempotent).
        await self._verification_service.transition(
            str(verification.id), VerificationStatus.PAYMENT_PENDING,
        )

        await self._session_service.record_event(
            type=SecurityEventType.PAYMENT_INITIATED,
            description=f"payment for {verification.vid} via {dto.method.value}",
            user_id=customer_id,
        )

        tx_ref = f"vp_{payment.id}"
        customer_info = CustomerInfo(
            email=user.email,
            phonenumber=user.phone_e164 or f"{user.phone_dial_code}{user.phone}",
            name=f"{user.first_name} {user.last_name}",
        )

        instructions: Optional[Dict[str, Any]] = None
        checkout_url: Optional[str] = None

        if dto.method == PaymentMethod.CARD:
            flw_gw = self._gateway_factory.get_gateway(IntegratedPlatform.FLUTTERWAVE)
            checkout_url = await flw_gw.initialize_payment(PaymentInitRequest(
                tx_ref=tx_ref,
                amount=snapshot.total_amount_minor / 100,
                currency=snapshot.currency,
                redirect_url=dto.redirect_url or settings.FLUTTERWAVE_REDIRECT_URL or "",
                customer=customer_info,
                customizations=Customizations(
                    title="Veriprops Property Verification",
                    description=f"Verification payment for {verification.vid}",
                ),
            ))
            await self._payment_repo.update(str(payment.id), UpdatePaymentDto(
                provider_ref=tx_ref,
            ))

        elif dto.method == PaymentMethod.BANK_TRANSFER:
            paystack_gw: PaystackPaymentGateway = self._gateway_factory.get_gateway(IntegratedPlatform.PAYSTACK)  # type: ignore[assignment]
            expiry = Utils.datetime_now_plus(hours=24)
            charge_result = await paystack_gw.charge_bank_transfer(PaystackBankTransferChargeRequest(
                email=user.email,
                amount=snapshot.total_amount_minor,
                reference=tx_ref,
                bank_transfer={"account_expires_at": expiry.isoformat()},
            ))
            await self._payment_repo.update(str(payment.id), UpdatePaymentDto(
                provider_ref=charge_result.reference,
            ))
            instructions = {
                "virtualAccountBank": charge_result.bank,
                "virtualAccountNumber": charge_result.account_number,
                "accountName": charge_result.account_name,
                "expiresAt": charge_result.expiry_date or expiry.isoformat(),
                "amountMinor": snapshot.total_amount_minor,
                "currency": snapshot.currency,
            }

        else:  # WIRE
            instructions = {
                "beneficiaryBank": settings.WIRE_BENEFICIARY_BANK,
                "swift": settings.WIRE_SWIFT,
                "iban": settings.WIRE_IBAN,
                "beneficiary": settings.WIRE_BENEFICIARY,
                "reference": verification.vid,
                "amountMinor": snapshot.total_amount_minor,
                "currency": snapshot.currency,
                "uploadProofTo": f"/api/payments/{payment.id}/wire-proof",
            }

        return InitiatePaymentResultDto(
            payment=self._to_dto_from_query(payment),
            checkout_url=checkout_url,
            instructions=instructions,
        )

    # ── Webhook / completion ─────────────────────────────────────

    async def record_provider_event(
        self, *, provider_ref: str, status: str, payload: Dict[str, Any],
    ) -> None:
        """Idempotent webhook handler. `status` is normalised externally."""
        payment = await self._payment_repo.get_by_provider_ref(provider_ref)
        if payment is None:
            logger.warning("Webhook for unknown provider_ref={}", provider_ref)
            return
        await self._attempt_repo.create(CreatePaymentAttemptDto(
            payment_id=str(payment.id),
            status=PaymentStatus(status),
            provider_ref=provider_ref,
            event_payload=json.dumps(payload),
        ))
        # Idempotency guard: skip state change if we already terminalised.
        if payment.status in (
            PaymentStatus.SUCCEEDED.value,
            PaymentStatus.FAILED.value,
        ):
            return
        await self._payment_repo.update(str(payment.id), UpdatePaymentDto(
            status=PaymentStatus(status),
            provider_metadata=json.dumps(payload),
        ))
        if status == PaymentStatus.SUCCEEDED.value:
            await self._on_payment_succeeded(payment)
        elif status == PaymentStatus.FAILED.value:
            await self._session_service.record_event(
                type=SecurityEventType.PAYMENT_FAILED,
                description=f"payment {payment.id} failed",
            )

    async def confirm_wire(
        self, payment_id: str, admin_id: str, dto: ConfirmWireDto,
    ) -> PaymentDto:
        payment = await self._payment_repo.get_model(payment_id)
        if payment is None:
            raise ResourceNotFoundException(resource="Payment")
        if payment.status not in (
            PaymentStatus.PENDING_WIRE.value,
            PaymentStatus.INITIATED.value,
        ):
            raise InvalidResourceStateException(resource="Payment")
        await self._payment_repo.update(payment_id, UpdatePaymentDto(
            status=PaymentStatus.SUCCEEDED,
            confirmed_by_admin_id=admin_id,
        ))
        refreshed = await self._payment_repo.get_model(payment_id)
        if refreshed is not None:
            await self._on_payment_succeeded(refreshed)
        return self._to_dto(refreshed)

    async def upload_wire_proof(
        self, customer_id: str, payment_id: str, dto: WireProofDto,
    ) -> PaymentDto:
        payment = await self._payment_repo.get_model(payment_id)
        if payment is None:
            raise ResourceNotFoundException(resource="Payment")
        verification = await self._verification_repo.get_model(payment.verification_id)
        if verification is None or str(verification.customer_id) != customer_id:
            raise ValidationException(message="Payment not owned by current user")
        await self._payment_repo.update(payment_id, UpdatePaymentDto(
            status=PaymentStatus.PENDING_WIRE,
            wire_proof_url=dto.proof_url,
        ))
        refreshed = await self._payment_repo.get_model(payment_id)
        return self._to_dto(refreshed)

    async def get(self, customer_id: str, payment_id: str) -> PaymentDto:
        payment = await self._payment_repo.get_model(payment_id)
        if payment is None:
            raise ResourceNotFoundException(resource="Payment")
        verification = await self._verification_repo.get_model(payment.verification_id)
        if verification is None or str(verification.customer_id) != customer_id:
            raise ValidationException(message="Payment not owned by current user")
        return self._to_dto(payment)

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _initial_status_for_method(method: PaymentMethod) -> PaymentStatus:
        if method == PaymentMethod.WIRE:
            return PaymentStatus.PENDING_WIRE
        if method == PaymentMethod.BANK_TRANSFER:
            return PaymentStatus.PENDING_TRANSFER
        return PaymentStatus.INITIATED

    async def _on_payment_succeeded(self, payment: Payment) -> None:
        verification = await self._verification_repo.get_model(payment.verification_id)
        if verification is None:
            return
        # Verification: PAYMENT_PENDING → PAID
        if verification.status == VerificationStatus.PAYMENT_PENDING.value:
            await self._verification_service.transition(
                str(verification.id), VerificationStatus.PAID,
            )
        # Trust elevation — first SUCCEEDED payment for this customer.
        user = await self._user_repo.get_model(verification.customer_id)
        if user and (user.trust_status or "") != TrustStatus.TRUSTED.value:
            await self._user_repo.update(str(user.id), UpdateUserDto(
                trust_status=TrustStatus.TRUSTED.value,
            ))
            await self._session_service.record_event(
                type=SecurityEventType.TRUST_ELEVATED,
                description=f"trusted on first successful payment {payment.id}",
                user_id=str(user.id),
            )
        await self._session_service.record_event(
            type=SecurityEventType.PAYMENT_SUCCEEDED,
            description=f"payment {payment.id} succeeded for {verification.vid}",
            user_id=str(verification.customer_id),
        )

    def _to_dto(self, payment: Optional[Payment]) -> PaymentDto:
        if payment is None:
            raise ResourceNotFoundException(resource="Payment")
        return PaymentDto(
            id=str(payment.id),
            verification_id=str(payment.verification_id),
            provider=PaymentProvider(payment.provider),
            method=PaymentMethod(payment.method),
            status=PaymentStatus(payment.status),
            amount_minor=int(payment.amount_minor),
            currency=payment.currency,
            provider_ref=payment.provider_ref,
            failure_reason=payment.failure_reason,
            wire_proof_url=payment.wire_proof_url,
            created_at=payment.date_created,
            updated_at=payment.date_updated,
        )

    @staticmethod
    def _to_dto_from_query(query) -> PaymentDto:
        return PaymentDto(
            id=str(query.id),
            verification_id=str(query.verification_id),
            provider=PaymentProvider(query.provider),
            method=PaymentMethod(query.method),
            status=PaymentStatus(query.status),
            amount_minor=int(query.amount_minor),
            currency=query.currency,
            provider_ref=getattr(query, "provider_ref", None),
            failure_reason=getattr(query, "failure_reason", None),
            wire_proof_url=getattr(query, "wire_proof_url", None),
            created_at=query.date_created,
            updated_at=getattr(query, "date_updated", None),
        )
