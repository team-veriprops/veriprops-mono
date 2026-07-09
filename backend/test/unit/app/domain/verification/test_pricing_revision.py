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
        # STANDARD = ₦120k = 12_000_000 kobo; 30% = 3_600_000. Helper takes the resolved base.
        base = TIER_PRICE_NGN_KOBO[VerificationTier.STANDARD]
        assert recheck_price_kobo(base, 30) == 3_600_000

    def test_recheck_scales_with_tier(self):
        basic = recheck_price_kobo(TIER_PRICE_NGN_KOBO[VerificationTier.BASIC], 30)
        premium = recheck_price_kobo(TIER_PRICE_NGN_KOBO[VerificationTier.PREMIUM], 30)
        assert premium > basic


class TestUpgradeDelta:
    def test_delta_is_price_difference(self):
        std = TIER_PRICE_NGN_KOBO[VerificationTier.STANDARD]
        prem = TIER_PRICE_NGN_KOBO[VerificationTier.PREMIUM]
        assert upgrade_delta_kobo(std, prem) == prem - std

    def test_is_upgrade_ordering(self):
        assert is_upgrade(VerificationTier.BASIC, VerificationTier.STANDARD)
        assert is_upgrade(VerificationTier.STANDARD, VerificationTier.PREMIUM)
        assert not is_upgrade(VerificationTier.PREMIUM, VerificationTier.STANDARD)
        assert not is_upgrade(VerificationTier.STANDARD, VerificationTier.STANDARD)
