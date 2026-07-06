"""Pure earnings-balance derivation (PRD §15.1/§15.2, D31).

The agent balance is **derived by date** from the commission ledger + payouts — never a
stored running total — so it always reconciles to the kobo (§15.3). Each commission clears
in two stages: the bulk after ``clearing_until``, the reserve once ``reserve_released_at``
is stamped (past the chargeback window). This module holds only the arithmetic so it is
trivially unit-testable; the service supplies the rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from main.app.domain.commission.models import Commission, CommissionStatus


@dataclass(frozen=True)
class EarningsBalance:
    """The six §15.1 line items, all in integer minor units."""

    available_minor: int      # withdrawable now (hero figure)
    clearing_minor: int       # earned, bulk not yet past its clearance date
    in_reserve_minor: int     # reserve held until the chargeback window closes
    on_hold_minor: int        # frozen by a dispute / chargeback
    lifetime_earned_minor: int  # everything ever earned that wasn't clawed back
    total_paid_minor: int     # already withdrawn (paid out)


def _bulk(c: Commission) -> int:
    return max(c.amount_minor - (c.reserve_amount_minor or 0), 0)


def derive_balance(
    commissions: Iterable[Commission],
    now: datetime,
    total_paid_minor: int,
    pending_locked_minor: int,
) -> EarningsBalance:
    """Fold the commission rows into the balance line items.

    ``total_paid_minor`` is the sum of disbursed payouts; ``pending_locked_minor`` is the sum
    of in-flight payout requests still reserving funds. Both reduce the withdrawable figure so
    money is never double-spent. ``available`` is clamped at 0 (a late reversal after payout is
    the accepted bounded tail risk, §15.2)."""
    gross_available = clearing = in_reserve = on_hold = lifetime = 0
    for c in commissions:
        if c.status == CommissionStatus.REVERSED.value:
            continue  # clawed back — earns nothing
        reserve = c.reserve_amount_minor or 0
        lifetime += c.amount_minor
        if c.status == CommissionStatus.FROZEN.value:
            on_hold += c.amount_minor
            continue
        bulk = _bulk(c)
        # Bulk portion: available once its clearance date passes, else still clearing.
        if c.clearing_until is not None and now >= c.clearing_until:
            gross_available += bulk
        else:
            clearing += bulk
        # Reserve portion: available once explicitly released, else held in reserve.
        if c.reserve_released_at is not None:
            gross_available += reserve
        else:
            in_reserve += reserve

    available = max(gross_available - total_paid_minor - pending_locked_minor, 0)
    return EarningsBalance(
        available_minor=available,
        clearing_minor=clearing,
        in_reserve_minor=in_reserve,
        on_hold_minor=on_hold,
        lifetime_earned_minor=lifetime,
        total_paid_minor=total_paid_minor,
    )
