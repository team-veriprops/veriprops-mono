"""Wire DTOs for the handoff landings (PRD §26.4.2).

Deliberately thin. A landing page must acknowledge where the customer left off — silent
context loss is a spec violation — but it is still an unauthenticated surface reached by
a forwardable link, so it carries the case reference and what is owed, never the address,
the customer's name, or anything else a leaked link should not disclose.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from main.app.core.state.status import VerificationStatus, VerificationTier
from main.app.domain.channel.whatsapp.handoff.models import HandoffIntent
from main.appodus_utils import Object
from main.appodus_utils.db.types.money import TransactionCurrency


class HandoffContextDto(Object):
    """What the landing page shows: "picking up where you left off" (§26.4.2)."""

    intent: HandoffIntent
    case_id: str
    # The opaque short code (VP-1042) — never the address or customer name, which would
    # leak through a WhatsApp message preview (§26.4.3).
    vid: str
    tier: VerificationTier
    status: VerificationStatus
    amount_due_minor: Optional[int] = None
    currency: Optional[TransactionCurrency] = None
    expires_at: datetime


class HandoffPaymentDto(Object):
    """The checkout a redeemed `pay` link opens."""

    tx_ref: str
    checkout_url: Optional[str] = None
    amount_minor: int
    currency: TransactionCurrency
