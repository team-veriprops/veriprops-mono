# TODO(gap): this package is dead and does not import — `repo.py`, `service.py` and
# `validator.py` all reference `main.app.domain.webhook.google_drive.*` and `main.app.db.repo`,
# neither of which exists, so only this module loads. It registers
# `g_drive_webhook_subscriptions` with no migration builder behind it. Nothing in the app's
# import graph reaches any of it, so it is inert rather than broken in production — kept and
# marked rather than deleted (D83, 2026-09-03), because it is vendored code outside the
# WhatsApp scope. The choice when someone picks it up: remove the package, or fix the imports
# and give the table a migration. PRD "Known Gaps & Roadmap".
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, DateTime

from main.appodus_utils import BaseEntity, BaseQueryDto, PageRequest, Object


class GoogleDriveWebhookSubscription(BaseEntity):
    __tablename__ = 'g_drive_webhook_subscriptions'
    resource_id = Column(String, unique=True, index=True)
    google_doc_id = Column(String, index=True)
    contract_id = Column(String)
    expiration = Column(DateTime)
    webhook_url = Column(String)
    channel_id = Column(String)


class GoogleDriveWebhookSubscriptionBaseDto(Object):
    pass


class CreateGoogleDriveWebhookSubscriptionDto(GoogleDriveWebhookSubscriptionBaseDto):
    resource_id: str
    google_doc_id: str
    contract_id: str
    expiration: datetime
    webhook_url: str
    channel_id: str


class UpdateGoogleDriveWebhookSubscriptionDto(GoogleDriveWebhookSubscriptionBaseDto):
    pass


class _UpdateGoogleDriveWebhookSubscriptionDto(Object):
    expiration: Optional[datetime] = None


class QueryGoogleDriveWebhookSubscriptionDto(CreateGoogleDriveWebhookSubscriptionDto,
                                              _UpdateGoogleDriveWebhookSubscriptionDto, BaseQueryDto):
    pass


class SearchGoogleDriveWebhookSubscriptionDto(PageRequest, BaseQueryDto):
    resource_id: Optional[str] = None
    google_doc_id: Optional[str] = None
    contract_id: Optional[str] = None
    expiration: Optional[datetime] = None
    webhook_url: Optional[str] = None
    channel_id: Optional[str] = None
