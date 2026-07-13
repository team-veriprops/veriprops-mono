"""Public runtime flags the frontend reads instead of holding its own copy."""
from __future__ import annotations

from typing import List

from main.app.core.state.status import VerificationTier
from main.appodus_utils import Object


class PublicPricingTierDto(Object):
    """A tier's current resolved price, for public marketing display (no line items)."""

    tier: VerificationTier
    price_ngn_minor: int


class PublicConfigDto(Object):
    # Drives whether the signup flow shows the phone-verification step.
    phone_verification_enabled: bool
    # §B go-live gate (D18): whether the Premium Legal Opinion report section is live.
    legal_opinion_enabled: bool = False
    # Chat message body cap — the frontend input maxLength reads this rather than
    # hardcoding its own value (backend is the source of truth).
    chat_message_max_length: int = 2000
    # Live per-tier prices — the marketing pricing section reads this rather than
    # holding static copy (backend `pricing_tier_config` is the source of truth).
    pricing_tiers: List[PublicPricingTierDto] = []
