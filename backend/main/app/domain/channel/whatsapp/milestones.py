"""§26.6.2 milestone delivery over WhatsApp (D65; WA-16/WA-34/WA-35).

The notification router decides *that* a milestone should go out; this decides *whether it
may* and *where to*. Three gates, all of which must pass, and none of which lives at a send
site — that separation is the WA-16/WA-27 property: "the customer never opted in" is one
place to audit rather than a rule every future milestone has to remember.

1. **Outbound messaging is enabled.** Same posture as the rest of the pipeline: a local run
   without it stays fully inspectable and sends nothing.
2. **The customer granted the §26.4.6 utility consent.** Read from the D63 ledger.
3. **The account has an ACTIVE linked number.** Resolved through
   `WhatsAppLinkService.resolve_phone_for_user`, never `users.phone` — a profile number
   nobody proved control of over WhatsApp would be the §26.4.3 leak running outwards.

Everything is best-effort and never raises. A milestone is a courtesy on top of a state
change that has already happened; a failed template send must not roll back the transaction
that moved the case, and the customer still has the portal, the email, and the status flow.
"""
from __future__ import annotations

from logging import Logger
from typing import Any, Dict, Optional

from kink import di, inject

from main.app.config.settings import settings
from main.app.core.state.status import VerificationStatus
from main.app.domain.channel.whatsapp.consent.service import WhatsAppConsentService
from main.app.domain.channel.whatsapp.link.service import WhatsAppLinkService
from main.app.domain.verification.models import Verification
from main.app.domain.verification.repo import VerificationRepo
from main.app.domain.verification.tracking.labels import customer_status_label
from main.appodus_utils.db.types.phone import PhoneNumber
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.integrations.messaging.models import (
    MessageContext,
    MessageRequestRecipient,
)
from main.appodus_utils.integrations.messaging.providers.whatsapp.phone import to_wa_recipient
from main.appodus_utils.integrations.messaging.templating.models import AvailableTemplate

logger: Logger = di["logger"]


def status_label_for(verification: Verification) -> str:
    """The one customer-facing status vocabulary (§26.4.5 delegate copy).

    `verification/tracking/labels.py` is what the dashboard renders, so a delegate and the
    buyer read the same words — the §26.3.2 projection's stage names are the channel's
    internal vocabulary, not a second thing to show a person.

    Module level rather than a method because it is pure: a synchronous public method on a
    `decorate_all_methods` class silently returns an un-awaited coroutine, which is the
    exact bug `test_decorated_service_contract.py` exists to catch.
    """
    return customer_status_label(VerificationStatus(verification.status))


@inject
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class WhatsAppMilestoneSender:
    def __init__(
        self,
        whatsapp_consent_service: WhatsAppConsentService,
        whatsapp_link_service: WhatsAppLinkService,
        verification_repo: VerificationRepo,
    ):
        self._whatsapp_consent_service = whatsapp_consent_service
        self._whatsapp_link_service = whatsapp_link_service
        self._verification_repo = verification_repo

    async def send_customer_milestone(
        self, user_id: str, verification_id: Optional[str], template: AvailableTemplate
    ) -> None:
        """Deliver one §26.7 milestone to the customer, if all three gates pass."""
        if not settings.ENABLE_OUT_MESSAGING:
            logger.warning(
                f"WhatsApp milestone {template.value} not dispatched "
                "(ENABLE_OUT_MESSAGING=False)"
            )
            return
        if not await self._whatsapp_consent_service.utility_granted(user_id):
            # Not a failure — this is the §26.4.6 opt-in doing its job.
            return
        phone_e164 = await self._whatsapp_link_service.resolve_phone_for_user(user_id)
        if not phone_e164:
            # Consented but never linked a number. There is nowhere to send, and inventing
            # one from the profile is exactly what D65 forbids.
            return

        verification = await self._get_verification(verification_id)
        if verification is None:
            return
        await self._send(
            phone_e164,
            template,
            self._context_for(template, verification),
        )

    async def send_delegate_milestone(
        self, phone_e164: str, vid: str, status_label: str, *, delegate_name: str
    ) -> None:
        """Deliver the §26.4.5 delegate's status-only milestone.

        No consent lookup: a delegate has no account and therefore no consent row. Their
        authorization *is* the consent — they OTP-verified the number specifically to
        receive these — and STOP ends the delegation itself (D77), which is the only
        opt-out lever a non-user has.
        """
        if not settings.ENABLE_OUT_MESSAGING:
            logger.warning(
                "delegate_status not dispatched (ENABLE_OUT_MESSAGING=False): "
                f"recipient={to_wa_recipient(phone_e164)}"
            )
            return
        await self._send_delegate(
            phone_e164,
            {
                MessageContext.SHARE_VID: vid,
                MessageContext.VERIFICATION_NEW_STATUS: status_label,
                MessageContext.FIRST_NAME: delegate_name,
            },
        )

    # ── Context ───────────────────────────────────────────────────

    @staticmethod
    def _context_for(
        template: AvailableTemplate, verification: Verification
    ) -> Dict[MessageContext, Any]:
        """The template's parameters, in the terms a customer reads.

        `report_ready` carries the **portal deep link** rather than a §26.5 handoff token
        (D75). A handoff token lives fifteen minutes; a milestone read an hour later would
        land the customer on the expiry page from a message they never clicked. Decision B
        already puts the report behind a real login, and the bot still mints a fresh
        `report` link on request — which is §26.4.2's recovery path, used when it is needed
        rather than on every send.
        """
        context: Dict[MessageContext, Any] = {MessageContext.SHARE_VID: verification.vid}
        if template is AvailableTemplate.WHATSAPP_REPORT_READY:
            context[MessageContext.LINK] = (
                f"{settings.PUBLIC_APP_BASE_URL.rstrip('/')}"
                f"/portal/verifications/{verification.vid}"
            )
        return context

    async def _get_verification(self, verification_id: Optional[str]) -> Optional[Verification]:
        if not verification_id:
            return None
        return await self._verification_repo.get_model(verification_id)

    # ── Transport ─────────────────────────────────────────────────

    async def _send(
        self, phone_e164: str, template: AvailableTemplate, context: Dict[MessageContext, Any]
    ) -> None:
        from main.app.domain.message.verification_messages import VerificationMessages

        try:
            await di[VerificationMessages].send_whatsapp_milestone(
                recipient=MessageRequestRecipient(phone=PhoneNumber.from_e164(phone_e164)),
                template=template,
                context=context,
            )
        except Exception as exc:  # noqa: BLE001 — see the module docstring
            logger.error(
                f"WhatsApp milestone {template.value} failed for "
                f"{to_wa_recipient(phone_e164)}: {exc}"
            )

    async def _send_delegate(
        self, phone_e164: str, context: Dict[MessageContext, Any]
    ) -> None:
        from main.app.domain.message.verification_messages import VerificationMessages

        try:
            await di[VerificationMessages].send_whatsapp_delegate_status(
                recipient=MessageRequestRecipient(phone=PhoneNumber.from_e164(phone_e164)),
                context=context,
            )
        except Exception as exc:  # noqa: BLE001 — see the module docstring
            logger.error(
                f"delegate_status failed for {to_wa_recipient(phone_e164)}: {exc}"
            )
