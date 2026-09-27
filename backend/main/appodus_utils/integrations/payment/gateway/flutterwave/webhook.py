from __future__ import annotations
from typing import TYPE_CHECKING

from main.appodus_utils.domain.webhook.callback.model import QueryCallbackDto
from main.appodus_utils.domain.webhook.callback.service import CallbackService

if TYPE_CHECKING:
    from loguru import Logger

    from main.app.domain.payment.service import PaymentService
import hmac
from typing import Dict, Optional

from fastapi import HTTPException
from httpx import QueryParams
from kink import di, inject
from starlette import status
from starlette.responses import Response, RedirectResponse

from main.app.config.settings import IntegratedPlatform, settings
from main.appodus_utils import Utils
from main.appodus_utils.integrations.interface import BaseWebhookHandler
from main.appodus_utils.config.settings import is_configured_secret
from main.appodus_utils.integrations.payment.gateway.flutterwave.models import FlutterwaveEvent

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
        """Flutterwave v3 sends the dashboard's secret hash verbatim in `verif-hash` (it is not
        an HMAC of the body). An unconfigured secret rejects every request."""
        secret = settings.FLUTTERWAVE_WEBHOOK_SECRET
        received = headers.get("verif-hash")
        if not is_configured_secret(secret) or not received:
            return False
        return hmac.compare_digest(received.encode(), secret.encode())

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
        """Route a verified event. A charge event only asks for the charge to be confirmed
        with the gateway; the body itself never settles anything. Events we do not act on
        are acknowledged, so Flutterwave stops retrying them."""
        event = payload_dict.get("event")
        data = payload_dict.get("data") or {}

        if event == FlutterwaveEvent.CHARGE_COMPLETED.value and data.get("tx_ref"):
            await self._payments().confirm_from_gateway(data["tx_ref"])
        elif event == FlutterwaveEvent.CHARGEBACK_INITIATED.value and data.get("flw_ref"):
            # Flutterwave cites a disputed charge only by its own reference.
            await self._payments().record_chargeback(
                IntegratedPlatform.FLUTTERWAVE,
                event_id=f"flutterwave:chargeback:{data['id']}",
                gateway_reference=data["flw_ref"],
                reason=data.get("comment"),
            )
        else:
            # Transfers are settled by the payout flow (S4); refunds were accepted when issued.
            logger.info(f"Flutterwave event {event!r} acknowledged without action")
            return {"status": "ignored"}
        return {"status": "success"}

    @staticmethod
    def _payments() -> "PaymentService":
        """Resolved per event: the payment domain depends on this integration package."""
        from main.app.domain.payment.service import PaymentService
        return di[PaymentService]
