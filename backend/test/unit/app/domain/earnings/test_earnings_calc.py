"""Pure earnings-balance derivation (§15.1/§15.2, D31) — reconciles to the kobo."""
from datetime import timedelta
from types import SimpleNamespace

from main.app.domain.commission.models import CommissionStatus
from main.app.domain.earnings.calc import derive_balance
from main.appodus_utils import Utils

NOW = Utils.datetime_now()
PAST = NOW - timedelta(days=1)
FUTURE = NOW + timedelta(days=1)


def _c(status=CommissionStatus.CLEARING, amount=100_000, reserve=10_000,
       clearing_until=FUTURE, reserve_released_at=None):
    return SimpleNamespace(
        status=status.value, amount_minor=amount, reserve_amount_minor=reserve,
        clearing_until=clearing_until, reserve_released_at=reserve_released_at,
    )


class TestDeriveBalance:
    def test_fresh_commission_is_clearing_plus_reserve_nothing_available(self):
        bal = derive_balance([_c()], NOW, total_paid_minor=0, pending_locked_minor=0)
        assert bal.available_minor == 0
        assert bal.clearing_minor == 90_000       # bulk = amount - reserve
        assert bal.in_reserve_minor == 10_000
        assert bal.lifetime_earned_minor == 100_000

    def test_bulk_clears_reserve_still_held(self):
        bal = derive_balance([_c(clearing_until=PAST)], NOW, 0, 0)
        assert bal.available_minor == 90_000
        assert bal.clearing_minor == 0
        assert bal.in_reserve_minor == 10_000

    def test_reserve_released_is_fully_available(self):
        bal = derive_balance(
            [_c(clearing_until=PAST, reserve_released_at=PAST)], NOW, 0, 0
        )
        assert bal.available_minor == 100_000
        assert bal.in_reserve_minor == 0

    def test_frozen_is_on_hold_only(self):
        bal = derive_balance([_c(status=CommissionStatus.FROZEN, clearing_until=PAST)], NOW, 0, 0)
        assert bal.on_hold_minor == 100_000
        assert bal.available_minor == 0
        assert bal.clearing_minor == 0
        assert bal.in_reserve_minor == 0

    def test_reversed_excluded_everywhere(self):
        bal = derive_balance([_c(status=CommissionStatus.REVERSED, clearing_until=PAST)], NOW, 0, 0)
        assert bal.lifetime_earned_minor == 0
        assert bal.available_minor == 0
        assert bal.on_hold_minor == 0

    def test_available_nets_paid_and_pending(self):
        bal = derive_balance(
            [_c(clearing_until=PAST, reserve_released_at=PAST)], NOW,
            total_paid_minor=30_000, pending_locked_minor=20_000,
        )
        # gross available 100k − 30k paid − 20k locked = 50k
        assert bal.available_minor == 50_000
        assert bal.total_paid_minor == 30_000

    def test_available_clamped_at_zero(self):
        bal = derive_balance(
            [_c(clearing_until=PAST, reserve_released_at=PAST)], NOW,
            total_paid_minor=200_000, pending_locked_minor=0,
        )
        assert bal.available_minor == 0  # late reversal after payout — bounded tail risk

    def test_zero_reserve_commission(self):
        bal = derive_balance([_c(reserve=0, clearing_until=PAST)], NOW, 0, 0)
        assert bal.available_minor == 100_000
        assert bal.in_reserve_minor == 0
