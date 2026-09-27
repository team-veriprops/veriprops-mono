import enum
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, Optional

from main.appodus_utils import Object
from pydantic import Field

from main.appodus_utils.db.types.money import TransactionCurrency


class GenericPaymentGatewayResponse(Object):
    status: str | bool | None
    message: str
    data: Optional[Dict[str, Any]] = None  # e.g., {"link": "..."} or nested objects


# ─── Collection: the provider-neutral contract (checkout → charge → refund) ────────────
#
# Every amount inside Veriprops is in minor units (kobo, cents). Each adapter converts at its
# own boundary: Flutterwave speaks major units, Paystack speaks kobo.


class GatewayChargeStatus(str, enum.Enum):
    """Where a charge stands at the gateway, normalised across providers."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    # Not settled yet, abandoned at the checkout, or a status this code does not know. None
    # of these may move a payment, so they share one value.
    PENDING = "PENDING"


class HostedCheckoutRequest(Object):
    """Open a gateway-hosted checkout for one charge. The customer pays on the gateway's page
    and is sent back to ``redirect_url``; Veriprops never sees card or bank details."""

    reference: str = Field(..., description="Our tx_ref; the gateway echoes it on every event for the charge")
    amount_minor: int = Field(..., gt=0)
    currency: TransactionCurrency
    redirect_url: str
    customer_email: str
    customer_phone: Optional[str] = None
    customer_name: str
    title: str
    description: str


class GatewayCharge(Object):
    """A charge as the gateway reports it when asked directly.

    This, never a webhook body, is what a payment is settled from: a webhook only says
    "go and look", and the answer is checked against what Veriprops asked the customer to pay.
    """

    reference: str = Field(..., description="Our tx_ref, as the gateway recorded it")
    gateway_transaction_id: str = Field(..., description="The gateway's id for the charge (refunds address it)")
    gateway_reference: str = Field(..., description="The gateway's own reference (Flutterwave flw_ref); chargebacks cite it")
    status: GatewayChargeStatus
    amount_minor: int
    currency: TransactionCurrency


def to_minor_units(amount_major: float | int | str) -> int:
    """A gateway's major-unit amount in minor units, without float drift (1500.5 → 150050)."""
    return int((Decimal(str(amount_major)) * 100).to_integral_value(rounding=ROUND_HALF_UP))


def to_major_units(amount_minor: int) -> float:
    """Minor units as the major-unit number a gateway expects (150050 → 1500.5)."""
    return float(Decimal(amount_minor) / 100)


# initialize_bank_transfer – Send Money to Bank
class BankTransferRequest(Object):
    account_bank: str = Field(..., description="Bank code (e.g., 044 for GTBank)")
    account_number: str
    amount: float
    narration: str
    currency: TransactionCurrency
    reference: str
    callback_url: Optional[str] = None
    debit_currency: Optional[str] = None
    fullname: str
    recipient_code:  Optional[str] = None


class BankTransferResponseData(Object):
    id: int
    account_number: str
    bank_code: str
    full_name: Optional[str]
    date_created: Optional[str]
    currency: TransactionCurrency
    amount: float
    fee: Optional[float]
    status: str
    reference: str


class BankTransferResponse(Object):
    message: str
    data: BankTransferResponseData


# get_transfer_fee
class TransferFeeRequest(Object):
    amount: float
    currency: TransactionCurrency


class TransferFeeResponseData(Object):
    currency: TransactionCurrency
    amount: float
    fee: float


class TransferFeeResponse(Object):
    status: str
    message: str
    data: TransferFeeResponseData


# get_all_country_banks
class Bank(Object):
    id: int
    code: str
    name: str


class CountryBanksResponse(Object):
    status: str
    message: str
    data: list[Bank]
