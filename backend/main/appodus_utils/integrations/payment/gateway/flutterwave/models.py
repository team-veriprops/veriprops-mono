import enum
from typing import Literal, Optional

from main.appodus_utils import Object
from main.appodus_utils.db.types.money import TransactionCurrency


# === Flutterwave Event Types ===
class FlutterwaveEvent(str, enum.Enum):
    CHARGE_COMPLETED = "charge.completed"
    TRANSFER_COMPLETED = "transfer.completed"
    TRANSFER_FAILED = "transfer.failed"
    REFUND_COMPLETED = "refund.completed"
    VIRTUAL_ACCOUNT_CREATED = "virtualaccount.created"
    BILL_COMPLETED = "bill.completed"
    PAYMENT_LINK_CANCELLED = "paymentlink.cancelled"

# === Webhook Payload Models ===
class WebhookCustomer(Object):
    name: Optional[str]
    email: Optional[str]
    phonenumber: Optional[str]

class WebhookData(Object):
    id: int
    tx_ref: Optional[str]
    flw_ref: Optional[str]
    amount: Optional[float]
    currency: Optional[TransactionCurrency]
    status: Optional[str]
    customer: Optional[WebhookCustomer] = None
    account_number: Optional[str] = None
    bank_code: Optional[str] = None
    full_name: Optional[str] = None
    created_at: Optional[str] = None
    reference: Optional[str] = None
    fee: Optional[float] = None
    narration: Optional[str] = None
    destination: Optional[str] = None

class FlutterwaveWebhookPayload(Object):
    event: FlutterwaveEvent
    data: WebhookData
    hash: str  # For verification
