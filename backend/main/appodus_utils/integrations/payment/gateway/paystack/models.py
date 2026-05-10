from datetime import datetime

from main.appodus_utils import Object
import enum
from typing import Literal, Optional, Union, Dict, Any, List

from pydantic import Field

from main.appodus_utils.db.types.money import TransactionCurrency


class PaystackChannel(str, enum.Enum):
    CARD = "card"
    BANK = "bank"
    BANK_TRANSFER = "bank_transfer"
    USSD = "ussd"
    QR = "qr"
    MOBILE_MONEY = "mobile_money"

class PaystackInitPaymentDto(Object):
    # ── Required ──────────────────────────────
    email: str
    amount: int = Field(..., description="Amount in kobo (₦1,000 = 100000)")

    # ── Common Optional ───────────────────────
    reference: Optional[str] = None
    currency: Optional[TransactionCurrency] = TransactionCurrency.NGN
    callback_url: Optional[str] = None

    # ── Payment Channels ──────────────────────
    channels: Optional[List[PaystackChannel]] = None
    # e.g. ["card", "bank_transfer", "ussd"]

    # ── Customer Info ─────────────────────────
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None

    # ── Metadata (your business payload) ──────
    metadata: Optional[Dict[str, Any]] = None

    # ── Payment Control ───────────────────────
    invoice_limit: Optional[int] = None
    expires_at: Optional[datetime] = None

    # ── Split / Marketplace ───────────────────
    split_code: Optional[str] = None
    subaccount: Optional[str] = None
    transaction_charge: Optional[int] = None
    bearer: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "buyer@email.com",
                "amount": 2500000,
                "currency": "NGN",
                "reference": "VRP-2026-00023",
                "callback_url": "https://veriprops.com/pay/verify",
                "channels": ["card", "bank_transfer", "ussd"],
                "metadata": {
                    "invoice_id": "inv_123",
                    "contract_id": "ctr_456",
                    "payment_object": "verification"
                },
                "first_name": "Kingsley",
                "last_name": "Ezenwere",
                "phone": "08012345678"
            }
        }
    }


###############################################################################################################
##########################  WEBHOOK ###########################################################################

# CreateRecipientRequest
class CreateRecipientRequest(Object):
    type: str = Field(default="nuban", description="Recipient type, usually 'nuban'")
    name: str = Field(..., description="Recipient's full name")
    account_number: str
    bank_code: str
    bank_name: str
    currency: TransactionCurrency = Field(...)


# CreateRecipientResponse
class RecipientData(Object):
    recipient_code: str
    name: str
    account_number: str
    bank_code: str
    currency: TransactionCurrency
    description: Optional[str] = None
    active: Optional[bool] = None
    email: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CreateRecipientResponse(Object):
    status: bool
    message: str
    data: RecipientData

# === Paystack Event Types ===
class PaystackEventType(str, enum.Enum):
    CHARGE_SUCCESS = "charge.success"
    CHARGE_FAILED = "charge.failed"
    TRANSFER_SUCCESS = "transfer.success"
    TRANSFER_FAILED = "transfer.failed"
    TRANSFER_REVERSED = "transfer.reversed"
    REFUND_SUCCESS = "refund.success"
    SUBSCRIPTION_CREATE = "subscription.create"
    SUBSCRIPTION_DISABLE = "subscription.disable"
    INVOICE_CREATE = "invoice.create"
    INVOICE_UPDATE = "invoice.update"
    INVOICE_SETTLED = "invoice.settled"
    INVOICE_STALE = "invoice.stale"
    PAYMENT_REQUEST_SUCCESS = "paymentrequest.success"
    PAYMENT_REQUEST_FAILED = "paymentrequest.failed"
    CUSTOMERIDENTITY_VERIFICATION_SUCCESS = "customeridentification.success"
    CUSTOMERIDENTITY_VERIFICATION_FAILED = "customeridentification.failed"

# === Webhook Payload Models ===
class CustomerData(Object):
    id: Optional[int] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    international_format_phone: Optional[str] = None
    customer_code: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    risk_action: Optional[str] = None


class AuthorizationData(Object):
    account_name: Optional[str] = None
    authorization_code: Optional[str] = None
    bank: Optional[str] = None
    bin: Optional[str] = None
    brand: Optional[str] = None
    card_type: Optional[str] = None
    channel: Optional[str] = None
    country_code: Optional[str] = None
    exp_month: Optional[str] = None
    exp_year: Optional[str] = None
    last4: Optional[str] = None
    receiver_bank: Optional[str] = None
    receiver_bank_account_number: Optional[str] = None
    reusable: Optional[bool] = None
    signature: Optional[str] = None


class SourceData(Object):
    entry_point: Optional[str] = None
    identifier: Optional[str] = None
    source: Optional[str] = None
    type: Optional[str] = None


class ChargeSuccessData(Object):

    id: int

    amount: int
    requested_amount: Optional[int] = None
    currency: TransactionCurrency

    status: Literal["success"]
    channel: Optional[str] = None
    domain: Optional[str] = None

    reference: str
    gateway_response: Optional[str] = None

    created_at: Optional[str] = None
    paid_at: Optional[str] = None

    ip_address: Optional[str] = None

    fees: Optional[int] = None
    fees_breakdown: Optional[Any] = None
    fees_split: Optional[Any] = None

    order_id: Optional[str] = None

    message: Optional[str] = None
    log: Optional[Any] = None

    metadata: Optional[Dict[str, Any]] = None

    plan: Optional[Dict[str, Any]] = None
    split: Optional[Dict[str, Any]] = None
    subaccount: Optional[Dict[str, Any]] = None

    pos_transaction_data: Optional[Any] = None

    customer: CustomerData
    authorization: Optional[AuthorizationData] = None
    source: Optional[SourceData] = None

    # ─────────────────────────────────────────────
    @staticmethod
    def to_naira(amount: int) -> float:
        """
        Converts Paystack integer kobo safely to NGN float.
        """
        return float(amount / 100)


class TransferData(Object):
    id: int
    amount: int
    currency: TransactionCurrency
    reason: Optional[str]
    recipient: str
    reference: str
    status: Literal["success", "failed", "reversed"]
    transfer_code: str


class RefundData(Object):
    id: int
    transaction: int
    reference: str
    amount: int
    created_at: str
    currency: TransactionCurrency
    channel: str
    status: str


class PaystackWebhookPayload(Object):
    event: PaystackEventType
    data: Union[Optional[RefundData], Optional[TransferData], Optional[ChargeSuccessData], Optional[AuthorizationData], Optional[CustomerData]]


# ── Bank transfer collection (POST /charge with bank_transfer field) ──


class PaystackBankTransferChargeRequest(Object):
    email: str
    amount: int = Field(..., description="Amount in kobo")
    bank_transfer: Dict[str, Any] = Field(default_factory=dict)
    currency: str = "NGN"
    reference: Optional[str] = None


class PaystackBankTransferResult(Object):
    reference: str
    bank: str
    account_number: str
    account_name: Optional[str] = None
    expiry_date: Optional[str] = None
