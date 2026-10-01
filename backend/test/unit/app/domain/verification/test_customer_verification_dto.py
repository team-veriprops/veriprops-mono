"""The customer's view of their own case carries what the portal shows about it — including
whether the public VID lookup is on, so the share controls can say so and turn it off (§13.1)."""
from types import SimpleNamespace

import pytest

from main.app.domain.verification.controller import _to_dto


def _verification(public_lookup_enabled):
    return SimpleNamespace(
        id="v1", vid="VP-2026-ABC123", status="COMPLETED", tier="STANDARD", property_id=None,
        price_locked_minor=12_000_000, currency="NGN", charge_currency=None, charge_amount_minor=None,
        fx_rate_at_quote=None, price_lock_expires_at=None, first_time_discount_minor=0,
        referral_credit_applied_minor=0, paid_at=None, sla_due_date=None, draft_step=0,
        public_lookup_enabled=public_lookup_enabled,
    )


@pytest.mark.parametrize("enabled", [True, False])
def test_the_public_lookup_flag_reaches_the_customer(enabled):
    assert _to_dto(_verification(enabled)).public_lookup_enabled is enabled
