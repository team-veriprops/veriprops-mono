from typing import Optional
from math import floor

from main.appodus_utils.integrations.payment.gateway.models import PaymentInitRequest
from main.appodus_utils.integrations.payment.gateway.paystack.models import PaystackInitPaymentDto


class PaystackMapper:
    """
    Maps internal payment requests to Paystack-compatible payloads.
    """

    @staticmethod
    def to_init_payment_dto(
        request: PaymentInitRequest
    ) -> PaystackInitPaymentDto:
        first_name, last_name = PaystackMapper._split_name(request.customer.name)

        return PaystackInitPaymentDto(
            email=request.customer.email,
            amount=PaystackMapper._to_kobo(request.amount),
            currency=request.currency,
            reference=request.tx_ref,
            callback_url=request.redirect_url,
            first_name=first_name,
            last_name=last_name,
            phone=request.customer.phonenumber,
            metadata={
                **(request.metadata or {}),
                "title": request.customizations.title,
                "description": request.customizations.description,
            },
        )

    # ─────────────────────────────────────────────

    @staticmethod
    def _to_kobo(amount: float) -> int:
        """
        Converts NGN float to Paystack integer kobo safely.
        """
        return int(round(amount * 100))

    @staticmethod
    def _split_name(full_name: str) -> tuple[Optional[str], Optional[str]]:
        """
        Splits 'John Doe Smith' → ('John', 'Doe Smith')
        Handles single names gracefully.
        """
        parts = full_name.strip().split()

        if not parts:
            return None, None

        if len(parts) == 1:
            return parts[0], None

        return parts[0], " ".join(parts[1:])
