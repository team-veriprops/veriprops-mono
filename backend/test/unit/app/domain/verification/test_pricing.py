"""Verification pricing (PRD §5.2, §4.4) — pure, no DB. NGN kobo is contractual."""
from main.app.core.state.status import VerificationTier
from main.app.domain.verification.pricing import (
    TIER_PRICE_NGN_KOBO,
    indicative_charge_minor,
    price_ngn_kobo,
)
from main.appodus_utils.db.types.money import TransactionCurrency


class TestTierPrice:
    def test_each_tier_priced_ascending(self):
        b = price_ngn_kobo(VerificationTier.BASIC)
        s = price_ngn_kobo(VerificationTier.STANDARD)
        p = price_ngn_kobo(VerificationTier.PREMIUM)
        assert b < s < p
        assert all(isinstance(v, int) for v in TIER_PRICE_NGN_KOBO.values())  # integer minor units


class TestIndicativeCharge:
    def test_ngn_is_identity(self):
        amount, rate = indicative_charge_minor(12_000_000, TransactionCurrency.NGN)
        assert amount == 12_000_000
        assert rate == 1.0

    def test_foreign_currency_is_converted_and_integer(self):
        amount, rate = indicative_charge_minor(12_000_000, TransactionCurrency.USD)
        # 12,000,000 kobo * 0.00063 = 7560 (USD cents), integer minor units.
        assert amount == 7560
        assert isinstance(amount, int)
        assert rate > 0
