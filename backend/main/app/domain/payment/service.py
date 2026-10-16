"""Payment service (PRD §4.4, §4.6, §5.4).

Gateway-mediated. Initiation is guarded by a client idempotency key; the webhook
handler is idempotent on the gateway event id, so a replayed "succeeded" webhook
cannot create a second PAID transition or receipt. Phone is verified before payment
completes. First successful payment upgrades the customer to `trusted`.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from typing import TYPE_CHECKING, Collection, Optional, Tuple

from kink import di, inject

from main.app.config.settings import IntegratedPlatform, settings
from main.app.core.links.portal import VerificationPage, absolute_url, verification_path
from main.app.core.idempotency.service import IdempotencyService
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.payment.chargeback.models import ChargebackWebhookDto
from main.app.domain.payment.models import (
    AdminPaymentDto,
    admin_payment_to_dto,
    CreatePaymentDto,
    Payment,
    PaymentMethodKind,
    PaymentPurpose,
    PaymentStatus,
    PaymentDto,
    PaymentWebhookDto,
    RefundOutcome,
    UpdatePaymentDto,
    payment_to_dto,
)
from main.app.domain.payment.repo import ADMIN_PAYMENT_SORTABLE, PaymentRepo
from main.app.core.state.machine import VERIFICATION_TERMINAL
from main.app.domain.payment.refund_request.models import RefundSource
from main.app.domain.payment.refund_request.service import RefundRequestService
from main.app.domain.user.auth.session.models import UserPersona
from main.app.domain.user.service import UserService
from main.app.domain.verification.models import VerificationStatus
from main.app.domain.verification.service import VerificationService
from main.app.domain.verification.task.service import VerificationTaskService
from main.appodus_utils import Page, Utils
from main.appodus_utils.exception.faults import log_fault_once
from main.appodus_utils.db.db_utils import DbUtils
from main.appodus_utils.db.types.money import TransactionCurrency
from main.appodus_utils.integrations.exception.exceptions import IntegrationException
from main.appodus_utils.integrations.factory import PaymentGatewayFactory
from main.appodus_utils.integrations.payment.gateway.models import (
    GatewayChargeStatus,
    HostedCheckoutRequest,
)
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    InvalidResourceStateException,
    ResourceNotFoundException,
    ValidationException,
)

if TYPE_CHECKING:
    from loguru import Logger

    from main.app.domain.payment.chargeback.service import ChargebackService

logger: Logger = di["logger"]

_INITIATE_SCOPE = "payment.initiate"
_WEBHOOK_SCOPE = "payment.webhook"
_PAYABLE = {VerificationStatus.SUBMITTED.value, VerificationStatus.PAYMENT_PENDING.value}
# A charge the gateway may still settle, one way or the other. SUCCEEDED and REFUNDED are
# final: no later event moves a payment out of them.
_OPEN_PAYMENT_STATUSES = [
    PaymentStatus.INITIATED, PaymentStatus.PROCESSING, PaymentStatus.PENDING_TRANSFER, PaymentStatus.FAILED,
]
_OPEN_PAYMENT_VALUES = {status.value for status in _OPEN_PAYMENT_STATUSES}
_CHECKOUT_TITLE = "Veriprops property verification"
# A verification whose payments are owed back to the customer.


class _GatewayRefundRefused(Exception):
    """A gateway refused one payment's refund; the payment has been put back to SUCCEEDED."""


def refundable_total(payments) -> int:
    """What a refund could send back from *payments* (already loaded): see `_refundable`."""
    return sum(p.amount_minor for p in payments if _refundable(p))


def _refundable(payment: Payment) -> bool:
    """A settled charge whose money is ours to return: not the issuer's (under a chargeback),
    and not already owed back by a refund Finance approved (that waits for its retry)."""
    return (payment.status == PaymentStatus.SUCCEEDED.value and not payment.chargeback_status
            and not payment.refund_due_minor)


