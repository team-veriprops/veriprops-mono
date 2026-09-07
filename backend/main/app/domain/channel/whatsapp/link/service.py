"""WhatsApp account linking (PRD §26.4.4, WA-23/WA-24/WA-25).

Two directions, one destination. **Web→WhatsApp**: the customer types a number in account
settings, we send a code to it over WhatsApp, they type the code back on the website.
**WhatsApp→web**: an unlinked number asks the bot for something that needs identity, the
bot sends a signed link, and the customer logs in on the website and confirms the same
code. Both end in one ACTIVE row, because both prove the same two facts — *this account*
and *control of this number*.

The rules that make it worth trusting:

* **One account, one number.** Enforced at both ends by the unique constraints, checked
  here first so a collision reads as a refusal rather than a database error.
* **The number is never taken from the browser in the WhatsApp→web direction.** It comes
  out of the signed token the bot sent, so a logged-in attacker cannot nominate a number
  the bot never messaged and have a code posted to it.
* **A number change is a re-verification, not an edit.** The old number is released and
  its thread goes cold in the same transaction as the new attempt begins, so there is no
  window where a stale number still resolves to the account (§26.4.4).
* **Nothing here reads case data.** This module answers only "whose number is this?" —
  `resolve_user_for_phone` is the single lookup every flow downstream depends on, and it
  answers `None` for anything short of an ACTIVE link.
"""
from __future__ import annotations

from typing import Optional

from kink import inject

from main.app.domain.audit.models import AuditActionType
from main.app.domain.audit.service import AuditLogService
from main.app.domain.channel.whatsapp.handoff.service import HandoffTokenService
from main.app.domain.channel.whatsapp.link.models import (
    CreateWhatsAppLinkDto,
    WhatsAppLink,
    WhatsAppLinkChallengeDto,
    WhatsAppLinkStatus,
)
from main.app.domain.channel.whatsapp.link.repo import WhatsAppLinkRepo
from main.app.domain.communication.conversation.service import ConversationService
from main.app.domain.user.auth.models import OtpChannel
from main.app.domain.user.auth.otp_service import OtpService
from main.appodus_utils import Utils
from main.appodus_utils.db.types.phone import PhoneNumber
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import (
    ResourceNotFoundException,
    ValidationException,
)
from main.appodus_utils.integrations.messaging.providers.whatsapp.phone import (
    to_e164,
    to_wa_recipient,
)

# One message for both "already linked to you" and "linked to someone else". Which of the
# two it is would tell a prober whether a given number has a Veriprops account.
NUMBER_UNAVAILABLE_MESSAGE = "That WhatsApp number can't be linked to this account."

# '+' plus a country code and a subscriber number — shorter than this is a typo, not a
# number, and sending a code to it would only burn the resend allowance.
MIN_E164_LENGTH = 9

