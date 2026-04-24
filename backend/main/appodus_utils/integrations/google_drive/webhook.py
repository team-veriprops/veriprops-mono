import hashlib
import hmac
from logging import Logger
from typing import Dict

from fastapi import HTTPException
from kink import di, inject
from starlette.datastructures import QueryParams
from starlette.responses import JSONResponse, Response

from main.app.config.settings import settings, IntegratedPlatform
from main.app.domain.webhook.callback.model import CreateCallbackDto, CallbackType, QueryCallbackDto
from main.app.domain.webhook.callback.service import CallbackService
from main.appodus_utils.integrations.google_drive.models import GoogleDriveWebhookPayload
from main.appodus_utils.integrations.interface import BaseWebhookHandler
from main.appodus_utils import Utils

logger: Logger = di['logger']

@inject
class GoogleWebhookHandler(BaseWebhookHandler):
    def __init__(self,
                 callback_service: CallbackService):
        super().__init__(settings.GOOGLE_WEBHOOK_SECRET)
        self._callback_service = callback_service

    @staticmethod
    def get_property_contract_service(): # Prevents cyclic dependency
        from main.app.domain.property.contract.service import PropertyContractService
        property_contract_service: PropertyContractService = di[PropertyContractService]

        return property_contract_service

    @property
    def platform(self) -> IntegratedPlatform:
        return IntegratedPlatform.GOOGLE_DRIVE

    async def webhook_replay_handler(self, callback: QueryCallbackDto) -> bool:
        payload = GoogleDriveWebhookPayload(**callback.payload)
        if callback.event_type == CallbackType.CONTRACT_UPDATED:
            await self.get_property_contract_service().handle_change(payload.fileId)

        return await self._callback_service.update_callback__handled(callback.id)

    async def validate_signature(self, body: bytes, headers: Dict) -> bool:

        # Get the verification token from headers
        verification_token = headers.get('X-Goog-Resource-State')
        if not verification_token:
            return False

        received_signature = headers.get('X-Goog-Signature')

        expected_signature = hmac.new(
            key=self.platform_secret.encode(),
            msg=body,
            digestmod=hashlib.sha256
        ).hexdigest()

        # Compare securely
        return hmac.compare_digest(received_signature, expected_signature)

    async def _process_handle_redirect_payload(self, payload: QueryParams, headers: Dict, response: Response) -> Dict:
        pass

    async def _process_verify_webhook_payload(self, payload: QueryParams):
        """Handle webhook verification challenge"""
        challenge = payload.get('challenge')
        if not challenge:
            raise HTTPException(status_code=400, detail="Missing challenge")
        return JSONResponse(content={"challenge": challenge})

    async def _process_handle_webhook_payload(self, payload: Dict):

        google_drive_payload = GoogleDriveWebhookPayload(**payload)

        # Handle different notification types
        if google_drive_payload.is_sync_notification():
            # Initial sync notification
            return JSONResponse(content={"status": "sync"})

        if google_drive_payload.is_update_notification():
            handle_from_time = Utils.datetime_now_plus(seconds=settings.GOOGLE_DOC_CHANGE_UPDATE_WINDOW)
            create_dto = CreateCallbackDto(
                platform=IntegratedPlatform.GOOGLE_DRIVE,
                event_type=CallbackType.CONTRACT_UPDATED,
                external_id=google_drive_payload.resourceId,
                payload=google_drive_payload,
                handle_from_time=handle_from_time
            )
            if await self._callback_service.exists_for_event(create_dto):
                await self._callback_service.update_callback__handle_time(create_dto)
            else:
                await self._callback_service.create_callback(create_dto)

        return JSONResponse(content={"status": "processed"})
