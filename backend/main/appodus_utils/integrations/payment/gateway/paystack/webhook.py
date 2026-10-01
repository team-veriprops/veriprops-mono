from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

    from main.app.domain.payment.service import PaymentService
    from main.app.domain.payout.disbursement import PayoutDisbursementService
import hashlib
import hmac
from typing import Dict, Optional

from fastapi import HTTPException
from httpx import QueryParams
from kink import di, inject
from starlette import status
from starlette.responses import Response, RedirectResponse

from main.app.config.settings import IntegratedPlatform, settings
from main.appodus_utils.domain.webhook.callback.service import CallbackService
from main.appodus_utils import Utils
from main.appodus_utils.integrations.interface import BaseWebhookHandler
from main.appodus_utils.config.settings import is_configured_secret
from main.appodus_utils.integrations.payment.gateway.paystack.models import PaystackEventType


logger: Logger = di["logger"]

@inject
class PaystackWebhookHandler(BaseWebhookHandler):

    def __init__(self,
                 callback_service: CallbackService,
                 # transaction_service: TransactionService
                 ):
        # Paystack signs webhooks with the account's secret key, read at validation time.
        super().__init__(settings.PAYSTACK_SECRET_KEY)
        self._callback_service = callback_service
        # self._transaction_service = transaction_service

    @property
    def platform(self) -> IntegratedPlatform:
        return IntegratedPlatform.PAYSTACK

    async def validate_signature(self, body: bytes, headers: Dict) -> bool:
        """`x-paystack-signature` is HMAC-SHA512 of the raw body, keyed by the secret key.
        An unconfigured key rejects every request."""
        key = settings.PAYSTACK_SECRET_KEY
        received = headers.get("x-paystack-signature")
        if not is_configured_secret(key) or not received:
            return False
        expected = hmac.new(key=key.encode(), msg=body, digestmod=hashlib.sha512).hexdigest()
        return hmac.compare_digest(received, expected)

    async def _process_handle_redirect_payload(self, payload: QueryParams, headers: Dict, response: Response) -> Optional[RedirectResponse]:
        redirect_url = settings.PAYMENT_FRONTEND_REDIRECT_PATH

        status_map = {
            "cancelled": "PAYMENT_CANCELLED",
            "successful": "PAYMENT_SUCCEEDED",
            "failure": "PAYMENT_ERROR",
        }

        status = status_map.get("successful", "PAYMENT_ERROR")

        redirect_url = (
            f"{redirect_url}"
            f"?status={status}"
        )
        redirect = Utils.create_redirect(redirect_url, response)

        return redirect

    async def _process_verify_webhook_payload(self, payload: QueryParams) -> int:

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not implemented!")

    async def _process_handle_webhook_payload(self, payload_dict: Dict) -> Dict:
        """Route a verified event. A charge event only asks for the charge to be confirmed
        with the gateway; the body itself never settles anything. Events we do not act on
        are acknowledged, so Paystack stops retrying them."""
        event = payload_dict.get("event")
        data = payload_dict.get("data") or {}

        if event == PaystackEventType.CHARGE_SUCCESS.value and data.get("reference"):
            await self._payments().confirm_from_gateway(data["reference"])
        elif event == PaystackEventType.CHARGE_DISPUTE_CREATE.value and (data.get("transaction") or {}).get("reference"):
            await self._payments().record_chargeback(
                IntegratedPlatform.PAYSTACK,
                event_id=f"paystack:dispute:{data['id']}",
                tx_ref=data["transaction"]["reference"],
                reason=data.get("category"),
            )
        elif event in _TRANSFER_EVENTS and data.get("reference"):
            # Success, failure or reversal alike: the payout settles from the transfer as
            # Paystack reports it when asked, never from this body.
            await self._payouts().settle_from_gateway(data["reference"])
        else:
            # Refunds were accepted when issued; anything else needs no action.
            logger.info(f"Paystack event {event!r} acknowledged without action")
            return {"status": "ignored"}
        return {"status": "success"}

    @staticmethod
    def _payments() -> "PaymentService":
        """Resolved per event: the payment domain depends on this integration package."""
        from main.app.domain.payment.service import PaymentService
        return di[PaymentService]

    @staticmethod
    def _payouts() -> "PayoutDisbursementService":
        """Resolved per event, for the same reason as `_payments`."""
        from main.app.domain.payout.disbursement import PayoutDisbursementService
        return di[PayoutDisbursementService]


_TRANSFER_EVENTS = {
    PaystackEventType.TRANSFER_SUCCESS.value,
    PaystackEventType.TRANSFER_FAILED.value,
    PaystackEventType.TRANSFER_REVERSED.value,
}
