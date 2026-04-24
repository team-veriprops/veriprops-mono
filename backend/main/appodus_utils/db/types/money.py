import enum
from decimal import Decimal, ROUND_HALF_UP

from pydantic import Field, ConfigDict

from main.appodus_utils import Object

VAT_RATE = Decimal("0.075")  # 7.5%


class TransactionCurrency(str, enum.Enum):
    NGN = "NGN"
    USD = "USD"
    GBP = "GBP"
    EUR = "EUR"

    @property
    def symbol(self) -> str:
        return CURRENCY_SYMBOLS[self.value]

    @property
    def name(self) -> str:
        return CURRENCY_NAMES[self.value]

    @property
    def fx_rate(self):
        return FX_RATES[self.value]


FX_RATES: dict[str, Decimal] = {
    TransactionCurrency.NGN: Decimal("1"),
    TransactionCurrency.USD: Decimal("0.00063"),
    TransactionCurrency.GBP: Decimal("0.00050"),
    TransactionCurrency.EUR: Decimal("0.00058"),
}

CURRENCY_SYMBOLS: dict[str, str] = {
    TransactionCurrency.NGN: "₦",
    TransactionCurrency.USD: "$",
    TransactionCurrency.GBP: "£",
    TransactionCurrency.EUR: "€",
}

CURRENCY_NAMES: dict[str, str] = {
    TransactionCurrency.NGN: "Nigerian Naira",
    TransactionCurrency.USD: "US Dollar",
    TransactionCurrency.GBP: "British Pound",
    TransactionCurrency.EUR: "Euro",
}


class Money(Object):
    value: Decimal = Field(0.0)
    currency: TransactionCurrency = Field(None)

    def get_value(self) -> Decimal:
        return self.value

    def get_float_value(self) -> float:
        quantized = self.value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return float(quantized)

    def get_currency(self) -> TransactionCurrency:
        return self.currency

    def plus(self, money: 'Money') -> 'Money':
        self._validate_currency(money.get_currency())
        self._validate_negative_credit(money.get_value())

        new_value = self.value + money.get_value()
        return Money(value=new_value, currency=self.currency)

    def minus(self, money: 'Money') -> 'Money':
        self._validate_debit_balance(money.get_value())
        self._validate_currency(money.get_currency())
        self._validate_negative_debit(money.get_value())

        new_value = self.value - money.get_value()
        return Money(value=new_value, currency=self.currency)

    def compare(self, other: 'Money') -> Decimal:
        """
        Compare self to other.  Return a decimal value:

            a or b is a NaN ==> Decimal('NaN')
            a < b           ==> Decimal('-1')
            a == b          ==> Decimal('0')
            a > b           ==> Decimal('1')

        :param other:
        :return:
        """
        self._validate_currency(other.get_currency())
        return self.value.compare(other.get_value())

    def is_less_than(self, other: 'Money') -> bool:
        return self.value.compare(other.get_value()) < 0

    def is_greater_than(self, other: 'Money') -> bool:
        return self.value.compare(other.get_value()) > 0

    def is_equal_to(self, other: 'Money') -> bool:
        return self.value.compare(other.get_value()) == 0

    def has_value(self):
        return self.is_greater_than(Money(value=Decimal(0), currency=self.currency))

    def _validate_currency(self, currency: TransactionCurrency):
        if self.currency != currency:
            raise ValueError("Money exception: currency mismatch")

    @staticmethod
    def _validate_negative_credit(amount: Decimal):
        if amount.compare(Decimal(0)) == Decimal(-1):
            raise ValueError("Money exception: negative credit amount")

    @staticmethod
    def _validate_negative_debit(amount: Decimal):
        if amount.compare(Decimal(0)) == Decimal(-1):
            raise ValueError("Money exception: negative debit amount")

    def _validate_debit_balance(self, amount: Decimal):
        if self.value.compare(Decimal(0)) == Decimal(-1) or self.value.compare(amount) == Decimal(-1):
            raise ValueError("Money exception: insufficient balance")

    model_config = ConfigDict(
        # strict=True,
        populate_by_name=True,  # allows using the alias when parsing
        # extra="forbid"          # disallow any extra fields not defined here
    )
