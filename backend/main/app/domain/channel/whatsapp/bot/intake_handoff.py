"""Turning a chat intake into a real draft (PRD §5.1, §26.5, D69/D71).

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

from main.app.domain.communication.assistant.intake_seeder import IntakeDraftSeeder
from main.app.domain.communication.assistant.session.service import AssistantSessionService
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import ResourceNotFoundException


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class WhatsAppIntakeHandoffService:
    def __init__(
        self,
        assistant_session_service: AssistantSessionService,
        intake_draft_seeder: IntakeDraftSeeder,
    ):
        self._assistant_session_service = assistant_session_service
        self._intake_draft_seeder = intake_draft_seeder

    async def seed_draft(self, phone_e164: str, customer_id: str) -> str:
        """Seed this customer's draft with what the assistant collected on this number.

        Returns the verification id the wizard should open.
        """
        collected = await self._collected_for(phone_e164)
        verification_id = await self._intake_draft_seeder.seed(customer_id, collected)
        await self._clear_collected(phone_e164)
        return verification_id

    async def _collected_for(self, phone_e164: str) -> dict:
        """The answers the assistant gathered for this number.

        A missing or emptied session is a link opened twice, or one opened long after the
        conversation was reset. Refusing is right: seeding a blank draft would put a
        customer who answered four questions in front of an empty form with no explanation.
        """
        session = await self._assistant_session_service.get_by_phone(phone_e164)
        collected = (session.context or {}).get("intake") if session else None
        if not collected:
            raise ResourceNotFoundException(resource="Intake")
        return collected

    async def _clear_collected(self, phone_e164: str) -> None:
        """Forget the conversation's working state now that it is a real draft."""
        session = await self._assistant_session_service.get_by_phone(phone_e164)
        if session is not None:
            await self._assistant_session_service.clear_flow(session)
