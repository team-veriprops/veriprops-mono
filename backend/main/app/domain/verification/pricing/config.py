"""Static pricing matrix — code-resident until Phase 18 builds the admin UI.

Amounts are stored in *minor units* (kobo for NGN). PRD §1.7 + Open Q #2/#3.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from main.app.domain.verification.models import (
    PricingLineItemDto,
    VerificationTier,
)


# Tier → (base label, base amount minor, list of (label, amount_minor, description))
TIER_MATRIX: Dict[VerificationTier, Tuple[str, int, List[Tuple[str, int, str]]]] = {
    VerificationTier.BASIC: (
        "Basic verification (registry-only)",
        15000_00,  # ₦15,000.00 admin/service fee
        [
            ("Registry search", 130000_00, "Title search at the registry of record"),
            ("Document collection", 5000_00, "Acquisition of certified true copies"),
        ],
    ),
    VerificationTier.STANDARD: (
        "Standard verification (registry + field + survey)",
        25000_00,
        [
            ("Registry search", 130000_00, "Title search at the registry of record"),
            ("Document collection", 5000_00, "Acquisition of certified true copies"),
            ("Field inspection", 90000_00, "On-site inspection by Field Agent"),
            ("Survey assessment", 100000_00, "Boundary + survey-plan check"),
        ],
    ),
    VerificationTier.PREMIUM: (
        "Premium verification (full + legal opinion)",
        50000_00,
        [
            ("Registry search", 130000_00, "Title search at the registry of record"),
            ("Document collection", 5000_00, "Acquisition of certified true copies"),
            ("Field inspection", 90000_00, "On-site inspection by Field Agent"),
            ("Survey assessment", 120000_00, "Boundary + survey-plan check"),
            ("Legal opinion", 355000_00, "Structured legal opinion by registered lawyer"),
        ],
    ),
}


# Headline tier prices (NGN minor units) — used by the public landing page.
# Sum of all line items is what the customer actually pays.
def total_for_tier(tier: VerificationTier) -> int:
    base_label, base_amount, line_items = TIER_MATRIX[tier]
    return base_amount + sum(amount for _, amount, _ in line_items)


def line_items_for_tier(tier: VerificationTier) -> List[PricingLineItemDto]:
    base_label, base_amount, line_items = TIER_MATRIX[tier]
    items: List[PricingLineItemDto] = [
        PricingLineItemDto(label="Service fee", amount_minor=base_amount, description=base_label),
    ]
    for label, amount, desc in line_items:
        items.append(PricingLineItemDto(label=label, amount_minor=amount, description=desc))
    return items


SUPPORTED_CURRENCIES = ("NGN", "USD", "GBP", "EUR")


# Stub FX table — anchored to NGN. Real provider lands in Phase 18.
STUB_FX_RATES: Dict[str, float] = {
    "NGN": 1.0,
    "USD": 1.0 / 1500.0,
    "GBP": 1.0 / 1900.0,
    "EUR": 1.0 / 1620.0,
}
