from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
import hashlib
import hmac
from decimal import Decimal
from typing import Dict, Optional

from fastapi import HTTPException
from httpx import QueryParams
from kink import di, inject
from starlette import status
from starlette.responses import Response, RedirectResponse

from main.app.config.settings import IntegratedPlatform, settings
# from main.app.domain.payment.transaction.service import TransactionService
from main.app.domain.webhook.callback.model import QueryCallbackDto
from main.app.domain.webhook.callback.service import CallbackService
from main.appodus_utils import Utils
from main.appodus_utils.db.types.money import Money
from main.appodus_utils.integrations.interface import BaseWebhookHandler
from main.appodus_utils.integrations.payment.gateway.flutterwave.models import FlutterwaveWebhookPayload, FlutterwaveEvent, \
    WebhookData

logger: Logger = di["logger"]

@inject
class FlutterwaveWebhookHandler(BaseWebhookHandler):
    def __init__(self,
                 callback_service: CallbackService,
                 # transaction_service: TransactionService
                 ):
        super().__init__(settings.FLUTTERWAVE_WEBHOOK_SECRET)
        self._callback_service = callback_service
        # self._transaction_service = transaction_service

    @property
    def platform(self) -> IntegratedPlatform:
        return IntegratedPlatform.FLUTTERWAVE

    async def validate_signature(self, body: bytes, headers: Dict) -> bool:
        received_signature = headers.get("verif-hash")
        if not received_signature:
            return False

        expected_signature = hmac.new(key=self.platform_secret.encode(), msg=body, digestmod=hashlib.sha256).hexdigest()

        # Compare securely
        return hmac.compare_digest(received_signature, expected_signature)

    async def webhook_replay_handler(self, callback: QueryCallbackDto) -> None:
        pass

    async def _process_handle_redirect_payload(self, payload: QueryParams, headers: Dict, response: Response) -> Optional[RedirectResponse]:
        redirect_url = settings.PAYMENT_FRONTEND_REDIRECT_PATH

        status_map = {
            "cancelled": "PAYMENT_CANCELLED",
            "successful": "PAYMENT_SUCCEEDED",
            "failure": "PAYMENT_ERROR",
        }

        status = status_map.get(payload.get("status").lower(), "PAYMENT_ERROR")

        redirect_url = (
            f"{redirect_url}"
            f"?status={status}"
        )
        redirect = Utils.create_redirect(redirect_url, response)

        return redirect

    async def _process_verify_webhook_payload(self, payload: QueryParams) -> int:

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not implemented!")

    async def _process_handle_webhook_payload(self, payload_dict: Dict) -> Dict:
        payload = FlutterwaveWebhookPayload(**payload_dict)

        event = payload.event
        data = payload.data

        if event == FlutterwaveEvent.CHARGE_COMPLETED and data.status == "successful":
            # Handle successful payment
            await self.handle_charge_completed(data)

        elif event == FlutterwaveEvent.TRANSFER_COMPLETED:
            # Handle successful transfer
            await self.handle_transfer_completed(data)

        elif event == FlutterwaveEvent.TRANSFER_FAILED:
            # Handle failed transfer
            await self.handle_transfer_failed(data)

        elif event == FlutterwaveEvent.REFUND_COMPLETED:
            # Handle refund confirmation
            await self.handle_refund_completed(data)

        elif event == FlutterwaveEvent.VIRTUAL_ACCOUNT_CREATED:
            # Handle virtual account creation
            await self.handle_virtual_account_created(data)

        elif event == FlutterwaveEvent.BILL_COMPLETED:
            # Handle successful bill payment
            await self.handle_bill_completed(data)

        elif event == FlutterwaveEvent.PAYMENT_LINK_CANCELLED:
            # Handle payment link cancellation
            await self.handle_payment_link_cancelled(data)

        else:
            # Log unhandled event
            msg = f"Unhandled Flutterwave event: {event}, Data: {data}"
            logger.error(msg)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)

        return {"status": "success"}

    # === Handlers (Stub Implementations) ===

    async def handle_charge_completed(self, data: WebhookData):
        # Bridge Flutterwave webhook → veriprops PaymentService.
        from main.app.domain.payment.service import PaymentService
        from main.app.domain.payment.models import PaymentStatus
        payment_service: PaymentService = di[PaymentService]
        await payment_service.record_provider_event(
            provider_ref=data.reference,
            status=PaymentStatus.SUCCEEDED.value,
            payload=data.model_dump() if hasattr(data, "model_dump") else dict(data.__dict__),
        )

    async def handle_transfer_completed(self, data: WebhookData):
        print("Transfer completed", data)

    async def handle_transfer_failed(self, data: WebhookData):
        print("Transfer failed", data)

    async def handle_refund_completed(self, data: WebhookData):
        print("Refund completed", data)

    async def handle_virtual_account_created(self, data: WebhookData):
        print("Virtual account created", data)

    async def handle_bill_completed(self, data: WebhookData):
        print("Bill completed", data)

    async def handle_payment_link_cancelled(self, data: WebhookData):
        print("Payment link cancelled", data)
