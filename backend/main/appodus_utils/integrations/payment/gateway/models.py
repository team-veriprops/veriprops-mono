import enum
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from main.appodus_utils import Object
from pydantic import Field

from main.appodus_utils.db.types.money import TransactionCurrency


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


# ─── Transfers: paying agents out (bank list → resolve → quote → send → look up) ──────


class GatewayTransferStatus(str, enum.Enum):
    """Where a transfer stands at the gateway, normalised across providers."""

    SUCCEEDED = "SUCCEEDED"
    # Refused, failed at the bank, or reversed after the fact: the money is back with us.
    FAILED = "FAILED"
    # Queued, in flight, waiting on an OTP, or a status this code does not know. None of
    # these may settle a payout, so they share one value.
    PENDING = "PENDING"


class GatewayBank(Object):
    """A bank a transfer can be sent to. ``code`` is the gateway's own code for it."""

    code: str
    name: str


class GatewayAccount(Object):
    """A bank account as the bank holds it: ``account_name`` is the bank's, never typed."""

    bank_code: str
    account_number: str
    account_name: str


# Both gateways accept this form; Paystack's is the stricter rule (lowercase, 16+ characters).
TRANSFER_REFERENCE_PATTERN = r"^[a-z0-9_-]{16,64}$"


class TransferRequest(Object):
    """Send ``amount_minor`` to one resolved bank account, under our own reference.

    The reference is how the transfer is found again when an answer is lost, and both
    gateways refuse a second transfer under a reference they have seen, so a retry of the
    same attempt can never pay twice."""

    reference: str = Field(..., pattern=TRANSFER_REFERENCE_PATTERN)
    amount_minor: int = Field(..., gt=0)
    currency: TransactionCurrency
    bank_code: str
    account_number: str
    account_name: str
    narration: str


class GatewayTransfer(Object):
    """A transfer as the gateway reports it when asked directly — what a payout settles from."""

    reference: str = Field(..., description="Our reference, as the gateway recorded it")
    gateway_transfer_id: str = Field(..., description="The gateway's own id or code for the transfer")
    status: GatewayTransferStatus
    amount_minor: int
    # The gateway's own words for a failure. Finance reads them to choose retry or reject;
    # they never reach an agent.
    failure_reason: Optional[str] = None
