"""Turning an assistant intake into a real draft (PRD §5.1, D69, D93).

The seam between a conversation and the website. The assistant collected four answers in the
wizard's own payload shape; this writes them into the customer's draft so the **existing**
submission wizard picks up from there — its §5.1 conditional fields, tier step, §5.3 consent
control and payment step are the ones already built and tested, and resumption works in both
directions because there is only ever one draft row (D69).

Both surfaces arrive here: WhatsApp when the customer redeems their intake link and signs in
(`channel/whatsapp/bot/intake_handoff.py`), the portal at the end of the intake itself, where
the customer is already signed in.
"""
from __future__ import annotations

from kink import inject

from main.app.domain.verification.service import VerificationService
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional

# The wizard step the seeded draft resumes at. Zero, deliberately: the customer lands on
# the property step with their answers filled in, so the first thing they see is what the
# assistant understood — and the §5.1 fields the chat skipped (D70) are right there.
SEEDED_WIZARD_STEP = 0


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class IntakeDraftSeeder:
    def __init__(self, verification_service: VerificationService):
        self._verification_service = verification_service

    async def seed(self, customer_id: str, collected: dict) -> str:
        """Create (or resume) this customer's draft, filled with *collected*.

        Returns the verification id the wizard opens. `create_draft` already auto-resumes a
        customer's unpaid draft, so a customer who had one open gets *that* row seeded rather
        than a second one — which keeps "one verification in flight" true across surfaces.
        """
        verification = await self._verification_service.create_draft(customer_id)
        # By object, not by id: the draft may have been created moments ago in this same
        # uncommitted transaction, where a re-fetch can come back empty and the seeding
        # would silently do nothing.
        await self._verification_service.seed_draft_payload(
            verification, SEEDED_WIZARD_STEP, collected
        )
        return Utils.uuid_to_hex(verification.id)
