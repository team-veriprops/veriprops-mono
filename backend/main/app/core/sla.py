"""SLA business-day calculator + Nigerian public-holiday calendar (PRD §0.2, §1.4).

The SLA clock starts at ``PAID`` and counts **business days** — Monday–Friday,
excluding Nigerian public holidays. Targets per tier (upper bound of the §1.4
ranges):

    Basic → 5, Standard → 7, Premium → 10 business days.

Holiday set per year:

- **Fixed-date** statutory holidays (New Year, Workers' Day, Democracy Day,
  Independence Day, Christmas, Boxing Day).
- **Easter-derived** (Good Friday, Easter Monday) via the Gregorian computus.
- **Movable Islamic** holidays (Eid al-Fitr, Eid al-Adha, Mawlid) — these depend
  on moon-sighting and are announced by the Nigerian government close to the date,
  so they are kept as a **maintained dataset** (``_MOVABLE_ISLAMIC_HOLIDAYS``)
  seeded for the near term and intended to be refreshed / made admin-configurable.
"""
from __future__ import annotations

import enum
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, Optional, Tuple, Union

from main.app.core.state.status import VerificationStatus, VerificationTier

DateLike = Union[date, datetime]

# Business-day SLA target per tier (PRD §1.4 upper bound).
SLA_BUSINESS_DAYS: Dict[VerificationTier, int] = {
    VerificationTier.BASIC: 5,
    VerificationTier.STANDARD: 7,
    VerificationTier.PREMIUM: 10,
}

# (month, day) for fixed-date Nigerian public holidays.
_FIXED_HOLIDAYS: Tuple[Tuple[int, int], ...] = (
    (1, 1),    # New Year's Day
    (5, 1),    # Workers' Day
    (6, 12),   # Democracy Day
    (10, 1),   # Independence Day
    (12, 25),  # Christmas Day
    (12, 26),  # Boxing Day
)

# Maintained movable Islamic holiday dates (moon-sighting dependent; refresh yearly).
# Dates are the Nigerian public-holiday observances; approximate until gazetted.
_MOVABLE_ISLAMIC_HOLIDAYS: Dict[int, Tuple[date, ...]] = {
    2026: (date(2026, 3, 20), date(2026, 3, 21),   # Eid al-Fitr
           date(2026, 5, 27), date(2026, 5, 28),   # Eid al-Adha
           date(2026, 8, 25)),                      # Mawlid (Eid al-Mawlid)
    2027: (date(2027, 3, 10), date(2027, 3, 11),
           date(2027, 5, 17), date(2027, 5, 18),
           date(2027, 8, 15)),
    2028: (date(2028, 2, 27), date(2028, 2, 28),
           date(2028, 5, 5), date(2028, 5, 6),
           date(2028, 8, 3)),
}


def _to_date(value: DateLike) -> date:
    return value.date() if isinstance(value, datetime) else value


def _easter_sunday(year: int) -> date:
    """Gregorian computus (Anonymous algorithm) — date of Easter Sunday."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ll = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ll) // 451
    month = (h + ll - 7 * m + 114) // 31
    day = ((h + ll - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def holidays_for_year(year: int) -> frozenset[date]:
    """All Nigerian public holidays observed in ``year``."""
    days = {date(year, month, day) for month, day in _FIXED_HOLIDAYS}
    easter = _easter_sunday(year)
    days.add(easter - timedelta(days=2))  # Good Friday
    days.add(easter + timedelta(days=1))  # Easter Monday
    days.update(_MOVABLE_ISLAMIC_HOLIDAYS.get(year, ()))
    return frozenset(days)


def is_business_day(value: DateLike) -> bool:
    """True if ``value`` is Mon–Fri and not a Nigerian public holiday."""
    d = _to_date(value)
    if d.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        return False
    return d not in holidays_for_year(d.year)


def add_business_days(start: DateLike, n: int) -> date:
    """Return the date ``n`` business days after ``start`` (``start`` not counted)."""
    if n < 0:
        raise ValueError("n must be non-negative")
    d = _to_date(start)
    remaining = n
    while remaining > 0:
        d += timedelta(days=1)
        if is_business_day(d):
            remaining -= 1
    return d


def business_days_between(start: DateLike, end: DateLike) -> int:
    """Count business days in the half-open interval (``start``, ``end``].

    Returns 0 when ``end`` is on or before ``start``.
    """
    a, b = _to_date(start), _to_date(end)
    count = 0
    d = a
    while d < b:
        d += timedelta(days=1)
        if is_business_day(d):
            count += 1
    return count


def sla_due_date(paid_at: DateLike, tier: VerificationTier) -> date:
    """Business-day SLA due date for ``tier``, counted from ``paid_at`` (PRD §5.10)."""
    return add_business_days(paid_at, SLA_BUSINESS_DAYS[VerificationTier(tier)])


def business_days_remaining(reference: DateLike, due: DateLike) -> int:
    """Business-day countdown from ``reference`` to ``due`` (0 once due/overdue)."""
    return business_days_between(reference, due)


# ── SLA health (shared by admin control panel §6.1 + customer tracker §9.1) ──

class SlaHealth(str, enum.Enum):
    """SLA countdown health. Same computation feeds the admin list and the
    customer-facing tracker (which relabels it On track / Running late / Delayed)."""

    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    OVERDUE = "OVERDUE"
    NONE = "NONE"  # pre-PAID / terminal — no active SLA clock


# business-days-remaining threshold below which the clock reads "at risk".
_SLA_AT_RISK_DAYS = 1
# Statuses with an active SLA clock (post-PAID, pre-terminal). Public — dashboards reuse
# this single definition for "work underway" rollups and the overdue count.
ACTIVE_SLA_STATES = {
    VerificationStatus.PAID.value,
    VerificationStatus.IN_PROGRESS.value,
    VerificationStatus.UNDER_REVIEW.value,
}
_ACTIVE_SLA_STATES = ACTIVE_SLA_STATES


def compute_sla_health(
    status: str, due: Optional[DateLike], today: date
) -> Tuple[SlaHealth, Optional[int]]:
    """SLA health + business-days-remaining for a verification.

    ``today`` is passed in (never read from the clock here) so callers control the
    reference date and the function stays deterministically testable. Returns a
    negative remaining count once overdue (business days past due).
    """
    if status not in _ACTIVE_SLA_STATES or not due:
        return SlaHealth.NONE, None
    due_d = _to_date(due)
    if due_d < today:
        return SlaHealth.OVERDUE, -business_days_between(due_d, today)
    remaining = business_days_remaining(today, due_d)
    if remaining <= _SLA_AT_RISK_DAYS:
        return SlaHealth.AT_RISK, remaining
    return SlaHealth.ON_TRACK, remaining
