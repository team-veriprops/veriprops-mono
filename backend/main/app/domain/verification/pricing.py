"""Verification pricing (PRD §5.2, §4.4).

NGN is the contractual amount, stored in integer minor units (kobo). Foreign
figures are **indicative only**, derived from the NGN amount at the quote-time FX
rate. Prices here are provisional per-tier defaults until the admin-configured
pricing API lands (Phase 18); they are intentionally centralised so that later
swap is a single call-site change.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from main.app.core.state.status import VerificationTier
from main.appodus_utils.db.types.money import TransactionCurrency

# Provisional contractual price per tier, in NGN kobo (₦50k / ₦120k / ₦300k).
TIER_PRICE_NGN_KOBO: dict[VerificationTier, int] = {
    VerificationTier.BASIC: 5_000_000,
    VerificationTier.STANDARD: 12_000_000,
    VerificationTier.PREMIUM: 30_000_000,
}

# Tier ordering for upgrade eligibility (§14.2) — a higher rank is a richer tier.
TIER_RANK: dict[VerificationTier, int] = {
    VerificationTier.BASIC: 1,
    VerificationTier.STANDARD: 2,
    VerificationTier.PREMIUM: 3,
}


def is_upgrade(current: VerificationTier, target: VerificationTier) -> bool:
    """True when ``target`` is a strictly higher tier than ``current`` (§14.2)."""
    return TIER_RANK[target] > TIER_RANK[current]


def price_ngn_kobo(tier: VerificationTier) -> int:
    """Contractual NGN price for a tier, in kobo."""
    return TIER_PRICE_NGN_KOBO[tier]


def recheck_price_kobo(tier: VerificationTier, pct: int) -> int:
    """Re-check fee (§14.1, D26) — a percentage of the original tier price, in NGN kobo.
    ``pct`` comes from the ``recheck_price_pct`` system-config knob."""
    return int(price_ngn_kobo(tier) * (pct / 100))


def upgrade_delta_kobo(current: VerificationTier, target: VerificationTier) -> int:
    """Tier-upgrade charge (§14.2) — the delta between the target and current tier prices,
    in NGN kobo. Non-positive when the target is not an upgrade (guarded by the caller)."""
    return price_ngn_kobo(target) - price_ngn_kobo(current)


@dataclass(frozen=True)
class Discount:
    """A resolved discount breakdown for a quote, all amounts in NGN kobo (§17.1).

    The combined first-time + referral discount is capped at ``max_discount_percent``
    of the base price; when the cap binds, the referral portion is trimmed first (the
    first-time discount is a fixed percentage the product always honours)."""

    base_minor: int
    first_time_minor: int
    referral_applied_minor: int
    total_discount_minor: int
    net_minor: int
    cap_hit: bool


def apply_discounts(
    base_kobo: int,
    *,
    first_time: bool,
    first_time_pct: int,
    referral_credit_kobo: int,
    max_discount_pct: int,
) -> Discount:
    """Resolve the discount breakdown for a base price (§17.1, §5.2).

    - ``first_time`` applies ``first_time_pct`` of the base (auto, never a code).
    - ``referral_credit_kobo`` is the customer's spendable referral credit; it is
      applied on top, but the *combined* discount never exceeds ``max_discount_pct``
      of the base. Reconciles exactly to the kobo (integer minor units, §4.4).
    """
    first_time_minor = int(base_kobo * first_time_pct / 100) if first_time else 0
    cap_minor = int(base_kobo * max_discount_pct / 100)

    # Referral credit fills the remaining head-room under the cap, bounded by the
    # customer's available credit and by never driving the price below zero.
    remaining_cap = max(0, cap_minor - first_time_minor)
    max_referral = min(remaining_cap, max(0, base_kobo - first_time_minor))
    referral_applied_minor = min(referral_credit_kobo, max_referral)

    total_discount_minor = first_time_minor + referral_applied_minor
    cap_hit = total_discount_minor >= cap_minor and (
        first_time_minor + referral_credit_kobo > cap_minor
    )
    net_minor = base_kobo - total_discount_minor
    return Discount(
        base_minor=base_kobo,
        first_time_minor=first_time_minor,
        referral_applied_minor=referral_applied_minor,
        total_discount_minor=total_discount_minor,
        net_minor=net_minor,
        cap_hit=cap_hit,
    )


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