# The audit trail keys on the account, not on the link row: a number change replaces the
# row, and the history has to survive that.
_AUDIT_RESOURCE = "whatsapp_link"


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class WhatsAppLinkService:
    def __init__(
        self,
        whatsapp_link_repo: WhatsAppLinkRepo,
        otp_service: OtpService,
        conversation_service: ConversationService,
        handoff_token_service: HandoffTokenService,
        audit_service: AuditLogService,
    ):
        self._whatsapp_link_repo = whatsapp_link_repo
        self._otp = otp_service
        self._conversations = conversation_service
        self._handoff = handoff_token_service
        self._audit = audit_service

    # ── Reads ─────────────────────────────────────────────────────

    async def get_for_user(self, user_id: str) -> Optional[WhatsAppLink]:
        """This account's link row, whatever state it is in (drives the settings page)."""
        return await self._whatsapp_link_repo.get_by_user_id(user_id)

    async def resolve_user_for_phone(self, phone_e164: str) -> Optional[str]:
        """The account that owns *phone_e164*, or ``None``.

        **The single identity lookup for the whole channel.** Every flow that could leak
        case data — status, short-code continuation, delegates — funnels through here, so
        the "never read case data to an unverified number" rule (§26.4.3) is one function
        to audit rather than a habit to maintain at a dozen call sites.
        """
        link = await self._whatsapp_link_repo.get_active_by_phone(to_e164(phone_e164))
        return link.user_id if link else None

    async def resolve_phone_for_user(self, user_id: str) -> Optional[str]:
        """The WhatsApp number this account has verified, or ``None``.

        The outbound inverse of `resolve_user_for_phone`, and the **only** address a
        business-initiated message may use (D65). `users.phone` is a profile field that
        nobody proved control of over WhatsApp; addressing a milestone to it would deliver
        case details to a number that was never OTP-verified as this customer's — the
        §26.4.3 leak, running outwards.

        ACTIVE only, for the same reason the inbound direction is: a pending attempt is
        not a link.
        """
        link = await self._whatsapp_link_repo.get_by_user_id(user_id)
        if link is None or link.status != WhatsAppLinkStatus.ACTIVE.value:
            return None
        return link.phone_e164

    # ── Web → WhatsApp (§26.4.4) ───────────────────────────────────

    async def start_link(self, user_id: str, phone_e164: str) -> WhatsAppLinkChallengeDto:
        """Begin linking *phone_e164* to *user_id*; returns where the code went and for how long.

        A number already spoken for — by this account or any other — is refused here
        rather than left to the unique constraint, so the caller gets an answer instead
        of an integrity error.
        """
        normalized = to_e164(phone_e164)
        if len(normalized) < MIN_E164_LENGTH:
            raise ValidationException(
                message="Enter a valid WhatsApp number in international format."
            )

        holder = await self._whatsapp_link_repo.get_any_by_phone(normalized)
        if holder is not None and holder.user_id != user_id:
            raise ValidationException(message=NUMBER_UNAVAILABLE_MESSAGE)

        link = await self._whatsapp_link_repo.get_by_user_id(user_id)
        if link is None:
            link = await self._whatsapp_link_repo.create_return_model(CreateWhatsAppLinkDto(
                user_id=user_id,
                phone_e164=normalized,
                wa_id=to_wa_recipient(normalized),
                status=WhatsAppLinkStatus.PENDING,
            ))
        else:
            if link.status == WhatsAppLinkStatus.ACTIVE.value and link.phone_e164 != normalized:
                # A number change is a re-verification: release the old number (and its
                # thread) before the new attempt begins, so there is no window in which
                # both numbers resolve to this account.
                await self._release(link, reason="number_change")
            self._whatsapp_link_repo.claim_number(link, normalized, to_wa_recipient(normalized))

        return WhatsAppLinkChallengeDto(
            phone_e164=normalized,
            resend_after_seconds=await self._send_code(normalized, user_id),
        )

    async def confirm_link(self, user_id: str, phone_e164: str, code: str) -> WhatsAppLink:
        """Complete linking once the customer proves control of the number."""
        normalized = to_e164(phone_e164)
        link = await self._whatsapp_link_repo.get_by_user_id(user_id)
        if link is None or link.phone_e164 != normalized:
            # No pending attempt for this number on this account — refuse without saying
            # whether the number, the account, or the attempt is the part that is wrong.
            raise ResourceNotFoundException(resource="WhatsApp link")

        await self._otp.verify_otp(
            OtpChannel.WHATSAPP, PhoneNumber.from_e164(normalized), code, user_id=user_id
        )
        self._whatsapp_link_repo.activate(link, Utils.datetime_now())
        # §26.8: one conversation object per person. The thread this number has been
        # talking in gains an owner rather than a second thread being opened.
        await self._conversations.set_whatsapp_thread_owner(normalized, user_id)
        self._audit.schedule(
            AuditActionType.WHATSAPP_NUMBER_LINKED,
            resource_type=_AUDIT_RESOURCE,
            resource_id=user_id,
            actor_id=user_id,
            details={"phone_e164": normalized},
        )
        return link

    async def unlink(self, user_id: str, reason: str = "customer_request") -> None:
        """Drop the link and let the old thread go cold (§26.4.4)."""
        link = await self._whatsapp_link_repo.get_by_user_id(user_id)
        if link is None or link.status == WhatsAppLinkStatus.REVOKED.value:
            raise ResourceNotFoundException(resource="WhatsApp link")
        await self._release(link, reason=reason)

    # ── WhatsApp → web (§26.4.4) ───────────────────────────────────

    async def issue_link_invitation(self, phone_e164: str) -> str:
        """The signed link the bot sends an unlinked number. Carries the number, not a grant."""
        return await self._handoff.issue_link(to_e164(phone_e164))

    async def start_link_from_token(self, user_id: str, token: str) -> WhatsAppLinkChallengeDto:
        """Begin linking the number named by the bot's signed link.

        The number comes out of the token, never out of the request body: a logged-in
        attacker who guesses someone's number must also hold a link the bot sent to it.
        The token is *not* spent here — the customer may need a resend before the code
        lands, and spending it would strand them. It is spent on confirmation.
        """
        claims = await self._handoff.decode_link(token)
        return await self.start_link(user_id, claims.phone)

    async def confirm_link_from_token(self, user_id: str, token: str, code: str) -> WhatsAppLink:
        """Complete the WhatsApp→web direction, spending the bot's link exactly once."""
        claims = await self._handoff.redeem_link(token)
        return await self.confirm_link(user_id, claims.phone, code)

    # ── Internals ─────────────────────────────────────────────────

    async def _send_code(self, phone_e164: str, user_id: str) -> int:
        return await self._otp.send_otp(
            OtpChannel.WHATSAPP, PhoneNumber.from_e164(phone_e164), user_id=user_id
        )

    async def _release(self, link: WhatsAppLink, reason: str) -> None:
        released = link.phone_e164
        self._whatsapp_link_repo.release_number(link, reason, Utils.datetime_now())
        if released:
            # The thread stays in the console for the agents; it just stops belonging to
            # an account, so nothing will read case data into it again (§26.4.4).
            await self._conversations.set_whatsapp_thread_owner(released, None)
        self._audit.schedule(
            AuditActionType.WHATSAPP_NUMBER_UNLINKED,
            resource_type=_AUDIT_RESOURCE,
            resource_id=link.user_id,
            actor_id=link.user_id,
            details={"phone_e164": released, "reason": reason},
        )
