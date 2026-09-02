"""Turning a chat intake into a real draft (PRD §5.1, §7.5, D69/D71).

The seam between the conversation and the website. The bot collected four answers into its
session and sent a single-use link; this is what happens when the customer opens it —
after they have signed in, because identity is exactly what the chat could not establish.

The whole point is that it hands into the **existing** submission wizard rather than
building a chat-specific checkout. Seeding a draft with the wizard's own payload shape
means the §5.1 conditional fields, the tier step, the §5.3 consent control and the payment
step are all the ones already built and tested — and resumption works in both directions
because there is only ever one draft row (D69).

Two rules live here:

* **The number on the token decides whose answers get loaded**, never the request. A
  signed-in customer opening a forwarded link would otherwise seed their draft from a
  stranger's conversation.
* **The answers are cleared once they are seeded.** They are a conversation's working
  state, not a record; leaving them would let a second redemption re-seed a draft the
  customer has since edited on the web.
"""
from __future__ import annotations

from kink import inject

from main.app.domain.channel.whatsapp.bot.session.service import WhatsAppBotSessionService
from main.app.domain.verification.service import VerificationService
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ResourceNotFoundException

# The wizard step the seeded draft resumes at. Zero, deliberately: the customer lands on
# the property step with their answers filled in, so the first thing they see is what the
# bot understood — and the §5.1 fields the chat skipped (D70) are right there.
_SEEDED_WIZARD_STEP = 0


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class WhatsAppIntakeHandoffService:
    def __init__(
        self,
        whatsapp_bot_session_service: WhatsAppBotSessionService,
        verification_service: VerificationService,
    ):
        self._whatsapp_bot_session_service = whatsapp_bot_session_service
        self._verification_service = verification_service

    async def seed_draft(self, phone_e164: str, customer_id: str) -> str:
        """Create (or resume) this customer's draft, filled with what the bot collected.

        Returns the verification id the wizard should open. `create_draft` already
        auto-resumes a customer's unpaid draft, so a customer who had one open on the web
        gets *that* row seeded rather than a second one — which is what keeps "one
        verification in flight" true across both surfaces.
        """
        collected = await self._collected_for(phone_e164)
        verification = await self._verification_service.create_draft(customer_id)
        # By object, not by id: the draft may have been created moments ago in this same
        # uncommitted transaction, where a re-fetch can come back empty and the seeding
        # would silently do nothing.
        await self._verification_service.seed_draft_payload(
            verification, _SEEDED_WIZARD_STEP, collected
        )
        await self._clear_collected(phone_e164)
        return Utils.uuid_to_hex(verification.id)

    async def _collected_for(self, phone_e164: str) -> dict:
        """The answers the bot gathered for this number.

        A missing or emptied session is a link opened twice, or one opened long after the
        conversation was reset. Refusing is right: seeding a blank draft would put a
        customer who answered four questions in front of an empty form with no explanation.
        """
        session = await self._whatsapp_bot_session_service.get(phone_e164)
        collected = (session.context or {}).get("intake") if session else None
        if not collected:
            raise ResourceNotFoundException(resource="Intake")
        return collected

    async def _clear_collected(self, phone_e164: str) -> None:
        """Forget the conversation's working state now that it is a real draft."""
        session = await self._whatsapp_bot_session_service.get(phone_e164)
        if session is not None:
            await self._whatsapp_bot_session_service.clear_flow(session)
