"""Re-check % pricing + tier-upgrade delta pricing + tier ordering (§14, D26)."""
from main.app.core.state.status import VerificationTier
from main.app.domain.verification.pricing import (
    TIER_PRICE_NGN_KOBO,
    is_upgrade,
    recheck_price_kobo,
    upgrade_delta_kobo,
)


class TestRecheckPricing:
    def test_recheck_is_pct_of_original(self):
        # STANDARD = ₦120k = 12_000_000 kobo; 30% = 3_600_000.
        assert recheck_price_kobo(VerificationTier.STANDARD, 30) == 3_600_000

    def test_recheck_scales_with_tier(self):
        basic = recheck_price_kobo(VerificationTier.BASIC, 30)
        premium = recheck_price_kobo(VerificationTier.PREMIUM, 30)
        assert premium > basic


class TestUpgradeDelta:
    def test_delta_is_price_difference(self):
        expected = TIER_PRICE_NGN_KOBO[VerificationTier.PREMIUM] - TIER_PRICE_NGN_KOBO[VerificationTier.STANDARD]
        assert upgrade_delta_kobo(VerificationTier.STANDARD, VerificationTier.PREMIUM) == expected

    def test_is_upgrade_ordering(self):
        assert is_upgrade(VerificationTier.BASIC, VerificationTier.STANDARD)
        assert is_upgrade(VerificationTier.STANDARD, VerificationTier.PREMIUM)
        assert not is_upgrade(VerificationTier.PREMIUM, VerificationTier.STANDARD)
        assert not is_upgrade(VerificationTier.STANDARD, VerificationTier.STANDARD)
