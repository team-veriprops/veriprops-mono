"""Verification pricing (PRD §5.2, §4.4).

NGN is the contractual amount, stored in integer minor units (kobo). Foreign
figures are **indicative only**, derived from the NGN amount at the quote-time FX
rate. Prices here are provisional per-tier defaults until the admin-configured
pricing API lands (Phase 18); they are intentionally centralised so that later
swap is a single call-site change.
"""
from __future__ import annotations

from decimal import Decimal

from main.app.core.state.status import VerificationTier
from main.appodus_utils.db.types.money import TransactionCurrency

# Provisional contractual price per tier, in NGN kobo (₦50k / ₦120k / ₦300k).
TIER_PRICE_NGN_KOBO: dict[VerificationTier, int] = {
    VerificationTier.BASIC: 5_000_000,
    VerificationTier.STANDARD: 12_000_000,
    VerificationTier.PREMIUM: 30_000_000,
}


def price_ngn_kobo(tier: VerificationTier) -> int:
    """Contractual NGN price for a tier, in kobo."""
    return TIER_PRICE_NGN_KOBO[tier]


def indicative_charge_minor(ngn_kobo: int, currency: TransactionCurrency) -> tuple[int, float]:
    """Convert an NGN-kobo amount to an *indicative* minor-unit charge in ``currency``.

    Returns ``(charge_amount_minor, fx_rate)``. For NGN this is the identity. The
    foreign figure is indicative only (§4.4) — the gateway converts at charge time.
    """
    rate = currency.fx_rate  # units of `currency` per 1 NGN
    if currency == TransactionCurrency.NGN:
        return ngn_kobo, float(rate)
    # ngn_kobo is kobo (NGN * 100); foreign minor units are also *100.
    charge_minor = int((Decimal(ngn_kobo) * Decimal(rate)).to_integral_value())
    return charge_minor, float(rate)
