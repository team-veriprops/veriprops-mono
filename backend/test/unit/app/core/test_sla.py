"""Unit tests for the SLA business-day calculator + NG holiday calendar (PRD §0.2, §1.4)."""
from datetime import date, datetime, timezone

import pytest

from main.app.core.sla import (
    SLA_BUSINESS_DAYS,
    add_business_days,
    business_days_between,
    business_days_remaining,
    holidays_for_year,
    is_business_day,
    sla_due_date,
)
from main.app.core.state.status import VerificationTier


class TestHolidayCalendar:
    def test_fixed_holidays_present(self):
        h = holidays_for_year(2026)
        for d in (date(2026, 1, 1), date(2026, 5, 1), date(2026, 6, 12),
                  date(2026, 10, 1), date(2026, 12, 25), date(2026, 12, 26)):
            assert d in h

    def test_easter_derived_holidays_2026(self):
        # Easter Sunday 2026 = 2026-04-05 → Good Friday 04-03, Easter Monday 04-06.
        h = holidays_for_year(2026)
        assert date(2026, 4, 3) in h   # Good Friday
        assert date(2026, 4, 6) in h   # Easter Monday

    def test_movable_islamic_holiday_in_set(self):
        assert date(2026, 3, 20) in holidays_for_year(2026)


class TestIsBusinessDay:
    def test_weekend_is_not_business_day(self):
        assert is_business_day(date(2026, 6, 6)) is False   # Saturday
        assert is_business_day(date(2026, 6, 7)) is False   # Sunday

    def test_ordinary_weekday_is_business_day(self):
        assert is_business_day(date(2026, 6, 9)) is True     # Tuesday

    def test_weekday_holiday_is_not_business_day(self):
        assert is_business_day(date(2026, 6, 12)) is False   # Democracy Day (Fri)
        assert is_business_day(date(2026, 10, 1)) is False   # Independence Day (Thu)

    def test_accepts_datetime(self):
        assert is_business_day(datetime(2026, 6, 9, 14, 30, tzinfo=timezone.utc)) is True


class TestAddBusinessDays:
    def test_skips_weekend(self):
        # Friday 2026-06-05 + 1 business day → Monday 2026-06-08.
        assert add_business_days(date(2026, 6, 5), 1) == date(2026, 6, 8)

    def test_skips_holiday(self):
        # Thursday 2026-06-11 + 1 business day skips Fri 06-12 (Democracy Day)
        # and the weekend → Monday 2026-06-15.
        assert add_business_days(date(2026, 6, 11), 1) == date(2026, 6, 15)

    def test_zero_returns_start(self):
        assert add_business_days(date(2026, 6, 9), 0) == date(2026, 6, 9)

    def test_negative_rejected(self):
        with pytest.raises(ValueError):
            add_business_days(date(2026, 6, 9), -1)


class TestBusinessDaysBetween:
    def test_full_week_has_five(self):
        # Mon 06-08 .. Mon 06-15 excludes the weekend → 5 business days,
        # but 06-12 is a holiday → 4.
        assert business_days_between(date(2026, 6, 8), date(2026, 6, 15)) == 4

    def test_end_before_start_is_zero(self):
        assert business_days_between(date(2026, 6, 15), date(2026, 6, 8)) == 0


class TestSlaDueDate:
    @pytest.mark.parametrize("tier,days", [
        (VerificationTier.BASIC, 5),
        (VerificationTier.STANDARD, 7),
        (VerificationTier.PREMIUM, 10),
    ])
    def test_due_date_counts_business_days_per_tier(self, tier, days):
        paid = date(2026, 6, 9)  # Tuesday
        due = sla_due_date(paid, tier)
        assert business_days_between(paid, due) == days
        assert SLA_BUSINESS_DAYS[tier] == days

    def test_due_date_skips_weekends_and_holidays(self):
        # Premium (10 business days) from Tue 2026-06-09 must land on a business day
        # and cross the 06-12 holiday + two weekends.
        due = sla_due_date(datetime(2026, 6, 9, 9, 0, tzinfo=timezone.utc), VerificationTier.PREMIUM)
        assert is_business_day(due) is True
        assert due == date(2026, 6, 24)


class TestCountdown:
    def test_remaining_decreases(self):
        paid = date(2026, 6, 9)
        due = sla_due_date(paid, VerificationTier.STANDARD)
        assert business_days_remaining(paid, due) == 7
        # Three business days later, four remain.
        later = add_business_days(paid, 3)
        assert business_days_remaining(later, due) == 4

    def test_remaining_zero_when_overdue(self):
        due = date(2026, 6, 9)
        assert business_days_remaining(date(2026, 6, 16), due) == 0
