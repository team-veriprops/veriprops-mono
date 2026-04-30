from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
from datetime import datetime

from fastapi import HTTPException
from kink import di, inject

from main.app.config.settings import settings, IntegratedPlatform
from main.appodus_utils import Page
from main.app.domain.webhook.google_drive.model import CreateGoogleDriveWebhookSubscriptionDto, \
    QueryGoogleDriveWebhookSubscriptionDto, SearchGoogleDriveWebhookSubscriptionDto, \
    _UpdateGoogleDriveWebhookSubscriptionDto
from main.app.domain.webhook.google_drive.repo import GoogleDriveWebhookSubscriptionRepo
from main.app.domain.webhook.google_drive.validator import GoogleDriveWebhookSubscriptionValidator
from main.appodus_utils.integrations.google_drive.google_drive_client import GoogleDriveClient
from main.app.utils.decorators.decorate_all_methods import decorate_all_methods
from main.app.utils.decorators.method_trace_logger import method_trace_logger
from main.app.utils.decorators.transactional import transactional
from main.appodus_utils import Utils

logger: Logger = di['logger']


@inject
@decorate_all_methods(transactional(), exclude=['__init__'], exclude_startswith='_')
@decorate_all_methods(method_trace_logger, exclude=['__init__'], exclude_startswith='_')
class GoogleDriveWebhookSubscriptionService:
    def __init__(self, g_drive_subscription_repo: GoogleDriveWebhookSubscriptionRepo,
                 g_drive_subscription_validator: GoogleDriveWebhookSubscriptionValidator,
                 google_drive_client:  GoogleDriveClient):
        self._g_drive_subscription_repo = g_drive_subscription_repo
        self._g_drive_subscription_validator = g_drive_subscription_validator
        self._google_drive = google_drive_client

    async def create_g_drive_subscription(self, google_doc_id: str,
                                          contract_id: str) -> QueryGoogleDriveWebhookSubscriptionDto:

        webhook_url = f"{settings.APP_DOMAIN}{settings.WEBHOOK_PATH}/{IntegratedPlatform.GOOGLE_DRIVE}"
        channel_id = f"webhook_{contract_id}_{Utils.datetime_now().timestamp()}"

        try:
            result = await self._google_drive.watch_file_changes(
                file_id=google_doc_id,
                channel_id=channel_id,
                webhook_url=webhook_url)

            obj_in: CreateGoogleDriveWebhookSubscriptionDto = CreateGoogleDriveWebhookSubscriptionDto(
                resource_id=result['resourceId'],
                google_doc_id=google_doc_id,
                contract_id=contract_id,
                expiration=datetime.fromtimestamp(int(result['expiration']) / 1000),
                webhook_url=webhook_url,
                channel_id=channel_id
            )
            return await self._g_drive_subscription_repo.create(obj_in)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to create document change notification: {str(e)}"
            )

    async def renew_webhook_subscription(self, g_drive_subscription_id: str) -> QueryGoogleDriveWebhookSubscriptionDto:
        """ Renew an expiring webhook subscription """
        await self._g_drive_subscription_validator.should_exist_by_id(g_drive_subscription_id)

        try:
            subscription = await self._g_drive_subscription_repo.get(g_drive_subscription_id)

            result = await self._google_drive.watch_file_changes(
                file_id=subscription.google_doc_id,
                channel_id=subscription.channel_id,
                webhook_url=subscription.webhook_url)

            obj_in = _UpdateGoogleDriveWebhookSubscriptionDto(expiration=datetime.fromtimestamp(int(result['expiration']) / 1000))
            return await self._g_drive_subscription_repo.update(g_drive_subscription_id, obj_in.model_dump(exclude_none=True))
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to renew document change notification: {str(e)}"
            )

    async def stop_webhook_subscription(self, g_drive_subscription_id: str) -> bool:
        """
        Stop an existing webhook subscription, maybe when a property is sold.
        """
        await self._g_drive_subscription_validator.should_exist_by_id(g_drive_subscription_id)

        try:
            subscription = await self._g_drive_subscription_repo.get(g_drive_subscription_id)

            result = await self._google_drive.stop_watching(subscription.channel_id, subscription.resource_id)

            return await self._g_drive_subscription_repo.hard_delete(subscription.id)

        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to stop document change notification: {str(e)}"
            )

    async def get_g_drive_subscription(self, g_drive_subscription_id: str) -> QueryGoogleDriveWebhookSubscriptionDto:
        await self._g_drive_subscription_validator.should_exist_by_id(g_drive_subscription_id)
        return await self._g_drive_subscription_repo.get(g_drive_subscription_id)

    async def get_g_drive_subscription_page(self, search_dto: SearchGoogleDriveWebhookSubscriptionDto) -> Page[
        QueryGoogleDriveWebhookSubscriptionDto]:
        return await self._g_drive_subscription_repo.get_page(search_dto=search_dto)

    async def soft_delete_g_drive_subscription(self, g_drive_subscription_id: str) -> bool:
        await self._g_drive_subscription_validator.should_exist_by_id(g_drive_subscription_id)
        await self._g_drive_subscription_repo.soft_delete(g_drive_subscription_id)

        return True
