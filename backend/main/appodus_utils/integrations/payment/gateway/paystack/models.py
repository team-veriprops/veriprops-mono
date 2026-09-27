from datetime import datetime

from main.appodus_utils import Object
import enum
from typing import Optional, Dict, Any, List

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
                "callback_url": "https://veriprops.ng/pay/verify",
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

# === Paystack Event Types ===
class PaystackEventType(str, enum.Enum):
    CHARGE_SUCCESS = "charge.success"
    CHARGE_FAILED = "charge.failed"
    TRANSFER_SUCCESS = "transfer.success"
    TRANSFER_FAILED = "transfer.failed"
    TRANSFER_REVERSED = "transfer.reversed"
    REFUND_SUCCESS = "refund.success"
    REFUND_PROCESSED = "refund.processed"
    REFUND_FAILED = "refund.failed"
    CHARGE_DISPUTE_CREATE = "charge.dispute.create"
    CHARGE_DISPUTE_REMIND = "charge.dispute.remind"
    CHARGE_DISPUTE_RESOLVE = "charge.dispute.resolve"
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

