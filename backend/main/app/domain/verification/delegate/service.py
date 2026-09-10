"""Per-case delegates (PRD §26.4.5, Decision O, D67/D77; WA-26).

Authorization, OTP verification, revocation, and the two lookups everything else depends
on: *does this number hold a delegation?* (the bot) and *who should this milestone also
reach?* (the notification router).

Two rules are worth stating plainly because everything else follows from them:

* **The buyer authorizes, and only the buyer.** Every write goes through
  `VerificationService.get_owned`, so ownership is proved against the case rather than
  taken from the request.
* **The grant is status-only, and that is structural.** The delegate audience sends the
  `delegate_status` template, which declares a case reference and a status label and
  nothing else — there is no link parameter for a report to travel in, so no code path
  can hand a delegate one by mistake.
"""
from __future__ import annotations

from logging import Logger
from typing import List, Optional

from kink import di, inject

from main.app.core.events import DomainEvent, EventType, publish_domain_event
from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.user.auth.models import OtpChannel
from main.app.domain.user.auth.otp_service import OtpService
from main.app.domain.verification.delegate.models import (
    CaseDelegate,
    CaseDelegateChallengeDto,
    CaseDelegateDto,
    CreateCaseDelegateDto,
)
from main.app.domain.verification.delegate.repo import CaseDelegateRepo
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.service import VerificationService
from main.appodus_utils import Utils
from main.appodus_utils.db.types.phone import PhoneNumber
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ResourceNotFoundException,
    ValidationException,
)
from main.appodus_utils.integrations.messaging.providers.whatsapp.phone import to_e164

logger: Logger = di["logger"]

# One live delegate per case (§26.4.5). Refused here rather than left to a constraint so
# the buyer is told what is in the way — and told it about the *case*, never about who
# else might hold the number.
ALREADY_DELEGATED_MESSAGE = (
    "This verification already has a delegate. Revoke the current one first."
)

# '+' plus a country code and a subscriber number. Shorter is a typo, and sending a code
# to it would only burn the number's resend allowance.
MIN_E164_LENGTH = 9

