"""Re-check service (PRD §14.1).

Customer requests a new verification cycle on a completed report; the admin approves and
scopes which roles to redo; the customer pays the re-check fee (a percentage of the original
tier price, D26); on payment the scoped tasks reopen and the verification returns to work.
The next release bumps the report to v2.0 (revision_kind RECHECK).
"""
from __future__ import annotations

from typing import List, Optional

from kink import inject

from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.core.state.status import (
    AgentRole,
    ReportRevisionKind,
    VerificationStatus,
)
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.payment.models import PaymentPurpose
from main.app.domain.payment.service import PaymentService
from main.app.domain.system_config.models import ConfigKey
from main.app.domain.system_config.service import ConfigService
from main.app.domain.verification.models import UpdateVerificationDto
from main.app.domain.verification.pricing import recheck_price_kobo
from main.app.domain.verification.recheck.models import (
    CreateRecheckDto,
    DecideRecheckDto,
    RecheckDto,
    RecheckRequest,
    RecheckStatus,
    RequestRecheckDto,
    UpdateRecheckDto,
)
from main.app.domain.verification.pricing_config.service import PricingConfigService
from main.app.domain.verification.recheck.repo import RecheckRepo
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.review.service import ReviewService
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

from main.app.core.state.status import VerificationTier


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class RecheckService:
    def __init__(
        self,
        recheck_repo: RecheckRepo,
        verification_service: VerificationService,
        verification_repo: VerificationRepo,
        review_service: ReviewService,
        payment_service: PaymentService,
        config_service: ConfigService,
        pricing_config_service: PricingConfigService,
        audit_service: AuditLogService,
    ):
        self._recheck_repo = recheck_repo
        self._verifications = verification_service
        self._verification_repo = verification_repo
        self._reviews = review_service
        self._payments = payment_service
        self._config = config_service
        self._pricing = pricing_config_service
        self._audit = audit_service

    async def request(
        self, verification_id: str, customer_id: str, dto: RequestRecheckDto
    ) -> RecheckRequest:
        """Customer requests a re-check on a completed report (§14.1)."""
        v = await self._verifications.get_owned(verification_id, customer_id)
        if v.status != VerificationStatus.COMPLETED.value:
            raise InvalidResourceStateException(
                resource="verification",
                message="A re-check can only be requested on a completed report.",
            )
        if not (dto.reason or "").strip():
            raise ValidationException(message="A reason is required for a re-check.")

        pct = await self._config.get_int(ConfigKey.RECHECK_PRICE_PCT)
        base = await self._pricing.tier_price_kobo(VerificationTier(v.tier))
        price = recheck_price_kobo(base, pct)
        recheck = await self._recheck_repo.create_return_model(CreateRecheckDto(
            verification_id=Utils.uuid_to_hex(v.id),
            customer_id=customer_id,
            reason=dto.reason.strip(),
            documents=dto.documents,
            price_minor=price,
            status=RecheckStatus.PENDING,
        ))
        self._audit.schedule(
            action=AuditActionType.RECHECK_REQUESTED,
            resource_type="recheck", resource_id=recheck.id, actor_id=customer_id,
            details={"verification_id": verification_id, "price_minor": price},
        )
        return recheck

    async def admin_decide(
        self, recheck_id: str, dto: DecideRecheckDto, admin_id: str
    ) -> RecheckRequest:
        """Admin approves (+ scopes) or rejects a pending re-check (§14.1)."""
        recheck = await self._get(recheck_id)
        if recheck.status != RecheckStatus.PENDING.value:
            raise InvalidResourceStateException(
                resource="recheck", message="This re-check has already been decided."
            )

        if not dto.approve:
            await self._recheck_repo.update(recheck.id, UpdateRecheckDto(
                status=RecheckStatus.REJECTED.value, decision_note=dto.note,
            ))
            await self._notify_decision(recheck, approved=False)
            self._audit.schedule(
                action=AuditActionType.RECHECK_REJECTED,
                resource_type="recheck", resource_id=recheck.id, actor_id=admin_id,
                details={"verification_id": recheck.verification_id, "note": dto.note},
            )
            return await self._recheck_repo.get_model(recheck.id)

        roles = [r.value for r in (dto.scope_roles or [])]
        if not roles:
            raise ValidationException(message="Select at least one role to re-check.")

        payment = await self._payments.initiate_secondary(
            verification_id=recheck.verification_id, customer_id=recheck.customer_id,
            amount_minor=recheck.price_minor, purpose=PaymentPurpose.RECHECK,
        )
        payment_ref = Utils.uuid_to_hex(payment.id)  # entity ref → .hex (32-char)
        await self._recheck_repo.update(recheck.id, UpdateRecheckDto(
            status=RecheckStatus.APPROVED.value, scope_roles=roles,
            payment_id=payment_ref, decision_note=dto.note,
        ))
        await self._notify_decision(recheck, approved=True)
        self._audit.schedule(
            action=AuditActionType.RECHECK_APPROVED,
            resource_type="recheck", resource_id=recheck.id, actor_id=admin_id,
            details={"verification_id": recheck.verification_id, "roles": roles,
                     "payment_id": payment_ref},
        )
        return await self._recheck_repo.get_model(recheck.id)

    async def on_payment_confirmed(self, payment_id: str) -> None:
        """The scoped tasks reopen once the re-check fee is paid (webhook, §14.1). Idempotent:
        a replayed confirmation for an already-started re-check is a no-op."""
        recheck = await self._recheck_repo.get_by_payment(Utils.uuid_to_hex(payment_id))
        if recheck is None or recheck.status != RecheckStatus.APPROVED.value:
            return
        # Record the version-bump reason so the next release becomes v2.0.
        await self._verification_repo.update(
            recheck.verification_id,
            UpdateVerificationDto(pending_revision_kind=ReportRevisionKind.RECHECK.value),
        )
        for role_value in (recheck.scope_roles or []):
            await self._reviews.reopen_task(
                recheck.verification_id, AgentRole(role_value), recheck.customer_id
            )
        await self._recheck_repo.update(recheck.id, UpdateRecheckDto(status=RecheckStatus.STARTED.value))
        self._audit.schedule(
            action=AuditActionType.RECHECK_STARTED,
            resource_type="recheck", resource_id=recheck.id, actor_id=recheck.customer_id,
            details={"verification_id": recheck.verification_id, "roles": recheck.scope_roles},
        )

    async def list_for_verification(self, verification_id: str, customer_id: str) -> List[RecheckRequest]:
        v = await self._verifications.get_owned(verification_id, customer_id)
        return await self._recheck_repo.list_for_verification(Utils.uuid_to_hex(v.id))

    async def page_pending(self, page: int, page_size: int):
        """Admin queue of pending re-check requests (paged). Checkout URL is omitted — the
        admin decides, the customer pays."""
        rows, total = await self._recheck_repo.page_pending(offset=page * page_size, limit=page_size)
        dtos = [
            RecheckDto(
                id=r.id, verification_id=r.verification_id, reason=r.reason, documents=r.documents,
                scope_roles=r.scope_roles, status=RecheckStatus(r.status), price_minor=r.price_minor,
                payment_id=r.payment_id, decision_note=r.decision_note, date_created=r.date_created,
            )
            for r in rows
        ]
        return self._recheck_repo._db_utils.build_page(dtos, total, page, page_size)

    # ── helpers ───────────────────────────────────────────────────

    async def _get(self, recheck_id: str) -> RecheckRequest:
        recheck = await self._recheck_repo.get_model(recheck_id)
        if recheck is None:
            raise ResourceNotFoundException(resource="recheck")
        return recheck

    async def _notify_decision(self, recheck: RecheckRequest, approved: bool) -> None:
        """Publish the §12.2 re-check decision notification to the customer (best-effort)."""
        await publish_domain_event(DomainEvent(
            type=EventType.RECHECK_DECISION, verification_id=recheck.verification_id,
            recipient_user_ids=(recheck.customer_id,),
            data={"decision": "APPROVED" if approved else "REJECTED"},
        ))
