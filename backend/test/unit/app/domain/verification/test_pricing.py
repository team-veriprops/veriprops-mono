"""Verification pricing (PRD §5.2, §4.4) — pure, no DB. NGN kobo is contractual."""
from main.app.core.state.status import VerificationTier
from main.app.domain.verification.pricing import (
    TIER_PRICE_NGN_KOBO,
    apply_discounts,
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


class TestApplyDiscounts:
    """First-time + referral discount resolution (§17.1), all in NGN kobo."""

    BASE = 12_000_000  # ₦120k

    def test_first_time_only(self):
        d = apply_discounts(self.BASE, first_time=True, first_time_pct=10,
                            referral_credit_kobo=0, max_discount_pct=25)
        assert d.first_time_minor == 1_200_000
        assert d.referral_applied_minor == 0
        assert d.net_minor == self.BASE - 1_200_000
        assert d.cap_hit is False

    def test_no_discount_for_returning_no_credit(self):
        d = apply_discounts(self.BASE, first_time=False, first_time_pct=10,
                            referral_credit_kobo=0, max_discount_pct=25)
        assert d.total_discount_minor == 0
        assert d.net_minor == self.BASE

    def test_referral_stacks_under_cap(self):
        d = apply_discounts(self.BASE, first_time=True, first_time_pct=10,
                            referral_credit_kobo=1_000_000, max_discount_pct=25)
        # 1.2m first-time + 1.0m referral = 2.2m, under the 3.0m (25%) cap.
        assert d.referral_applied_minor == 1_000_000
        assert d.total_discount_minor == 2_200_000
        assert d.cap_hit is False

    def test_combined_capped_at_max_percent(self):
        d = apply_discounts(self.BASE, first_time=True, first_time_pct=10,
                            referral_credit_kobo=10_000_000, max_discount_pct=25)
        cap = int(self.BASE * 0.25)  # 3,000,000
        assert d.total_discount_minor == cap
        assert d.referral_applied_minor == cap - d.first_time_minor  # referral trimmed first
        assert d.cap_hit is True

    def test_reconciles_to_the_kobo(self):
        d = apply_discounts(self.BASE, first_time=True, first_time_pct=10,
                            referral_credit_kobo=500_000, max_discount_pct=25)
        assert d.net_minor + d.total_discount_minor == self.BASE
