"""Referral domain — Phase 17 (S51).

Customer referral codes, redemptions, first-time discounts, and referrer credits.
"""
from main.app.domain.referral.models import (
    ReferralCode,
    ReferralRedemption,
)
from main.app.domain.referral.controller import referral_router

__all__ = ["ReferralCode", "ReferralRedemption", "referral_router"]
