"""Confirm Money arithmetic reconciles exactly in minor units (kobo) — PRD R0.5.

Money stores an exact Decimal; verifying it never drifts the way binary floats do
underpins the pay → refund → commission → payout reconciliation requirement.
"""
from decimal import Decimal

import pytest

from main.appodus_utils.db.types.money import Money, TransactionCurrency

NGN = TransactionCurrency.NGN


def _ngn(kobo: int) -> Money:
    return Money(value=Decimal(kobo), currency=NGN)


class TestMoneyKoboReconciliation:
    def test_pay_minus_refund_is_zero(self):
        paid = _ngn(35_000_000)       # ₦350,000.00
        refund = _ngn(35_000_000)
        assert paid.minus(refund).is_equal_to(_ngn(0))

    def test_line_items_sum_to_total_exactly(self):
        # STANDARD tier line items (kobo) from the 0001 pricing reference.
        registry = _ngn(13_000_000)
        docs = _ngn(500_000)
        field = _ngn(9_000_000)
        survey = _ngn(10_000_000)
        total = registry.plus(docs).plus(field).plus(survey)
        assert total.is_equal_to(_ngn(32_500_000))
        assert total.get_value() == Decimal(32_500_000)

    def test_commission_split_reconciles(self):
        gross = _ngn(9_000_000)            # field inspection fee
        commission = _ngn(2_700_000)       # 30%
        platform_remainder = gross.minus(commission)
        assert platform_remainder.plus(commission).is_equal_to(gross)

    def test_no_float_drift_over_many_additions(self):
        acc = _ngn(0)
        for _ in range(1000):
            acc = acc.plus(_ngn(1))        # add 1 kobo, 1000 times
        assert acc.get_value() == Decimal(1000)

    def test_currency_mismatch_rejected(self):
        with pytest.raises(ValueError):
            _ngn(100).plus(Money(value=Decimal(100), currency=TransactionCurrency.USD))
