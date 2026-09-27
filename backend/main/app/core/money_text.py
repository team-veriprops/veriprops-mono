"""Money as a customer or admin reads it."""
from __future__ import annotations


def naira(minor: int) -> str:
    """Kobo → a readable naira amount. Whole naira: we do not price in kobo.

    Shared by every surface that states a price or a commission in words (the assistant's
    tier quotes, the commission-margin refusal), so one amount never renders two ways (D54).
    """
    return f"₦{minor // 100:,}"