def _charged_share(payment: Payment, amount_minor: int) -> int:
    """*amount_minor* of the contractual amount, in what the customer was charged: the same
    fraction of the charge-currency amount when one was fixed at pricing time (§17.1)."""
    charged, _currency = _charge_of(payment)
    if amount_minor >= payment.amount_minor:
        return charged
    return int((Decimal(charged) * amount_minor / payment.amount_minor).to_integral_value(rounding=ROUND_HALF_UP))


def _charge_of(payment: Payment) -> Tuple[int, TransactionCurrency]:
    """What the customer is charged: the quoted charge currency when one was fixed at pricing
    time (§17.1), otherwise the contractual amount itself."""
    if payment.charge_amount_minor and payment.charge_currency:
        return payment.charge_amount_minor, TransactionCurrency(payment.charge_currency)
    return payment.amount_minor, TransactionCurrency(payment.currency)


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
        gateway_factory: PaymentGatewayFactory,
        refund_request_service: RefundRequestService,
    ):
        self._payment_repo = payment_repo
        self._verification_service = verification_service
        self._task_service = task_service
        self._user_service = user_service
        self._idempotency = idempotency_service
        self._audit = audit_service
        self._gateways = gateway_factory
        self._refund_requests = refund_request_service

    async def requires_phone_verification(self, customer_id: str) -> bool:
        """The pay-step phone gate (§10.5): a customer must verify their phone before paying.

        One rule for every payment surface — the portal pay page renders its phone gate from
        the session, and the WhatsApp pay landing (which has no session) asks this directly."""
        user = await self._user_service.get_user_model(customer_id)
        return not user.phone_verified

    async def initiate(
        self,
        verification_id: str,
        customer_id: str,
        method: PaymentMethodKind,
        idempotency_key: Optional[str] = None,
        return_path: Optional[str] = None,
    ) -> Payment:
        """Open a charge for a submitted verification. A live charge opens the gateway's
        hosted checkout, which sends the customer back to *return_path* (the portal pay page
        by default; the WhatsApp handoff has no session and returns to its own page)."""
        verification = await self._verification_service.get_owned(verification_id, customer_id)
        if verification.status not in _PAYABLE:
            raise InvalidResourceStateException(
                resource="verification",
                message="This verification is not awaiting payment.",
            )

        if await self.requires_phone_verification(customer_id):
            raise ValidationException(message="Verify your phone number before paying.")

        if idempotency_key:
            outcome = await self._idempotency.begin_or_replay(idempotency_key, _INITIATE_SCOPE)
            if outcome.is_replay and outcome.resource_id:
                existing = await self._payment_repo.get_model(outcome.resource_id)
                if existing:
                    return existing

        tx_ref = f"{verification.vid}-{Utils.random_str(8)}"
        payment = await self._payment_repo.create_return_model(CreatePaymentDto(
            verification_id=verification_id,
            customer_id=customer_id,
            tx_ref=tx_ref,
            method=method,
            amount_minor=verification.price_locked_minor or 0,
            currency=verification.currency,
            charge_currency=verification.charge_currency,
            charge_amount_minor=verification.charge_amount_minor,
            provider=self._new_charge_provider(),
            status=PaymentStatus.INITIATED,
            checkout_url=self._stub_checkout_url(verification_id, tx_ref),
        ))
        if not settings.PAYMENT_STUB_MODE:
            await self._open_hosted_checkout(payment, verification.vid, return_path)

        await self._verification_service.mark_payment_pending(verification_id)

        self._audit.schedule(
            action=AuditActionType.PAYMENT_INITIATED,
            resource_type="payment",
            resource_id=payment.id,
            actor_id=customer_id,
            details={"verification_id": verification_id, "tx_ref": tx_ref},
        )

        if idempotency_key:
            await self._idempotency.complete(idempotency_key, _INITIATE_SCOPE, resource_id=payment.id)
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
        payment = await self._payment_repo.create_return_model(CreatePaymentDto(
            verification_id=verification_id,
            customer_id=customer_id,
            tx_ref=tx_ref,
            method=method,
            purpose=purpose,
            amount_minor=amount_minor,
            currency=verification.currency,
            provider=self._new_charge_provider(),
            status=PaymentStatus.INITIATED,
            checkout_url=self._stub_checkout_url(verification_id, tx_ref),
        ))
        if not settings.PAYMENT_STUB_MODE:
            await self._open_hosted_checkout(payment, verification.vid)
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

        payment = await self._payment_repo.get_by_tx_ref(dto.tx_ref)
        if not payment:
            raise ResourceNotFoundException(resource="payment")

        if dto.succeeded:
            # The charge settles once. A second success event for it (a different event id,
            # so the dedup above lets it through) finds it no longer open and stands down
            # before paying the verification, its tasks or a referral credit a second time.
            settled = await self._payment_repo.claim_transition(
                payment.id, _OPEN_PAYMENT_STATUSES, PaymentStatus.SUCCEEDED, gateway_event_id=dto.event_id,
            )
            if settled is None:
                return False
            self._audit.schedule(
                action=AuditActionType.PAYMENT_SUCCEEDED,
                resource_type="payment",
                resource_id=payment.id,
                actor_id=payment.customer_id,
                details={"verification_id": payment.verification_id, "purpose": payment.purpose},
            )
            # A charge can settle after its case closed (cancelled while the payment was
            # pending). The case must not reopen; the money goes back through Finance.
            verification = await self._verification_service.get_by_id(payment.verification_id)
            if verification.status in VERIFICATION_TERMINAL:
                await self._refund_late_charge(payment, verification.status)
                return True
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
            # A failure never lands on a settled payment (a late event must not undo a
            # success), and the attempt is counted in SQL so concurrent failures all count.
            failed = await self._payment_repo.claim_transition(
                payment.id, _OPEN_PAYMENT_STATUSES, PaymentStatus.FAILED,
                gateway_event_id=dto.event_id, increments={"failure_count": 1},
            )
            if failed is None:
                return False
            self._audit.schedule(
                action=AuditActionType.PAYMENT_FAILED,
                resource_type="payment",
                resource_id=payment.id,
                actor_id=payment.customer_id,
            )
        return True

    async def confirm_from_gateway(self, tx_ref: str) -> bool:
        """Settle a live payment from the gateway's own account of the charge.

        Webhooks and the pay page's return both land here, and neither is trusted on its own
        word: the charge is looked up at the gateway, and it settles the payment only when its
        reference, amount and currency match what the customer was asked to pay. A match goes
        through the idempotent ``handle_webhook``, keyed on the gateway's transaction and
        status, so the webhook and the return path settle a charge once between them.
        Returns whether anything changed.
        """
        payment = await self._payment_repo.get_by_tx_ref(tx_ref)
        if payment is None:
            # Another integration on the same gateway account, or a reference we never issued.
            logger.warning(f"Gateway event for unknown tx_ref {tx_ref!r} ignored")
            return False
        if payment.status not in _OPEN_PAYMENT_VALUES or not payment.provider:
            return False  # settled, or a stub payment with no gateway to ask
        if payment.chargeback_status:
            # The issuer owns this charge's outcome now; its gateway status no longer is ours.
            return False

        gateway = self._gateways.for_platform(IntegratedPlatform(payment.provider))
        charge = await gateway.get_charge(tx_ref)
        if charge is None or charge.status == GatewayChargeStatus.PENDING:
            return False
        if charge.status == GatewayChargeStatus.FAILED and payment.status == PaymentStatus.FAILED.value:
            return False  # already recorded; a revisit must not count the failure again

        expected_amount, expected_currency = _charge_of(payment)
        if (charge.reference, charge.amount_minor, charge.currency) != (tx_ref, expected_amount, expected_currency):
            # Reported once per charge: every poll and redelivery would otherwise add a row.
            if not await self._idempotency.claim(
                f"{payment.provider}:{charge.gateway_transaction_id}:MISMATCH", _WEBHOOK_SCOPE,
            ):
                return False
            logger.error(
                f"Charge for {tx_ref} does not match the quote: gateway reported "
                f"{charge.reference} {charge.amount_minor} {charge.currency.value}, "
                f"expected {expected_amount} {expected_currency.value}"
            )
            self._audit.schedule(
                action=AuditActionType.PAYMENT_AMOUNT_MISMATCH,
                resource_type="payment", resource_id=payment.id, actor_id=payment.customer_id,
                details={
                    "tx_ref": tx_ref, "gateway_reference": charge.gateway_reference,
                    "reported_amount_minor": charge.amount_minor, "reported_currency": charge.currency.value,
                    "expected_amount_minor": expected_amount, "expected_currency": expected_currency.value,
                },
            )
            return False

        if payment.gateway_reference != charge.gateway_reference:
            await self._payment_repo.update(payment.id, UpdatePaymentDto(gateway_reference=charge.gateway_reference))
        return await self.handle_webhook(PaymentWebhookDto(
            event_id=f"{payment.provider}:{charge.gateway_transaction_id}:{charge.status.value}",
            tx_ref=tx_ref,
            succeeded=charge.status == GatewayChargeStatus.SUCCEEDED,
        ))

    async def reconcile_for_verification(self, verification_id: str, customer_id: str) -> Optional[Payment]:
        """The customer's return from a hosted checkout, or a reload of the pay page.

        Asks the gateway about the verification's latest payment, so a charge whose webhook
        is late or lost still settles, and returns it. Older open payments are left to their
        own webhooks. The stub path settles only through its own confirm step."""
        await self._verification_service.get_owned(verification_id, customer_id)
        return await self._reconcile_latest(verification_id)

    async def reconcile_for_handoff(self, verification_id: str) -> Optional[Payment]:
        """The WhatsApp handoff's return from a hosted checkout. Its caller holds a grant
        scoped to this one case (§26.5), which is the authorization, so no ownership check."""
        return await self._reconcile_latest(verification_id)

    async def record_chargeback(
        self,
        platform: IntegratedPlatform,
        *,
        event_id: str,
        tx_ref: Optional[str] = None,
        gateway_reference: Optional[str] = None,
        reason: Optional[str] = None,
        amount_minor: Optional[int] = None,
    ):
        """Route a gateway's dispute notice to the chargeback flow (§6a).

        Gateways cite a disputed charge differently (Paystack by our reference, Flutterwave
        only by its own), so the payment is found by either. A dispute over a charge we do
        not hold is logged and dropped."""
        payment = None
        if tx_ref:
            payment = await self._payment_repo.get_by_tx_ref(tx_ref)
        elif gateway_reference:
            payment = await self._payment_repo.get_by_gateway_reference(platform.value, gateway_reference)
        if payment is None:
            logger.warning(f"{platform.value} chargeback {event_id} names no payment we hold; ignored")
            return None
        return await self._chargeback_service().handle_webhook(ChargebackWebhookDto(
            event_id=event_id, tx_ref=payment.tx_ref, reason=reason, amount_minor=amount_minor,
        ))

    async def get_payment(self, payment_id: str) -> Optional[Payment]:
        return await self._payment_repo.get_model(payment_id)

    async def refund(
        self, verification_id: str, amount_minor: int, actor_id: str, reason: Optional[str] = None,
        payment_ids: Optional[Collection[str]] = None,
    ) -> RefundOutcome:
        """Send *amount_minor* back to the customer (§8.5), spread across the case's settled
        charges oldest first — part of a charge when the amount runs out.

        Only an approved refund request calls this (refund_request/): no other path may move
        a customer's money. Each charge is claimed first, so a concurrent refund skips it, and
        is then refunded at its gateway. A refusal puts that charge alone back to SUCCEEDED,
        still owing its share (`refund_due_minor`) for Finance to retry; the others stay
        refunded, so our record never disagrees with where the money is. A charge under a
        chargeback is held: the issuer is already returning that money. The stub path moves
        no money.

        **Call it last in its transaction.** Money leaves at the gateway as it runs, so
        nothing that could still roll the transaction back may follow it."""
        payments = await self._payment_repo.list_for_verification(verification_id)
        if payment_ids is not None:
            # A late charge is refunded by itself, never through the case's older charges.
            wanted = {Utils.uuid_to_hex(pid) for pid in payment_ids}
            payments = [p for p in payments if Utils.uuid_to_hex(p.id) in wanted]
        refundable = sum(p.amount_minor for p in payments if _refundable(p))
        if amount_minor > refundable:
            raise ValidationException(
                message="The refund is more than this case's settled charges can return.",
            )
        outcome = RefundOutcome()
        remaining = amount_minor
        for payment in payments:
            if payment.status != PaymentStatus.SUCCEEDED.value or payment.refund_due_minor:
                continue  # settled elsewhere, or already owing a refund Finance approved
            if payment.chargeback_status:
                outcome.held_payment_ids.append(Utils.uuid_to_hex(payment.id))
                continue
            if remaining <= 0:
                break
            share = min(remaining, int(payment.amount_minor))
            remaining -= share
            try:
                if await self._refund_one(payment, share, actor_id, reason):
                    outcome.refunded_minor += share
            except _GatewayRefundRefused:
                outcome.failed_payment_ids.append(Utils.uuid_to_hex(payment.id))
        return outcome

    async def refundable_minor(self, verification_id: str) -> int:
        """What `refund` would send back right now: settled charges not under a chargeback.
        The admin confirms this amount before cancelling a paid case."""
        return sum(
            p.amount_minor for p in await self._payment_repo.list_for_verification(verification_id)
            if _refundable(p)
        )

    async def retry_refund(self, payment_id: str, admin_id: str) -> Payment:
        """Finance retries a refund the gateway refused (§18.1): exactly what the charge still
        owes of an approved refund. A charge owing nothing never qualifies (a retry resends an
        approved refund, it never starts one); a second refusal raises and keeps the debt."""
        payment = await self._payment_repo.get_model(payment_id)
        if payment is None:
            raise ResourceNotFoundException(resource="payment")
        if (payment.status != PaymentStatus.SUCCEEDED.value or payment.chargeback_status
                or not payment.refund_due_minor):
            raise InvalidResourceStateException(
                resource="payment", message="This payment is not awaiting a refund.",
            )
        try:
            await self._refund_one(payment, payment.refund_due_minor, admin_id, reason="finance_refund_retry")
        except _GatewayRefundRefused:
            raise IntegrationException("The payment gateway declined the refund. Try again later.") from None
        return await self._payment_repo.get_model(payment_id)

    async def page_for_admin(
        self, page: int, page_size: int, query: Optional[str], status: Optional[PaymentStatus],
        order_by: Optional[str] = None,
    ) -> Page[AdminPaymentDto]:
        """Finance's payments list (§18.1): every charge, newest first unless *order_by* says otherwise."""
        rows, total, applied = await self._payment_repo.page_for_admin(page, page_size, query, status, order_by)
        return DbUtils.build_page(
            [admin_payment_to_dto(p, vid) for p, vid in rows], total, page, page_size,
            sort=applied, sortable=ADMIN_PAYMENT_SORTABLE,
        )

    async def page_refunds_to_retry(self, page: int, page_size: int) -> Page[PaymentDto]:
        rows, total = await self._payment_repo.page_refunds_to_retry(page, page_size)
        return self._payment_repo._db_utils.build_page([payment_to_dto(p) for p in rows], total, page, page_size)

    async def _refund_one(self, payment: Payment, amount_minor: int, actor_id: str, reason: Optional[str]) -> bool:
        """Claim, then refund *amount_minor* of *payment* at its gateway. False when another
        refund got there first; raises ``_GatewayRefundRefused`` when the gateway refuses, with
        the claim undone and the amount left owing on the charge."""
        refunded = await self._payment_repo.claim_transition(
            payment.id, [PaymentStatus.SUCCEEDED], PaymentStatus.REFUNDED,
            refunded_amount_minor=amount_minor, refund_due_minor=None,
        )
        if refunded is None:
            return False
        if not settings.PAYMENT_STUB_MODE and payment.provider:
            try:
                gateway = self._gateways.for_platform(IntegratedPlatform(payment.provider))
                await gateway.refund_charge(payment.tx_ref, _charged_share(payment, amount_minor), reason)
            except Exception as e:
                await self._payment_repo.claim_transition(
                    payment.id, [PaymentStatus.REFUNDED], PaymentStatus.SUCCEEDED,
                    refunded_amount_minor=None, refund_due_minor=amount_minor,
                )
                log_fault_once(e, f"refund of payment {payment.tx_ref}")
                self._audit.schedule(
                    action=AuditActionType.PAYMENT_REFUND_FAILED,
                    resource_type="payment", resource_id=payment.id, actor_id=actor_id,
                    details={"verification_id": payment.verification_id, "tx_ref": payment.tx_ref,
                             "amount_minor": amount_minor, "reason": reason},
                )
                raise _GatewayRefundRefused() from e
        self._audit.schedule(
            action=AuditActionType.PAYMENT_REFUNDED,
            resource_type="payment", resource_id=payment.id, actor_id=actor_id,
            details={"verification_id": payment.verification_id, "amount_minor": amount_minor,
                     "reason": reason},
        )
        return True

    async def _refund_late_charge(self, payment: Payment, case_status: str) -> None:
        """File a full refund request for a charge that settled on a closed case. It still
        waits for Finance: no customer money leaves unapproved."""
        await self._refund_requests.file(
            verification_id=payment.verification_id, customer_id=payment.customer_id,
            source=RefundSource.LATE_CHARGE, amount_minor=payment.amount_minor,
            currency=TransactionCurrency(payment.currency), requested_by=None,
            reason=RefundSource.LATE_CHARGE.value, payment_id=Utils.uuid_to_hex(payment.id),
            note=f"Charge {payment.tx_ref} settled after the case was {case_status.lower()}.",
        )

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

    async def _reconcile_latest(self, verification_id: str) -> Optional[Payment]:
        payments = await self._payment_repo.list_for_verification(verification_id)
        latest = max(payments, key=lambda p: p.date_created, default=None)
        if latest is None:
            return None
        if not settings.PAYMENT_STUB_MODE and latest.status in _OPEN_PAYMENT_VALUES and latest.provider:
            try:
                await self.confirm_from_gateway(latest.tx_ref)
            except IntegrationException as e:
                # A gateway that cannot answer now is asked again on the next visit or poll.
                logger.warning(f"Could not reconcile {latest.tx_ref} with its gateway: {e.message}")
        return await self._payment_repo.get_model(latest.id)

    @staticmethod
    def _chargeback_service() -> "ChargebackService":
        """Resolved lazily: the chargeback domain reads payments, so importing it at module
        load would be a cycle."""
        from main.app.domain.payment.chargeback.service import ChargebackService
        return di[ChargebackService]

    def _new_charge_provider(self) -> Optional[str]:
        """The platform a new charge is made on; None on the stub path, which has no gateway."""
        return None if settings.PAYMENT_STUB_MODE else self._gateways.active().platform.value

    @staticmethod
    def _stub_checkout_url(verification_id: str, tx_ref: str) -> Optional[str]:
        """The stub path's "checkout": the pay page itself, which completes via the stub confirm.
        A live charge's URL comes from the gateway (`_open_hosted_checkout`)."""
        if not settings.PAYMENT_STUB_MODE:
            return None
        return f"{verification_path(verification_id, VerificationPage.PAY)}?txRef={tx_ref}&stub=1"

    async def _open_hosted_checkout(self, payment: Payment, vid: str, return_path: Optional[str] = None) -> None:
        """Open the active gateway's hosted checkout for *payment* and record its URL.

        The customer comes back to the pay page, which reconciles with the gateway, so a lost
        webhook never strands a paid customer."""
        customer = await self._user_service.get_user_model(payment.customer_id)
        amount_minor, currency = _charge_of(payment)
        url = await self._gateways.active().create_hosted_checkout(HostedCheckoutRequest(
            reference=payment.tx_ref,
            amount_minor=amount_minor,
            currency=currency,
            redirect_url=absolute_url(return_path or verification_path(payment.verification_id, VerificationPage.PAY)),
            customer_email=customer.email,
            customer_phone=customer.phone,
            customer_name=f"{customer.first_name} {customer.last_name}".strip(),
            title=_CHECKOUT_TITLE,
            description=f"Verification {vid}",
        ))
        await self._payment_repo.update(payment.id, UpdatePaymentDto(checkout_url=url))
        payment.checkout_url = url
