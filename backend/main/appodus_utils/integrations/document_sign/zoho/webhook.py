from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
import hashlib
import hmac
from typing import Dict, Optional

from fastapi import HTTPException
from kink import di, inject
from starlette import status
from starlette.datastructures import QueryParams
from starlette.responses import Response, RedirectResponse

from main.app.config.settings import settings, IntegratedPlatform
from main.app.domain.webhook.callback.model import QueryCallbackDto
from main.appodus_utils.integrations.interface import BaseWebhookHandler

logger: Logger = di['logger']

@inject
class ZohoWebhookHandler(BaseWebhookHandler):

    def __init__(self):
        super().__init__(settings.ZOHO_WEBHOOK_SECRET)

    async def webhook_replay_handler(self, callback: QueryCallbackDto) -> None:
        pass

    @property
    def platform(self) -> IntegratedPlatform:
        return IntegratedPlatform.ZOHO_DOC_SIGN

    async def _process_handle_redirect_payload(self, payload: QueryParams, headers: Dict, response: Response) -> \
    Optional[RedirectResponse]:
        pass

    async def _process_verify_webhook_payload(self, payload: QueryParams) -> int:

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not implemented")

    async def validate_signature(self, body: bytes, headers: Dict) -> bool:
        received_signature = headers.get("x-zoho-signature")
        if not received_signature:
            return False

        expected_signature = hmac.new(
            key=settings.ZOHO_WEBHOOK_SECRET.encode(),
            msg=body,
            digestmod=hashlib.sha256
        ).hexdigest()

        # Compare securely
        return hmac.compare_digest(received_signature, expected_signature)

    async def _process_handle_webhook_payload(self, payload: Dict) -> Dict:
        logger.info(f"Received webhook event: {payload['event']}")

        # Process events (e.g., update DB when document is signed)
        if payload["event"] == "request_signed":
            request_id = payload["request_id"]
            logger.info(f"Document {request_id} was signed!")

        return {"status": "success"}
