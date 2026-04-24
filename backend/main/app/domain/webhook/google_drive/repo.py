from typing import Type

from kink import inject
from more_itertools.more import first
from sqlalchemy import and_, literal
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.db.repo import GenericRepo
from main.app.domain.webhook.google_drive.model import GoogleDriveWebhookSubscription, CreateGoogleDriveWebhookSubscriptionDto, UpdateGoogleDriveWebhookSubscriptionDto, QueryGoogleDriveWebhookSubscriptionDto, SearchGoogleDriveWebhookSubscriptionDto


@inject
class GoogleDriveWebhookSubscriptionRepo(GenericRepo[GoogleDriveWebhookSubscription, CreateGoogleDriveWebhookSubscriptionDto, UpdateGoogleDriveWebhookSubscriptionDto, QueryGoogleDriveWebhookSubscriptionDto, SearchGoogleDriveWebhookSubscriptionDto]):
    def __init__(self, db: AsyncSession, model: Type[GoogleDriveWebhookSubscription] = GoogleDriveWebhookSubscription, query_dto: Type[QueryGoogleDriveWebhookSubscriptionDto] = QueryGoogleDriveWebhookSubscriptionDto):
        super().__init__(db, model, query_dto)
        self.db = db