_AUDIT_RESOURCE = "case_delegate"


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class CaseDelegateService:
    def __init__(
        self,
        case_delegate_repo: CaseDelegateRepo,
        verification_service: VerificationService,
        verification_repo: VerificationRepo,
        otp_service: OtpService,
        audit_service: AuditLogService,
    ):
        self._case_delegate_repo = case_delegate_repo
        self._verification_service = verification_service
        self._verification_repo = verification_repo
        self._otp = otp_service
        self._audit = audit_service

    # ── The buyer's surface ───────────────────────────────────────

    async def list_for_case(self, verification_id: str, customer_id: str) -> List[CaseDelegateDto]:
        """The case's delegate, as the case page renders it. At most one (§26.4.5)."""
        await self._verification_service.get_owned(verification_id, customer_id)
        delegate = await self._case_delegate_repo.get_live_for_case(verification_id)
        return [self._to_dto(delegate)] if delegate else []

    async def authorize(
        self, verification_id: str, customer_id: str, name: str, phone_e164: str
    ) -> CaseDelegateChallengeDto:
        """Nominate a delegate and send them a code (§26.4.5).

        Nothing is visible yet. The row exists so the one-per-case slot is taken, but
        `verified_at` stays null until they answer — an authorization the delegate never
        confirmed grants exactly as much as no authorization at all.
        """
        await self._verification_service.get_owned(verification_id, customer_id)

        normalized = to_e164(phone_e164)
        if len(normalized) < MIN_E164_LENGTH:
            raise ValidationException(
                message="Enter a valid WhatsApp number in international format."
            )
        if not name.strip():
            raise ValidationException(message="Enter the delegate's name.")

        if await self._case_delegate_repo.get_live_for_case(verification_id) is not None:
            raise ValidationException(message=ALREADY_DELEGATED_MESSAGE)

        await self._case_delegate_repo.create_return_model(CreateCaseDelegateDto(
            verification_id=verification_id, name=name.strip(), phone_e164=normalized,
        ))
        self._audit.schedule(
            AuditActionType.CASE_DELEGATE_AUTHORIZED,
            resource_type=_AUDIT_RESOURCE, resource_id=verification_id, actor_id=customer_id,
            details={"phone_e164": normalized, "name": name.strip()},
        )
        return CaseDelegateChallengeDto(
            phone_e164=normalized,
            resend_after_seconds=await self._otp.send_otp(
                OtpChannel.WHATSAPP, PhoneNumber.from_e164(normalized), user_id=customer_id
            ),
        )

    async def confirm(
        self, verification_id: str, customer_id: str, code: str
    ) -> CaseDelegateDto:
        """Prove the delegate controls the number, and start their visibility.

        The buyer relays the code, which is the §26.4.5 "narrower grant" in practice: the
        delegate never touches the website, and the person who authorized them is the one
        who completes it.
        """
        await self._verification_service.get_owned(verification_id, customer_id)
        delegate = await self._case_delegate_repo.get_live_for_case(verification_id)
        if delegate is None:
            raise ResourceNotFoundException(resource="delegate")

        await self._otp.verify_otp(
            OtpChannel.WHATSAPP,
            PhoneNumber.from_e164(delegate.phone_e164),
            code,
            user_id=customer_id,
        )
        self._case_delegate_repo.verify(delegate, Utils.datetime_now())
        return self._to_dto(delegate)

    async def revoke(
        self, verification_id: str, customer_id: str, reason: str = "customer_request"
    ) -> None:
        """End the delegation. Effective on the next event, because the audience is
        resolved at send time rather than stored anywhere (§26.4.5)."""
        await self._verification_service.get_owned(verification_id, customer_id)
        delegate = await self._case_delegate_repo.get_live_for_case(verification_id)
        if delegate is None:
            raise ResourceNotFoundException(resource="delegate")
        await self._revoke_row(delegate, reason, actor_id=customer_id)

    # ── The bot's lookup (§26.4.3's second question) ───────────────

    async def resolve_delegate_for_phone(self, phone_e164: str) -> Optional[CaseDelegate]:
        """The delegation this number holds, or ``None``.

        Deliberately **beside** `WhatsAppLinkService.resolve_user_for_phone` rather than
        inside it (D67): that function stays the channel's single *account* lookup and
        therefore its single audit surface, and the bot asks this one only after it has
        answered `None`. A number that is both a customer's and a delegate's resolves as
        the customer — the account grant is strictly wider, and reading it as a delegate
        would lose that person their own data.
        """
        return await self._case_delegate_repo.get_active_by_phone(to_e164(phone_e164))

    # ── The milestone audience (D65) ──────────────────────────────

    async def notify_milestone(self, verification_id: str) -> None:
        """Send this case's delegate their status-only milestone, if it has one.

        Called from the notification subscriber for every `whatsapp=True` rule, so a
        delegate hears about the same four moments the customer does — as
        `delegate_status`, never as the customer's template.
        """
        delegate = await self._case_delegate_repo.get_active_for_case(verification_id)
        if delegate is None:
            return
        verification = await self._verification_repo.get_model(verification_id)
        if verification is None:
            return

        from main.app.domain.channel.whatsapp.milestones import (
            WhatsAppMilestoneSender,
            status_label_for,
        )

        await di[WhatsAppMilestoneSender].send_delegate_milestone(
            delegate.phone_e164,
            verification.vid,
            status_label_for(verification),
            delegate_name=delegate.name,
        )

    # ── STOP from a delegate's number (D77) ───────────────────────

    async def revoke_by_phone(self, phone_e164: str) -> Optional[CaseDelegate]:
        """Honour an opt-out from a number that is a delegate and nothing else.

        A delegate has no account and therefore no consent row, so ending the delegation
        is the only lever that actually stops the messages — and continuing to message
        someone who typed STOP is what moves a Meta quality rating. The account holder is
        told, because the useful response is to authorize somebody else.
        """
        delegate = await self._case_delegate_repo.get_active_by_phone(to_e164(phone_e164))
        if delegate is None:
            return None
        await self._revoke_row(delegate, "delegate_opt_out", actor_id=None)

        verification = await self._verification_repo.get_model(delegate.verification_id)
        if verification is not None:
            await publish_domain_event(DomainEvent(
                type=EventType.DELEGATE_REVOKED,
                verification_id=delegate.verification_id,
                recipient_user_ids=(verification.customer_id,),
                data={"name": delegate.name, "vid": verification.vid},
            ))
        return delegate

    # ── Internals ─────────────────────────────────────────────────

    async def _revoke_row(
        self, delegate: CaseDelegate, reason: str, actor_id: Optional[str]
    ) -> None:
        self._case_delegate_repo.revoke(delegate, reason, Utils.datetime_now())
        self._audit.schedule(
            AuditActionType.CASE_DELEGATE_REVOKED,
            resource_type=_AUDIT_RESOURCE,
            resource_id=delegate.verification_id,
            actor_id=actor_id,
            details={"phone_e164": delegate.phone_e164, "reason": reason},
        )

    @staticmethod
    def _to_dto(delegate: CaseDelegate) -> CaseDelegateDto:
        return CaseDelegateDto(
            id=Utils.uuid_to_hex(delegate.id),
            name=delegate.name,
            phone_e164=delegate.phone_e164,
            verified=delegate.verified_at is not None,
            verified_at=delegate.verified_at,
            revoked_at=delegate.revoked_at,
            revoked_reason=delegate.revoked_reason,
        )
