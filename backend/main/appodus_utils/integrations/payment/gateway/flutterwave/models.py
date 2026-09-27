import enum


class FlutterwaveEvent(str, enum.Enum):
    """Flutterwave v3 webhook event names the integration recognises."""

    CHARGE_COMPLETED = "charge.completed"
    TRANSFER_COMPLETED = "transfer.completed"
    REFUND_COMPLETED = "refund.completed"
    # Chargeback webhooks must be enabled by Flutterwave support; they cite the charge by flw_ref.
    CHARGEBACK_INITIATED = "chargeback.initiated"
    CHARGEBACK_ACCEPTED = "chargeback.accepted"
    CHARGEBACK_DECLINED = "chargeback.declined"
    CHARGEBACK_LOST = "chargeback.lost"
