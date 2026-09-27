from typing import Optional

from main.appodus_utils.integrations.payment.gateway.models import HostedCheckoutRequest
from main.appodus_utils.integrations.payment.gateway.paystack.models import PaystackInitPaymentDto


class PaystackMapper:
    """Maps the provider-neutral checkout request onto Paystack's /transaction/initialize body."""

    @staticmethod
    def to_init_payment_dto(request: HostedCheckoutRequest) -> PaystackInitPaymentDto:
        first_name, last_name = PaystackMapper._split_name(request.customer_name)
        return PaystackInitPaymentDto(
            email=request.customer_email,
            # Already in the currency's minor unit, which is what Paystack takes.
            amount=request.amount_minor,
            currency=request.currency,
            reference=request.reference,
            callback_url=request.redirect_url,
            first_name=first_name,
            last_name=last_name,
            phone=request.customer_phone,
            metadata={"title": request.title, "description": request.description},
        )

    @staticmethod
    def _split_name(full_name: str) -> tuple[Optional[str], Optional[str]]:
        """'John Doe Smith' → ('John', 'Doe Smith'); a single name has no last name."""
        parts = full_name.strip().split()
        if not parts:
            return None, None
        if len(parts) == 1:
            return parts[0], None
        return parts[0], " ".join(parts[1:])
