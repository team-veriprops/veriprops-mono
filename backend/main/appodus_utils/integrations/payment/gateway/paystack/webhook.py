from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
import hashlib
import hmac
from typing import Dict, Optional

from asyncmy.converters import Decimal
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
from main.appodus_utils.integrations.payment.gateway.paystack.models import PaystackWebhookPayload, PaystackEventType, \
    ChargeSuccessData, TransferData, RefundData


logger: Logger = di["logger"]

@inject
class PaystackWebhookHandler(BaseWebhookHandler):

    def __init__(self,
                 callback_service: CallbackService,
                 # transaction_service: TransactionService
                 ):
        super().__init__(settings.PAYSTACK_WEBHOOK_SECRET)
        self._callback_service = callback_service
        # self._transaction_service = transaction_service

    @property
    def platform(self) -> IntegratedPlatform:
        return IntegratedPlatform.PAYSTACK

    async def validate_signature(self, body: bytes, headers: Dict) -> bool:
        received_signature = headers.get("x-paystack-signature")
        if not received_signature:
            return False

        expected_signature = hmac.new(key=self.platform_secret.encode(), msg=body, digestmod=hashlib.sha512).hexdigest()

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
        payload = PaystackWebhookPayload(**payload_dict)

        event = payload.event
        data = payload.data

        if event == PaystackEventType.CHARGE_SUCCESS:
            await self.handle_charge_success(data)

        elif event == PaystackEventType.TRANSFER_SUCCESS:
            await self.handle_transfer_success(data)

        elif event == PaystackEventType.TRANSFER_FAILED:
            await self.handle_transfer_failed(data)

        elif event == PaystackEventType.TRANSFER_REVERSED:
            await self.handle_transfer_reversed(data)

        elif event == PaystackEventType.REFUND_SUCCESS:
            await self.handle_refund_success(data)
        else:
            # Log unhandled event
            msg = f"Unhandled Paystack event: {event}, Data: {data}"
            logger.error(msg)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)

        return {"status": "success"}

    # === Event-specific Handlers ===
    async def handle_charge_success(self, data: ChargeSuccessData):
        print(f"[charge.success] Payment received: {data.amount} from {data.customer.email}")

        paid_amount = Money(value=Decimal(ChargeSuccessData.to_naira(data.amount)), currency=data.currency)
        authorization_dict = data.authorization.model_dump(exclude_none=True)
        await self._transaction_service.finalize_transaction(ext_ref=data.reference, payment_channel=data.channel, paid_amount=paid_amount, extra_data=authorization_dict)

    async def handle_transfer_success(self, data: TransferData):
        print(f"[transfer.success] Transfer to {data.recipient} successful. Ref: {data.reference}")

    async def handle_transfer_failed(self, data: TransferData):
        print(f"[transfer.failed] Transfer to {data.recipient} failed. Ref: {data.reference}")

    async def handle_transfer_reversed(self, data: TransferData):
        print(f"[transfer.reversed] Transfer reversed. Ref: {data.reference}")

    async def handle_refund_success(self, data: RefundData):
        print(f"[refund.success] Refund successful. Ref: {data.reference}")
